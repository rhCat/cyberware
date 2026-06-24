#!/usr/bin/env python3
"""infra/store/chainstore.py — P5-T01: the per-run chained-JSONL ARTIFACT OF RECORD for govd's provenance.

govd's Store historically wrote plain per-run `ledger.json` snapshots + a flat `decisions.jsonl` (no prev-hash
chain, no fsync-on-append). P5-T01 introduces a prev-hash chain per run (and one for the decisions feed) as
the authoritative, tamper-evident **artifact of record**, over `infra.cwp.ledger`'s crash-safe
`durable_append` (flock + fsync + torn-tail recovery). The SQL `StoreBackend` is a DERIVED index of this
chain; the reconciler proves index == chain. The chain is appended **chain-first**, the index mirrored after —
so a crash can leave the index behind the chain (reconcilable) but never ahead.

Path convention:
  <root>/<run_id>/chain.jsonl     one prev-hash chain per run (genesis binds run_id + plan_sha)
  <root>/decisions.chain.jsonl    one prev-hash chain for the verdict feed

NEVER write a secret (the session token) into a chain — `fields` is a value-free projection by construction.
"""
from __future__ import annotations
import os
import threading

from infra.cwp import chainverify
from infra.cwp import ledger

SCHEMA = chainverify.CURRENT_MAJOR              # major-2: canonical RFC-8785 JCS link digest


def run_chain_path(root, run_id):
    return os.path.join(root, run_id, "chain.jsonl")


def decisions_chain_path(root):
    return os.path.join(root, "decisions.chain.jsonl")


def link_digest(rec):
    """A linked chain record's OWN link digest (the value the next record's `prev` must equal)."""
    return chainverify.link_digest(chainverify.link_of(rec), SCHEMA)


def record_columns(rec):
    """Project a linked chain record into the value-free index columns the StoreBackend stores."""
    f = rec.get("fields", {}) or {}
    return {"run_id": rec.get("run_id"), "seq": rec.get("seq"), "prev": rec.get("prev"),
            "link_digest": link_digest(rec), "kind": rec.get("kind", rec.get("type", "")),
            "ts": f.get("ts", "") or rec.get("ts", ""), "plan_sha": rec.get("plan_sha", ""), "fields": f}


class ChainStore:
    """The artifact-of-record write/read seam — the ONLY place that appends to a run / decisions chain."""

    def __init__(self, root):
        self.root = os.path.abspath(os.path.expanduser(root))
        # serialize this instance's genesis-check + append so two threads can't both seed a genesis (the
        # cross-PROCESS case is the single-writer-per-record-root assumption the durable_append flock already
        # encodes for appends; govd drives all chain writes through ONE worker thread regardless).
        self._lock = threading.Lock()

    def _genesis_if_empty(self, path, run_id, plan_sha):
        if not os.path.isfile(path) or os.path.getsize(path) == 0:
            os.makedirs(os.path.dirname(path), exist_ok=True)
            ledger.durable_append(path, ledger.genesis(run_id, plan_sha, SCHEMA), SCHEMA)

    def append_record(self, run_id, plan_sha, kind, fields):
        """Append one value-free record to this run's chain (writes the genesis on first touch). Returns the
        linked record (with seq + prev). `fields` MUST be value-free (no token / wrapper / model-check log)."""
        path = run_chain_path(self.root, run_id)
        rec = {"type": "record", "kind": kind, "run_id": run_id, "plan_sha": plan_sha, "fields": dict(fields)}
        with self._lock:
            self._genesis_if_empty(path, run_id, plan_sha)
            return ledger.durable_append(path, rec, SCHEMA)

    def append_decision(self, summary):
        """Append one verdict to the global decisions chain (value-free metadata)."""
        path = decisions_chain_path(self.root)
        rec = {"type": "decision", "run_id": summary.get("run_id"), "plan_sha": summary.get("plan_sha", ""),
               "kind": "decision", "fields": dict(summary)}
        with self._lock:
            self._genesis_if_empty(path, "decisions-feed", "decisions")
            return ledger.durable_append(path, rec, SCHEMA)

    def read_run(self, run_id):
        """(entries, schema, truncation) for a run's chain — torn final line tolerated (a crash artifact)."""
        path = run_chain_path(self.root, run_id)
        if not os.path.isfile(path):
            return [], SCHEMA, None
        return ledger.read_chain(path, allow_torn_tail=True)

    def run_ids(self):
        """Run ids that have a chain on disk (the artifact-of-record side of the set-diff)."""
        if not os.path.isdir(self.root):
            return []
        out = []
        for name in os.listdir(self.root):
            if os.path.isfile(run_chain_path(self.root, name)):
                out.append(name)
        return sorted(out)
