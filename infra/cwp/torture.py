"""Reusable Ledger-v2 durability torture harness (P1-T02).

The durability proof for the Ledger-v2 chain: imported by the unit suite (fast scale) AND by the
governed `cws-ledgercheck/torture` perk (P1-T09). Each writer process appends via
`ledger.durable_append`, which re-reads the chain tail UNDER an exclusive lock and links from it, so N
concurrent writers serialize into ONE valid prev-hash chain (never from a stale in-memory copy). The
harness reads the result back (torn-tail-aware) and checks the durability acceptance: zero lost (count),
zero torn (every line parses), a single valid chain (verify_chain), contiguous seq.
"""
import json
import multiprocessing
import os
import signal
import time

from infra.cwp import ledger as L

# Use a fork context explicitly: macOS defaults to 'spawn' (3.8+), which re-imports the parent module in
# each child — flaky/slow here. fork is safe for these workers (they only open+flock+append a file; the
# parent holds no ledger lock at spawn time) and is the default on Linux/CI anyway.
_CTX = multiprocessing.get_context("fork")


class TortureConfig:
    def __init__(self, workers=8, appends_per=200, timeout_sec=60):
        self.workers = workers
        self.appends_per = appends_per
        self.timeout_sec = timeout_sec


FAST = TortureConfig(8, 200)          # ~1600 appends, sub-2s — the unit-suite scale
FULL = TortureConfig(16, 5000)        # the acceptance scale (16 writers x 5000) — governed perk only


def _writer(chain_path, worker_id, count, barrier):
    """Top-level + picklable (macOS spawn-safe). Append `count` linked records to the shared chain."""
    if barrier is not None:
        barrier.wait()                # fire all writers together for genuine contention
    for i in range(count):
        L.durable_append(chain_path, {"task_id": f"w{worker_id}_i{i}", "verdict": "pass", "worker": worker_id})


def _ensure_genesis(chain_path):
    if not os.path.exists(chain_path) or os.path.getsize(chain_path) == 0:
        L.write_chain(chain_path, [L.genesis("run-torture", "plan-torture")])


def _all_lines_parse(chain_path):
    with open(chain_path) as f:
        for ln in f.read().splitlines():
            if ln.strip():
                try:
                    json.loads(ln)
                except json.JSONDecodeError:
                    return False
    return True


def run_concurrent_torture(chain_path, config=FAST):
    """Spawn config.workers processes each appending config.appends_per records concurrently. Returns
    (report, entries)."""
    chain_path = str(chain_path)
    _ensure_genesis(chain_path)
    barrier = _CTX.Barrier(config.workers)
    procs = [_CTX.Process(target=_writer, args=(chain_path, w, config.appends_per, barrier))
             for w in range(config.workers)]
    for p in procs:
        p.start()
    for p in procs:
        p.join(config.timeout_sec)
    alive = [p for p in procs if p.is_alive()]
    for p in alive:
        p.terminate()
    entries, schema, truncation = L.read_chain(chain_path, allow_torn_tail=True)
    total_expected = 1 + config.workers * config.appends_per
    ok_chain, problems = L.verify_chain(entries, schema)
    seqs = [e.get("seq") for e in entries[1:]]
    report = {"workers": config.workers, "appends_per": config.appends_per,
              "total_expected": total_expected, "entry_count": len(entries),
              "lost": total_expected - len(entries), "all_parse": _all_lines_parse(chain_path),
              "verify_chain_ok": ok_chain, "problems": problems[:3],
              "seqs_contiguous": seqs == list(range(1, len(entries))),
              "truncation": truncation, "alive_after_timeout": len(alive)}
    return report, entries


def run_crash_torture(chain_path, kills=4, appends_per=2000):
    """Spawn writers and SIGKILL them mid-write, then assert read_chain recovers (a torn tail is dropped
    and recorded) and the recovered prefix verify_chain's clean — kill-9 must never corrupt the chain."""
    chain_path = str(chain_path)
    _ensure_genesis(chain_path)
    procs = [_CTX.Process(target=_writer, args=(chain_path, w, appends_per, None))
             for w in range(kills)]
    for p in procs:
        p.start()
    time.sleep(0.05)
    for p in procs:
        try:
            os.kill(p.pid, signal.SIGKILL)
        except ProcessLookupError:
            pass
    for p in procs:
        p.join(5)
    entries, schema, truncation = L.read_chain(chain_path, allow_torn_tail=True)
    ok_chain, problems = L.verify_chain(entries, schema)
    return {"entry_count": len(entries), "verify_chain_ok": ok_chain, "problems": problems[:3],
            "truncation": truncation, "recovered": ok_chain}, entries
