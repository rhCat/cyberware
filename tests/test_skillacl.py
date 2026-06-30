"""Step 6 — the ACCESS-1 skill-intrinsic access gate (infra/govern/skillacl.py + its wiring in govern()).

A skill's OWN access policy (`access.json`), independent of the per-actor token ACL. Default: local-open /
remote-closed, but back-compat — an undeclared skill stays remote-open until the `skillacl_enforce` rollout
flag; a govd in local mode or a `local_dev` principal is always open; a DECLARED policy is always enforced.
"""
from __future__ import annotations
import os

from infra import registry
from infra.govern import govd, skillacl


def _problem_ids(v):
    return {p.get("id") for p in v.get("problems", [])}


# ── the gate truth table (unit) ──
def test_selftest_truth_table():
    r = skillacl.skillacl_selftest()
    assert r["ok"], r


def test_access_allows_branches():
    A = skillacl.access_allows
    assert A(None, mode="local")[0]                                          # local-open
    assert A(None, mode="remote", is_local_dev=True)[0]                      # dev override
    assert A(None, mode="remote")[0]                                         # undeclared -> open (flag off)
    assert not A(None, mode="remote", enforce_default_closed=True)[0]        # undeclared -> closed (flag on)
    assert A({"remote": True}, mode="remote")[0]                             # declared opt-in
    assert not A({"remote": False}, mode="remote")[0]                        # declared, not remote-exposed
    assert not A("not-a-dict", mode="remote")[0]                             # malformed -> fail closed
    ok, prob = A({"remote": True, "principals": ["pm"]}, mode="remote", principal="x")
    assert not ok and prob["id"] == "skill_principal_denied"
    ok, prob = A({"remote": True, "min_tier": "core"}, mode="remote", principal_tier="community")
    assert not ok and prob["id"] == "skill_tier_below_floor"


# ── load_access + the policy sha ──
def test_load_access_reads_the_policy(tmp_path, monkeypatch):
    chip = str(tmp_path)
    d = os.path.join(chip, "general", "widget")
    os.makedirs(d)
    open(os.path.join(d, "perks.json"), "w").write('{"skill":"widget","perks":[]}')
    monkeypatch.setattr(registry, "SKILLCHIP", chip)
    assert skillacl.load_access("general:widget") is None                    # absent -> None (default)
    open(os.path.join(d, "access.json"), "w").write('{"remote": true}')
    assert skillacl.load_access("general:widget") == {"remote": True}        # present -> dict
    open(os.path.join(d, "access.json"), "w").write("{ not json")
    assert skillacl.load_access("general:widget") == {"remote": False}       # malformed -> CLOSED sentinel


def test_access_policy_sha_is_stable_and_distinct():
    a = skillacl.access_policy_sha({"remote": True})
    assert a == skillacl.access_policy_sha({"remote": True})                  # stable
    assert a != skillacl.access_policy_sha(None)                              # a policy != no-policy
    assert skillacl.access_policy_sha(None) == skillacl.access_policy_sha("garbage")  # both -> the closed sentinel


# ── the gate is WIRED into govern() (integration on a real, undeclared skill) ──
def test_govern_local_mode_is_open():
    v = govd.govern({"skill": "fs", "perk": "find_large", "var_keys": ["SEARCH_DIR"]}, {"mode": "local"})
    assert "skill_remote_closed" not in _problem_ids(v)


def test_govern_remote_default_open_until_the_flag():
    base = {"skill": "fs", "perk": "find_large", "var_keys": ["SEARCH_DIR"]}
    assert "skill_remote_closed" not in _problem_ids(govd.govern(base, {"mode": "remote"}))               # back-compat
    assert "skill_remote_closed" in _problem_ids(
        govd.govern(base, {"mode": "remote", "skillacl_enforce": True}))                                  # flag -> closed


def test_govern_remote_dev_override_opens():
    v = govd.govern({"skill": "fs", "perk": "find_large", "var_keys": ["SEARCH_DIR"]},
                    {"mode": "remote", "skillacl_enforce": True}, local_dev=True)
    assert "skill_remote_closed" not in _problem_ids(v)                       # a local_dev principal is always open
