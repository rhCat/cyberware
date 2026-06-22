"""P1-T08 — principal auth + token-bucket rate-limit logic (infra/govern/principals.py).

Pins both sides of every comparison so the gate logic is mutation-killable (the agent-mode syscall
boundary's identity check)."""
from __future__ import annotations

from infra.govern import principals as P


def test_authenticate_matches_token_sha_and_rejects_others():
    reg = {"a": {"token_sha": P.token_sha("S")}}
    assert P.authenticate("S", reg) == "a"
    assert P.authenticate("wrong", reg) is None
    assert P.authenticate("", reg) is None


def test_bearer_of_only_accepts_the_bearer_scheme():
    assert P.bearer_of("Bearer xyz") == "xyz"
    assert P.bearer_of("bearer xyz") == "xyz"
    assert P.bearer_of("token=xyz") == ""           # query-style is NOT accepted
    assert P.bearer_of("Basic xyz") == ""
    assert P.bearer_of("") == ""


def test_rate_ok_burst_then_throttle_then_refill():
    b = {}
    assert [P.rate_ok(b, 100.0, 1.0, 3) for _ in range(3)] == [True, True, True]
    assert P.rate_ok(b, 100.0, 1.0, 3) is False     # burst exhausted at the same instant -> throttled
    assert P.rate_ok(b, 101.0, 1.0, 3) is True       # 1s later -> exactly one token refilled
    assert P.rate_ok(b, 101.0, 1.0, 3) is False      # only one refilled


def test_record_has_principal():
    assert P.record_has_principal({"principal": "a"}) is True
    assert P.record_has_principal({"principal": ""}) is False
    assert P.record_has_principal({}) is False


def test_load_principals_absent_is_empty(tmp_path):
    assert P.load_principals(str(tmp_path / "nope.json")) == {}


def test_selftest_ok():
    assert P.principals_selftest()["ok"] is True
