#!/usr/bin/env python3
"""tests/test_acl.py — per-actor ACL (M0): govern() threads the principal scope as a PURE restriction.

The pure decision core (`principals.acl_allows`/`acl_sha`) is pinned both-sides by
`infra/govern/principals.py::principals_selftest`. Here we pin the govern() INTEGRATION: the ACL can only ADD
a hard, non-self-approvable reject; it never relaxes another gate (the floor-monotone P1 property); an
out-of-scope claim cannot self-approve; and a non-canonical name is rejected before the claim is blessed.
"""
from __future__ import annotations
import json
import os

from infra import registry
from infra.govern import govd
from infra.tool import skill_index


def _a_real_claim():
    """The first real (skill, perk) on whatever chip is mounted — robust to the catalog's contents."""
    skill = sorted(skill_index.all_skills())[0]
    perks = json.load(open(os.path.join(registry.skill_dir(skill), "perks.json")))["perks"]
    return skill, perks[0]["id"]


def _ids(v):
    return [p["id"] for p in v.get("problems", [])]


def test_unscoped_is_unrestricted_but_strict_denies():
    skill, perk = _a_real_claim()
    ledger = {"skill": skill, "perk": perk, "var_keys": []}
    # no scope, not strict -> the ACL adds nothing (back-compat: byte-identical to pre-ACL behaviour)
    assert not any(i.startswith("acl_") for i in _ids(govd.govern(ledger, {}, scope=None, strict=False)))
    # no scope, strict -> deny-by-default (the Phase-B end-state)
    v = govd.govern(ledger, {}, scope=None, strict=True)
    assert "acl_unscoped" in _ids(v) and v["decision"] == "reject"


def test_out_of_scope_skill_is_hard_rejected():
    skill, perk = _a_real_claim()
    v = govd.govern({"skill": skill, "perk": perk, "var_keys": []},
                    {}, scope={"skills": ["something-not-this-skill"]})
    assert "acl_skill_denied" in _ids(v) and v["decision"] == "reject"


def test_in_scope_claim_adds_no_acl_problem_and_is_a_pure_restriction():
    skill, perk = _a_real_claim()
    ledger = {"skill": skill, "perk": perk, "var_keys": []}
    permissive = {"skills": [skill], "perks": {skill: [perk]}, "max_tier": "community", "secrets": True}
    scoped = govd.govern(ledger, {}, scope=permissive)
    unscoped = govd.govern(ledger, {}, scope=None)
    assert not any(i.startswith("acl_") for i in _ids(scoped))          # in scope -> the ACL rejects nothing
    # P1 (floor-monotone): the ACL is a PURE restriction — it removes NO problem the unscoped run reported.
    assert set(_ids(unscoped)) <= set(_ids(scoped))


def test_noncanonical_perk_name_is_rejected_before_blessing():
    skill, perk = _a_real_claim()
    for bad in ("./" + perk, perk + "/", "a/b", ".."):
        v = govd.govern({"skill": skill, "perk": bad, "var_keys": []}, {})
        assert "noncanonical_name" in _ids(v) and v["decision"] == "reject", bad


def test_acl_reject_is_not_self_approvable():
    # an out-of-scope claim cannot be cleared by approve[] — acl_* are appended, never routed to needs_approve
    skill, perk = _a_real_claim()
    v = govd.govern({"skill": skill, "perk": perk, "var_keys": [], "approve": [perk, "destructive"]},
                    {}, scope={"skills": ["nope"]})
    assert v["decision"] == "reject" and "acl_skill_denied" in _ids(v)
