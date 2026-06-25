#!/usr/bin/env python3
"""infra/store/mirror.py — P5-T01: the best-effort ASYNC mirror of govd's provenance into the chained-JSONL
ARTIFACT OF RECORD + a derived StoreBackend index.

It lives OUT of infra/govern/govd.py on purpose: govd (the enforcement surface) only constructs a StoreMirror
and hands it value-free snapshots; ALL the queue / worker / projection logic — and its mutable branches —
lives here, with its own tests. So the decision path stays thin and its mutation surface unchanged.

A SINGLE daemon worker drains a bounded queue and writes chain-FIRST then index, each job isolated in
try/except. The mirror is therefore:
  * OFF the decision path — the request thread only enqueues a snapshot; no flock/fsync/DB latency on it;
  * exception-isolated — a backend (or chain) fault logs and is swallowed, never failing a decision;
  * single-writer — one worker ⇒ no chain genesis/append race.
The session token can never reach the chain/index: both projections are ALLOWLISTS (a new field is excluded
by default), and the chain (artifact of record) is written before the derived index.
"""
from __future__ import annotations
import json
import os
import queue
import sys
import threading
import time

# value-free projections — ALLOWLISTS (defense in depth): a newly-added, possibly secret-bearing field is
# excluded by default; the token / wrapper / model-check spec+log can never ride into the chain or the index.
_SAFE_RUN_KEYS = ("ts", "skill", "perk", "decision", "destructive", "approved", "plan_sha", "var_keys",
                  "principal", "snippet_shas", "traceparent")
_SAFE_EVENT_KEYS = ("ts", "type", "step", "status", "exit", "reason", "span", "authority", "keyid",
                    "snippet_shas", "meter", "traceparent")


def value_free_run(rec):
    return {k: rec.get(k) for k in _SAFE_RUN_KEYS if k in rec}


def value_free_event(event):
    return {k: event[k] for k in _SAFE_EVENT_KEYS if k in event}


class StoreMirror:
    """Async, best-effort mirror of a provenance run into the chain (artifact of record) + the derived index."""

    def __init__(self, root, cfg=None, maxsize=20000):
        self.chain = self.backend = self._cols = None
        self._q = queue.Queue(maxsize=maxsize)
        self._worker = None
        self.root = root
        self._lease_guard = None        # P5-T04: () -> bool — do I hold the single-writer lease? None ⇒ single-node
        self.blocked = 0                # split-brain attempts this instance refused to write (for the drill/tests)
        try:
            from infra.store import backend as _sb
            from infra.store import chainstore as _cs
            self.chain = _cs.ChainStore(root)
            self.backend = _sb.make_backend(root, cfg or {})
            self._cols = _cs.record_columns
            self._worker = threading.Thread(target=self._drain, name="govd-store-mirror", daemon=True)
            self._worker.start()
        except Exception as e:                               # the index is optional; degrade to snapshot only
            sys.stderr.write(f"[govd] store mirror unavailable, continuing on snapshot only: {e}\n")
            self.chain = self.backend = self._cols = None

    def enabled(self):
        return self.chain is not None

    def set_lease_guard(self, guard):
        """P5-T04: install the single-writer gate. `guard` is a no-arg callable returning True iff THIS instance
        currently holds the write lease. With a guard installed, the drain worker writes to the SHARED artifact
        of record ONLY while we hold the lease; a write attempted without the lease is DROPPED and recorded as a
        split-brain attempt (so a partitioned ex-active can never append behind the new active's back)."""
        self._lease_guard = guard

    def _record_blocked(self, job):
        """A shared write refused because this instance does not hold the lease — record the attempt as evidence
        (value-free: op/run/kind/ts only) to a local jsonl, never to the shared chain we are barred from."""
        self.blocked += 1
        try:
            ev = {"ts": round(time.time(), 3), "op": job.get("op"), "run_id": job.get("run_id"),
                  "kind": job.get("kind"), "reason": "no_lease_split_brain_blocked"}
            with open(os.path.join(self.root, "split-brain-attempts.jsonl"), "a") as f:
                f.write(json.dumps(ev, sort_keys=True) + "\n")
        except Exception as e:
            sys.stderr.write(f"[govd] split-brain attempt (unrecordable): {e}\n")

    def record_run(self, run_id, record):
        """Enqueue a run's CREATE record (its plan_sha is also the out-of-band expected origin)."""
        plan = record.get("plan_sha", "")
        self._put({"op": "record", "run_id": run_id, "plan_sha": plan, "kind": "create",
                   "fields": value_free_run(record), "origin_plan": plan})

    def record_event(self, run_id, plan_sha, event):
        """Enqueue one value-free event for a run."""
        self._put({"op": "record", "run_id": run_id, "plan_sha": plan_sha, "kind": "event",
                   "fields": value_free_event(event), "origin_plan": None})

    def decision(self, summary):
        """Enqueue one verdict for the decisions chain/index."""
        self._put({"op": "decision", "summary": summary})

    def _put(self, job):
        if self.chain is None:
            return
        try:
            self._q.put_nowait(job)
        except queue.Full:
            sys.stderr.write("[govd] store mirror queue full; dropping a job (index reconcile-repairs)\n")
        except Exception as e:
            sys.stderr.write(f"[govd] store mirror enqueue failed: {e}\n")

    def _drain(self):
        """The SINGLE mirror writer. Drains forever; each job's chain+index write is isolated so one bad job
        never stops the worker. Chain (artifact of record) is written BEFORE the derived index."""
        while True:
            job = self._q.get()
            try:
                # P5-T04 single-writer gate: only the lease HOLDER may touch the shared artifact of record. A
                # write enqueued without the lease (a partitioned ex-active, a rogue second writer) is refused
                # and recorded — never appended — so the shared chain has exactly one writer at a time.
                if self._lease_guard is not None and not self._lease_guard():
                    self._record_blocked(job)
                    continue
                if job.get("op") == "decision":
                    self.chain.append_decision(job["summary"])
                    if self.backend is not None:
                        self.backend.index_decision(job["summary"])
                else:
                    rec = self.chain.append_record(job["run_id"], job["plan_sha"], job["kind"], job["fields"])
                    if self.backend is not None:
                        if job.get("origin_plan") is not None:
                            self.backend.set_origin(job["run_id"], job["origin_plan"])
                        if self._cols is not None:
                            c = self._cols(rec)
                            self.backend.index_record(c["run_id"], c["seq"], c["prev"], c["link_digest"],
                                                      c["kind"], c["ts"], c["plan_sha"], c["fields"])
            except Exception as e:
                sys.stderr.write(f"[govd] store mirror write failed: {e}\n")
            finally:
                self._q.task_done()

    def flush(self, timeout=10.0):
        """Block until every enqueued job is fully WRITTEN, not merely dequeued. `unfinished_tasks` counts jobs
        the worker has `get()`-ed but not yet `task_done()`-ed, so it stays > 0 while a write is still in flight
        — `empty()` alone goes True the instant the last job is dequeued, before its chain+index write lands.
        Waiting on `unfinished_tasks` is what makes a post-flush read / reconcile race-free under load (a writer
        mid-INSERT must not overlap a reader opening the same sqlite). Best-effort under the timeout."""
        if self.chain is None:
            return
        deadline = time.time() + timeout
        while self._q.unfinished_tasks and time.time() < deadline:
            time.sleep(0.005)
