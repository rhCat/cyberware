#!/usr/bin/env python3
"""infra/settle/throughput.py — P6-T16 single-writer-per-currency group commit + checkpoint resume.

Settlement throughput without losing the double-entry invariants. Two pieces:

  * GroupCommitWriter — ONE writer per currency. Posting sets are staged then committed as a BATCH: the whole
    batch is validated balanced first, then appended atomically (all-or-nothing — a single unbalanced set in
    the batch rejects the batch, never a partial append). Per-currency serialization (a lock) means two
    writers never interleave on the same currency's chain. The writer maintains RUNNING balances
    incrementally (O(postings) per commit), so committing is not re-folding the whole history each time.
  * checkpoint / resume_verify — a checkpoint captures the committed balance SET plus its balance-root (the
    same Merkle commitment reward_ledger.balance_root computes). Resume recomputes the root from the
    checkpoint's stored balances and verifies it matches — O(accounts), independent of how many entries
    were committed, so a writer that restarts after 1M entries verifies its resume point cheaply.

Built on infra.settle.reward_ledger (balanced posting sets, exact Money, balance_root). No floats, no I/O.
"""
from __future__ import annotations
import hashlib
import threading

from infra.settle import reward_ledger as RL
from infra.settle.money import Money


def _balances_root(items):
    """Merkle root over balance items [(account, currency, amount_str)] — the SAME commitment
    reward_ledger.balance_root computes: sorted by (account, currency), leaf `account|currency|amount`."""
    from infra.cwp import checkpoint as cp
    leaves = [hashlib.sha256(f"{a}|{c}|{amt}".encode()).digest()
              for a, c, amt in sorted(items, key=lambda t: (t[0], t[1]))]
    return cp.merkle_root(leaves).hex()


class GroupCommitWriter:
    """Single-writer-per-currency group-commit batcher over one reward-ledger `entries` chain."""

    def __init__(self, entries, currency="USD"):
        self.entries = entries
        self.currency = currency
        self._lock = threading.Lock()       # per-writer serialization: one commit to this chain at a time
        self._staged = []
        self._bal = {}                      # running {(account, currency): Money}, maintained incrementally
        self.committed = 0

    def stage(self, postings):
        """Queue one posting set for the next group commit (not yet on the chain)."""
        self._staged.append(list(postings))
        return len(self._staged)

    def commit(self, memo="group"):
        """Validate EVERY staged posting set is balanced, then append them all atomically + fold them into the
        running balances. Returns the count committed so far. A single unbalanced set raises BEFORE any append
        — the batch is all-or-nothing, the chain never sees a partial group."""
        with self._lock:
            batch = self._staged
            if not batch:
                return self.committed
            for postings in batch:                      # validate the WHOLE batch first (atomicity)
                if not RL.is_balanced(postings):
                    raise ValueError("unbalanced posting set in batch — group commit refused (no partial append)")
            for postings in batch:                      # all valid -> append all + fold incrementally
                RL.post(self.entries, postings, memo)
                for p in postings:
                    k = (p["account"], p["currency"])
                    self._bal[k] = (self._bal.get(k) or Money.zero(p["currency"])) + Money(p["amount"], p["currency"])
            self.committed += len(batch)
            self._staged = []
            return self.committed

    def checkpoint(self):
        """An O(accounts) checkpoint from the RUNNING balances — no re-fold of the entry history."""
        items = [(a, c, str(m.amount)) for (a, c), m in self._bal.items()]
        return {"root": _balances_root(items),
                "balances": {f"{a}|{c}": amt for a, c, amt in items}, "committed": self.committed}


def checkpoint(entries):
    """An ad-hoc checkpoint folded from a ledger chain (O(entries)). For a live writer prefer
    GroupCommitWriter.checkpoint(), which reads the running balances in O(accounts)."""
    items = [(a, c, str(m.amount)) for (a, c), m in RL.balances(entries).items()]
    return {"root": _balances_root(items),
            "balances": {f"{a}|{c}": amt for a, c, amt in items},
            "committed": sum(1 for e in entries if e.get("type") == "posting_set")}


def resume_verify(ckpt):
    """The RESUME proof: recompute the balance-root from the checkpoint's stored balance set and verify it
    equals the committed root — O(accounts), independent of the entry count. A checkpoint whose balances were
    altered, or whose root was tampered, fails; so does a malformed checkpoint."""
    if not isinstance(ckpt, dict) or "root" not in ckpt or "balances" not in ckpt:
        return False
    items = [(k.rsplit("|", 1)[0], k.rsplit("|", 1)[1], v) for k, v in ckpt["balances"].items()]
    return _balances_root(items) == ckpt["root"]


def throughput_selftest():
    """Correctness of the throughput path (not a benchmark): a balanced batch group-commits atomically, an
    unbalanced member rejects the WHOLE batch with no partial append, the writer's running checkpoint matches
    the folded ledger root, checkpoint->resume verifies (and rejects a tampered checkpoint), and value stays
    conserved. `ok` iff all hold."""
    entries = RL.open_ledger("throughput", "throughput-plan")
    w = GroupCommitWriter(entries, "USD")
    for i in range(50):
        w.stage([RL._posting(f"payer{i}", -Money("1.00", "USD")), RL._posting(f"payee{i}", Money("1.00", "USD"))])
    w.commit("batch-1")
    committed_n = sum(1 for e in entries if e.get("type") == "posting_set")
    batched_ok = committed_n == 50 and w.committed == 50

    before = len(entries)
    w.stage([RL._posting("x", -Money("1.00", "USD")), RL._posting("y", Money("1.00", "USD"))])
    w.stage([RL._posting("bad", Money("5.00", "USD"))])                 # unbalanced -> rejects the batch
    atomic = False
    try:
        w.commit("batch-2")
    except ValueError:
        atomic = len(entries) == before                                 # NO partial append from the bad batch

    cp = w.checkpoint()
    running_matches_fold = cp["root"] == RL.balance_root(entries)        # running checkpoint == the ledger's root
    resume_ok = resume_verify(cp)
    resume_detects_tamper = not resume_verify({"root": "0" * 64, "balances": cp["balances"]})
    conserved = RL.global_zero(entries)
    ok = bool(batched_ok and atomic and running_matches_fold and resume_ok and resume_detects_tamper and conserved)
    return {"batched_ok": batched_ok, "atomic_batch": atomic, "running_matches_fold": running_matches_fold,
            "resume_ok": resume_ok, "resume_detects_tamper": resume_detects_tamper, "conserved": conserved,
            "ok": ok}


if __name__ == "__main__":
    import json
    import sys
    r = throughput_selftest()
    print(json.dumps(r, indent=2))
    sys.exit(0 if r["ok"] else 1)
