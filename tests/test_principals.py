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


# ───────────────────────── the auth SEAM (OAuth/OIDC portability) ─────────────────────────
# Every branch here is an IDENTITY decision, so each asserts a fail-CLOSED outcome explicitly.
# The default path must stay byte-identical in behaviour: an existing deployment names no verifier.

def _seam_reg():
    return {"alice": {"subject": "oidc:sub:1a2b3c"},
            "bot": {"token_sha": P.token_sha("s3cret")},
            "nosub": {"subject": "", "token_sha": P.token_sha("other")}}


def test_seam_default_is_unchanged_bearer_secret():
    reg = _seam_reg()
    assert P.resolve_principal("s3cret", reg) == "bot"          # no verifier named
    assert P.resolve_principal("s3cret", reg, "") == "bot"
    assert P.resolve_principal("s3cret", reg, "token_sha") == "bot"
    assert P.resolve_principal("wrong", reg) is None


def test_seam_unknown_verifier_fails_closed():
    # An unknown scheme must NOT silently fall back to the secret path — that would let a typo in
    # auth_verifier quietly re-enable bearer secrets on a deployment that meant to disable them.
    assert P.resolve_principal("s3cret", _seam_reg(), "not-registered") is None


def test_seam_registered_verifier_maps_subject_to_principal():
    P.register_verifier("t_oidc", lambda b: "oidc:sub:1a2b3c" if b == "good" else None)
    reg = _seam_reg()
    assert P.resolve_principal("good", reg, "t_oidc") == "alice"
    assert P.resolve_principal("bad", reg, "t_oidc") is None
    # a bearer SECRET must not authenticate under an external scheme
    assert P.resolve_principal("s3cret", reg, "t_oidc") is None


def test_seam_raising_verifier_is_a_refusal():
    def boom(_b):
        raise RuntimeError("jwks unreachable")
    P.register_verifier("t_boom", boom)
    assert P.resolve_principal("anything", _seam_reg(), "t_boom") is None


def test_seam_empty_subject_never_matches():
    # A principal that has not opted in (no/blank `subject`) must be unreachable via the external scheme,
    # even when the verifier returns an empty claim.
    P.register_verifier("t_empty", lambda _b: "")
    assert P.resolve_principal("x", _seam_reg(), "t_empty") is None
    P.register_verifier("t_blank", lambda _b: None)
    assert P.resolve_principal("x", _seam_reg(), "t_blank") is None
