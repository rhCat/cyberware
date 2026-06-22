"""P5-T03 — multi-tenant org isolation over principals (infra/govern/orgs.py).

Pins both sides of every comparison so the isolation logic is mutation-killable: the syscall boundary's
tenant check (a principal in org A must reach nothing in org B), revocation, SPIFFE identity, and per-org
record roots."""
from __future__ import annotations

from infra.govern import orgs as O


def _reg():
    from infra.govern import principals as P
    return {
        "org-a": {"principals": {"a1": {"token_sha": P.token_sha("tok-A")}}},
        "org-b": {"principals": {"b1": {"token_sha": P.token_sha("tok-B")},
                                 "b2": {"token_sha": P.token_sha("tok-B2"), "revoked": True}}},
    }


def test_authorize_resolves_to_its_own_org_and_rejects_unknown():
    reg = _reg()
    a = O.authorize("tok-A", reg)
    assert a["org"] == "org-a" and a["principal"] == "a1"
    assert O.authorize("nope", reg) is None
    assert O.authorize("", reg) is None


def test_revoked_principal_authenticates_to_nobody():
    assert O.authorize("tok-B2", _reg()) is None     # revoked -> None even with a matching token_sha


def test_spiffe_identity_is_well_formed():
    assert O.spiffe_id("org-a", "a1") == "spiffe://cyberware/org-a/a1"
    assert O.authorize("tok-A", _reg())["spiffe"] == "spiffe://cyberware/org-a/a1"


def test_org_isolation_matrix_only_same_org_allowed():
    assert O.can_access("org-a", "org-a") is True
    assert O.can_access("org-b", "org-b") is True
    assert O.can_access("org-a", "org-b") is False    # every cross-org cell refused
    assert O.can_access("org-b", "org-a") is False


def test_per_org_record_roots_are_distinct():
    base = "/srv/govd"
    assert O.record_root_for(base, "org-a") != O.record_root_for(base, "org-b")
    assert O.record_root_for(base, "org-a") == "/srv/govd/org/org-a"


def test_selftest_ok():
    assert O.orgs_selftest()["ok"] is True
