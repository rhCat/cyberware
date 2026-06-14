"""Mutation-pinning slice for infra/cwp/chainverify.py — the R3 gate cws-mutate/mut-chain-verifier (P1-T10).

Pins BOTH sides of every comparison and every and/or arm in the chain verifier, so a single-token mutation
flips at least one assertion (the cws-mutate engine mutates this file; TEST_CMD failing = a killed mutant).
Imports cwd-relative (sys.path from __file__) so under the mutator it resolves to the SANDBOX copy, never
an absolute live path (the harness-integrity trap). Chains are BUILT with the un-mutated writer
(ledger.genesis/append) and VERIFIED with the target (chainverify.verify_chain)."""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pytest  # noqa: E402

from infra.cwp import chainverify as C  # noqa: E402
from infra.cwp import ledger as L       # noqa: E402


def _chain():
    c = [L.genesis("run-A", "plan-A")]
    L.append(c, {"task_id": "t1", "n": 1})
    L.append(c, {"task_id": "t2", "n": 2})
    return c


def test_clean_passes():
    assert C.verify_chain(_chain(), 2)[0] is True


def test_empty_and_nonobject_genesis_fail():
    assert C.verify_chain([], 2)[0] is False
    assert C.verify_chain(["not a dict"], 2)[0] is False


def test_genesis_type_pinned():
    c = _chain(); c[0] = {**c[0], "type": "step"}
    ok, p = C.verify_chain(c, 2)
    assert ok is False and "genesis" in p[0]


def test_genesis_prev_zero_pinned():
    c = _chain(); c[0] = {**c[0], "prev": "f" * 64}
    assert C.verify_chain(c, 2)[0] is False


def test_origin_and_or_arms():
    # build each chain ON its own genesis so the ONLY fault is the origin binding (not a prev mismatch),
    # which is what pins the inner `run_id and plan_sha` and the two `or` arms.
    g1 = [{"type": "genesis", "schema": 2, "seq": 0, "prev": C.ZERO, "run_id": "r"}]      # run_id only
    L.append(g1, {"task_id": "t1"})
    ok, p = C.verify_chain(g1, 2)
    assert ok is False and "origin" in p[0]
    g2 = [{"type": "genesis", "schema": 2, "seq": 0, "prev": C.ZERO, "plan_sha": "p"}]    # plan_sha only
    L.append(g2, {"task_id": "t1"})
    assert C.verify_chain(g2, 2)[0] is False
    sh = [{"type": "genesis", "schema": 2, "seq": 0, "prev": C.ZERO, "supersedes_head": "h"}]
    L.append(sh, {"task_id": "x"})
    assert C.verify_chain(sh, 2)[0] is True                                               # supersedes_head arm
    sup = [{"type": "genesis", "schema": 2, "seq": 0, "prev": C.ZERO, "supersedes": "done"}]
    L.append(sup, {"task_id": "x"})
    assert C.verify_chain(sup, 2)[0] is True                                              # supersedes arm


def test_transplant_both_sides():
    c = _chain()
    assert C.verify_chain(c, 2, "run-A", "plan-A")[0] is True
    assert C.verify_chain(c, 2, "IMPOSTOR", "plan-A")[0] is False
    assert C.verify_chain(c, 2, "run-A", "IMPOSTOR")[0] is False
    assert "transplant" in C.verify_chain(c, 2, "IMPOSTOR", "plan-A")[1][0]


def test_second_genesis_both_arms_named():
    c = _chain(); c2 = [c[0], {**c[1], "type": "genesis"}, c[2]]   # arm 1: mid-chain genesis type
    ok, p = C.verify_chain(c2, 2)
    assert ok is False and "second genesis" in p[0]
    c = _chain(); c3 = [c[0], {**c[1], "prev": C.ZERO}, c[2]]      # arm 2: mid-chain zero prev
    ok, p = C.verify_chain(c3, 2)
    assert ok is False and "second genesis" in p[0]               # must trip BEFORE the prev-compare


def test_prev_mismatch_named():
    c = _chain(); c[1] = {**c[1], "n": 999}                        # tamper -> downstream prev recompute fails
    ok, p = C.verify_chain(c, 2)
    assert ok is False and "t2" in p[0]


def test_entry_not_object():
    c = _chain(); c[1] = "not a dict"
    assert C.verify_chain(c, 2)[0] is False


def test_seq_contiguity_and_plus_one():
    g = L.genesis("r", "p")
    e1 = {"task_id": "t1", "seq": 1, "prev": C.link_digest(C.link_of(g), 2)}
    gap = {"task_id": "t2", "seq": 3, "prev": C.link_digest(C.link_of(e1), 2)}      # seq jumps 1 -> 3
    ok, p = C.verify_chain([g, e1, gap], 2)
    assert ok is False and "contiguous" in p[0]
    good = {"task_id": "t2", "seq": 2, "prev": C.link_digest(C.link_of(e1), 2)}     # contiguous passes
    assert C.verify_chain([g, e1, good], 2)[0] is True


def test_seq_bool_rejected():
    g = L.genesis("r", "p")
    e1 = {"task_id": "t1", "seq": True, "prev": C.link_digest(C.link_of(g), 2)}
    ok, p = C.verify_chain([g, e1], 2)
    assert ok is False and "integer" in p[0]


def test_schema_dispatch():
    lk = {"task_id": "x", "n": 1}
    assert C.link_digest(lk, 1) != C.link_digest(lk, 2)
    g = {"type": "genesis", "schema": 1, "seq": 0, "prev": C.ZERO, "run_id": "r", "plan_sha": "p"}
    e1 = {"task_id": "t1", "seq": 1, "prev": C.link_digest(C.link_of(g), 1)}
    assert C.verify_chain([g, e1], 1)[0] is True                  # v1-linked verifies under schema 1
    assert C.verify_chain([g, e1], 2)[0] is False                 # ...but not under schema 2
    with pytest.raises(ValueError):
        C.link_digest(lk, 3)                                      # unsupported schema raises


def test_link_of_drops_only_prev():
    assert C.link_of({"task_id": "x", "prev": "abc", "n": 1}) == {"task_id": "x", "n": 1}
    a = {"task_id": "x", "seq": 1, "prev": "AAA"}
    b = {"task_id": "x", "seq": 1, "prev": "BBB"}
    assert C.link_digest(C.link_of(a), 2) == C.link_digest(C.link_of(b), 2)


def test_v1_is_key_order_independent():
    assert C.link_digest_v1({"a": 1, "b": 2}) == C.link_digest_v1({"b": 2, "a": 1})  # pins sort_keys=True
