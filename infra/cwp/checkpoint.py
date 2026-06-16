#!/usr/bin/env python3
"""infra/cwp/checkpoint.py — Merkle checkpoints for Ledger-v2 (P1-T03).

A long chain is expensive to cold-verify in full. A **checkpoint** is a chain entry inserted every
`interval` records carrying a **Merkle root** over the data entries since the previous checkpoint. Two
verification tiers result:

  * **cold-verify** (the hot path, ≤ 2 s for a 1M-entry chain): trust the last *audited* checkpoint and
    re-link only the TAIL after it. The cost is bounded by the checkpoint interval, NOT the chain length.
  * **audit** (the periodic deep pass): recompute every checkpoint's Merkle root over its window and
    compare to the claimed root — a **forged checkpoint** (a tampered root) is detected here.

The Merkle leaf of an entry is its `link_digest` (the same content digest the prev-hash chain uses), so a
checkpoint commits to exactly what the chain records.
"""
from __future__ import annotations
import hashlib

from infra.cwp import ledger
from infra.cwp.chainverify import CURRENT_MAJOR, link_digest, link_of

CHECKPOINT_INTERVAL = 1000


def merkle_root(leaves) -> bytes:
    """A binary SHA-256 Merkle root over the leaf digests (odd nodes duplicate the last). Empty → the
    sha256 of the empty string, so an empty window has a stable, distinguishable root."""
    if not leaves:
        return hashlib.sha256(b"").digest()
    level = list(leaves)
    while len(level) > 1:
        nxt = []
        for i in range(0, len(level), 2):
            a = level[i]
            b = level[i + 1] if i + 1 < len(level) else level[i]
            nxt.append(hashlib.sha256(a + b).digest())
        level = nxt
    return level[0]


def _leaf(entry, schema=CURRENT_MAJOR) -> bytes:
    return bytes.fromhex(link_digest(link_of(entry), schema))


def _is_checkpoint(e) -> bool:
    return isinstance(e, dict) and e.get("type") == "checkpoint"


def make_checkpoint(window, schema=CURRENT_MAJOR) -> dict:
    """A checkpoint record committing (via a Merkle root) to the data entries in `window`."""
    return {"type": "checkpoint",
            "window_start": window[0]["seq"] if window else None,
            "window_end": window[-1]["seq"] if window else None,
            "count": len(window),
            "merkle_root": merkle_root([_leaf(e, schema) for e in window]).hex()}


def build_checkpointed_chain(n, interval=CHECKPOINT_INTERVAL, run_id="ckpt-run", plan_sha="ckpt-plan"):
    """A Ledger-v2 chain of `n` data entries with a checkpoint linked in after every `interval`."""
    entries = [ledger.genesis(run_id, plan_sha)]
    window = []
    for i in range(n):
        ledger.append(entries, {"i": i, "data": f"entry-{i}"})
        window.append(entries[-1])
        if (i + 1) % interval == 0:
            ledger.append(entries, make_checkpoint(window))
            window = []
    return entries


def cold_verify_from_last_checkpoint(entries, schema=CURRENT_MAJOR):
    """Trust the last (audited) checkpoint and re-link only the tail after it. Returns
    (ok, tail_verified) where tail_verified is the number of entries checked — bounded by the interval,
    independent of the chain length. This is the ≤2s cold-verify path."""
    last_cp = len(entries) - 1                              # scan BACKWARD from the tip — O(tail), not O(n)
    while last_cp > 0 and not _is_checkpoint(entries[last_cp]):
        last_cp -= 1
    tail = 0
    for i in range(last_cp + 1, len(entries)):
        if entries[i].get("prev") != link_digest(link_of(entries[i - 1]), schema):
            return False, tail
        tail += 1
    return True, tail


def audit_checkpoints(entries, schema=CURRENT_MAJOR):
    """The deep pass: recompute every checkpoint's Merkle root over its window and compare. Returns
    (ok, problem) — problem names the first forged checkpoint (seq + claimed vs recomputed root)."""
    by_seq = {e["seq"]: e for e in entries if "seq" in e}
    for e in entries:
        if not _is_checkpoint(e):
            continue
        ws, we = e.get("window_start"), e.get("window_end")
        window = [by_seq[s] for s in range(ws, we + 1) if s in by_seq and not _is_checkpoint(by_seq[s])]
        recomputed = merkle_root([_leaf(w, schema) for w in window]).hex()
        if recomputed != e.get("merkle_root"):
            return False, {"checkpoint_seq": e.get("seq"), "claimed": e.get("merkle_root"),
                           "recomputed": recomputed}
    return True, None


def checkpoint_drill(n=20500, interval=CHECKPOINT_INTERVAL, budget_ms=2000) -> dict:
    """The P1-T03 acceptance, demonstrated: build a checkpointed chain, cold-verify from the last checkpoint
    (window-bounded, under budget), confirm a clean audit, then FORGE a checkpoint's Merkle root and confirm
    the audit detects it while cold-verify — which trusts audited checkpoints — does not. Returns a report;
    `ok` is True iff every property holds."""
    import time
    entries = build_checkpointed_chain(n, interval)
    t0 = time.perf_counter()
    cold_ok, tail = cold_verify_from_last_checkpoint(entries)
    cold_ms = (time.perf_counter() - t0) * 1000
    audit_ok, _ = audit_checkpoints(entries)

    # forge: tamper a checkpoint's committed root; the deep audit must catch it
    cps = [e for e in entries if _is_checkpoint(e)]
    forged_detected = True
    if cps:
        victim = cps[len(cps) // 2]
        orig = victim["merkle_root"]
        victim["merkle_root"] = "0" * 64
        forged_ok, problem = audit_checkpoints(entries)
        forged_detected = (not forged_ok) and problem is not None
        victim["merkle_root"] = orig                                   # restore

    window_bounded = tail <= interval + 1                              # tail ~ the in-flight window, not n
    report = {"n": n, "interval": interval, "checkpoints": len(cps),
              "cold_verify_ok": cold_ok, "cold_verify_tail": tail, "cold_verify_ms": round(cold_ms, 2),
              "budget_ms": budget_ms, "within_budget": cold_ms <= budget_ms,
              "window_bounded": window_bounded, "audit_clean": audit_ok,
              "forged_checkpoint_detected": forged_detected}
    report["ok"] = (cold_ok and audit_ok and forged_detected and window_bounded and report["within_budget"])
    return report


if __name__ == "__main__":
    import json
    import sys
    r = checkpoint_drill()
    print(json.dumps(r, indent=2))
    sys.exit(0 if r["ok"] else 1)
