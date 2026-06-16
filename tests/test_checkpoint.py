"""Merkle checkpoints for Ledger-v2 (P1-T03): cold-verify from the last checkpoint is window-bounded
(≤2s regardless of chain length), and a forged checkpoint is caught by the deep audit."""
from __future__ import annotations

from infra.cwp import checkpoint as C


def test_merkle_root_is_deterministic_and_handles_odd_leaves():
    a, b, c = b"a" * 32, b"b" * 32, b"c" * 32
    assert C.merkle_root([a, b]) == C.merkle_root([a, b])         # deterministic
    assert C.merkle_root([a, b, c]) != C.merkle_root([a, b])      # odd leaf changes the root
    assert C.merkle_root([a]) == a or C.merkle_root([a]) is not None


def test_drill_holds():
    r = C.checkpoint_drill()
    assert r["ok"], r
    assert r["cold_verify_ok"] and r["within_budget"] and r["forged_checkpoint_detected"]


def test_cold_verify_is_window_bounded_not_chain_bounded():
    small = C.checkpoint_drill(n=10500)
    big = C.checkpoint_drill(n=80500)
    # the tail re-linked is the in-flight window, identical regardless of chain length
    assert small["cold_verify_tail"] == big["cold_verify_tail"] <= small["interval"] + 1
    assert small["within_budget"] and big["within_budget"]


def test_forged_checkpoint_caught_by_audit_but_not_cold_verify():
    entries = C.build_checkpointed_chain(5000, interval=1000)
    assert C.audit_checkpoints(entries)[0] is True               # clean chain audits clean
    cps = [e for e in entries if e.get("type") == "checkpoint"]
    cps[1]["merkle_root"] = "0" * 64                              # forge a committed root
    ok_audit, problem = C.audit_checkpoints(entries)
    assert not ok_audit and problem["checkpoint_seq"] == cps[1]["seq"]
    # cold-verify trusts audited checkpoints, so it does NOT re-derive their roots — the tail still links
    assert C.cold_verify_from_last_checkpoint(entries)[0] is True


def test_tail_tamper_is_caught_by_cold_verify():
    entries = C.build_checkpointed_chain(1500, interval=1000)     # 500-entry tail after the last checkpoint
    entries[-2]["data"] = "tampered"                             # a mid-tail entry the next prev covers
    assert C.cold_verify_from_last_checkpoint(entries)[0] is False
