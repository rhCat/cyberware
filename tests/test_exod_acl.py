#!/usr/bin/env python3
"""tests/test_exod_acl.py — ACL M1, exod side: three-way dual-control + the off-node re-enforcement
(`_acl_check`). exod independently re-derives the acl_sha (inside verify_acl_attestation), JOINs it against
the grant, and re-runs the SAME acl_allows on the grant's claim — trusting govd's grant for nothing about the
ceiling. The audit-vs-refuse decision lives in run_step; here we pin the deny-reason core directly.
"""
from __future__ import annotations
import pytest

from infra.cwp import sign
from infra.exec.exod import Exod
from infra.govern import issue, principals

GRANT = sign.keygen_from_seed(b"grant-key".ljust(32, b"0"))
EXODK = sign.keygen_from_seed(b"exod-key".ljust(32, b"0"))
OP = sign.keygen_from_seed(b"acl-issuer".ljust(32, b"0"))
# max_tier 'community' = the permissive ceiling (admits any declared tier incl. the undeclared None->community
# fail-safe); these tests isolate the skill/perk/join/signature paths — the tier ceiling is pinned in
# infra/govern/principals.py::principals_selftest.
ACL = {"skills": ["cws-fs"], "perks": {"cws-fs": ["read"]}, "max_tier": "community", "secrets": False}


def _exod(acl_pub=OP.public_key(), strict=False):
    return Exod(EXODK, grant_issuer_pub=GRANT.public_key(), acl_issuer_pub=acl_pub, acl_strict=strict,
                runner=lambda *a, **k: None)            # the runner is never touched by _acl_check


def _att(acl=ACL, pid="agent-1", tok="sha-abc", now=1000, ttl=3600):
    return issue.mint_attestation(OP, pid=pid, token_sha=tok, acl=acl, nbf=now, exp=now + ttl, attestation_id="att-1")


def _gbody(skill="cws-fs", perk="read", tok="sha-abc", pid="agent-1", acl=ACL, **over):
    gb = {"acl_sha": principals.acl_sha(pid, tok, acl), "skill": skill, "perk": perk,
          "sandbox_tier": None, "destructive": False, "credentials": []}
    gb.update(over)
    return gb


def test_three_way_dual_control_rejects_a_shared_key():
    with pytest.raises(ValueError):
        Exod(EXODK, grant_issuer_pub=GRANT.public_key(), acl_issuer_pub=GRANT.public_key())   # acl == grant
    with pytest.raises(ValueError):
        Exod(EXODK, grant_issuer_pub=GRANT.public_key(), acl_issuer_pub=EXODK.public_key())   # acl == exod
    Exod(EXODK, grant_issuer_pub=GRANT.public_key(), acl_issuer_pub=OP.public_key())          # 3 distinct -> ok


def test_in_scope_attestation_passes():
    assert _exod()._acl_check({"attestation": _att()}, _gbody(), now=1500) is None


def test_missing_attestation_on_an_acl_grant():
    assert _exod()._acl_check({}, _gbody(), now=1500) == "attestation_missing"


def test_grant_claim_outside_the_attested_acl_is_refused():
    # the grant claims cws-fs/write but the operator only attested read — exod re-runs acl_allows and denies
    assert _exod()._acl_check({"attestation": _att()}, _gbody(perk="write"), now=1500) == "acl_perk_denied"


def test_grant_acl_sha_must_join_the_attestation():
    gb = _gbody()
    gb["acl_sha"] = "00" * 32                           # the grant's digest no longer matches the attestation
    assert _exod()._acl_check({"attestation": _att()}, gb, now=1500) == "acl_join_mismatch"


def test_forged_attestation_rejected():
    other = sign.keygen_from_seed(b"forger".ljust(32, b"0"))
    forged = issue.mint_attestation(other, pid="agent-1", token_sha="sha-abc", acl=ACL, nbf=1000, exp=5000,
                                    attestation_id="att-1")
    assert _exod()._acl_check({"attestation": forged}, _gbody(), now=1500) == "bad_signature"


def test_legacy_unscoped_grant_passes_but_strict_refuses():
    legacy = {"skill": "x", "perk": "y", "capabilities": ["run"]}   # no acl_sha
    assert _exod()._acl_check({}, legacy, now=1500) is None
    assert _exod(strict=True)._acl_check({}, legacy, now=1500) == "unscoped_grant"


def test_acl_grant_without_a_pinned_issuer_is_unverifiable():
    no_pub = Exod(EXODK, grant_issuer_pub=GRANT.public_key(), runner=lambda *a, **k: None)
    assert no_pub._acl_check({"attestation": _att()}, _gbody(), now=1500) == "no_issuer_pinned"


def test_m2_token_proof_required_and_misattribution_refused():
    import base64
    from cryptography.hazmat.primitives import serialization as _s
    from infra.exec import aclverify
    pk = sign.keygen_from_seed(b"client-proof".ljust(32, b"0"))    # the actor's INDEPENDENT proof key
    ppub_b64 = base64.b64encode(pk.public_key().public_bytes(_s.Encoding.Raw, _s.PublicFormat.Raw)).decode()
    att = issue.mint_attestation(OP, pid="agent-1", token_sha="sha-abc", acl=ACL, nbf=1000, exp=2000,
                                 attestation_id="att-1", proof_pubkey=ppub_b64)
    gb = {**_gbody(), "run_id": "R1", "plan_sha": "a" * 64}
    e = _exod()                                                    # acl-issuer pinned, strict

    def chk(proof):
        req = {"attestation": att, "step": "1"}
        if proof is not None:
            req["token_proof"] = proof
        return e._acl_check(req, gb, now=1500)

    good = aclverify.mint_token_proof(pk, run_id="R1", plan_sha="a" * 64, step="1", token_sha="sha-abc")
    assert chk(good) is None                                       # the actor's valid proof -> allowed
    assert chk(None) == "proof_missing"                           # attestation binds a proof key, none presented
    # MISATTRIBUTION: a compromised govd relays this attestation but holds only a DIFFERENT actor's proof
    # (signed by a key != the attested proof_pubkey) -> the signature cannot satisfy the attested key.
    other = sign.keygen_from_seed(b"other-actor".ljust(32, b"0"))
    relayed = aclverify.mint_token_proof(other, run_id="R1", plan_sha="a" * 64, step="1", token_sha="sha-abc")
    assert chk(relayed) == "proof_bad_signature"


def test_m2_no_proof_required_when_attestation_omits_proof_pubkey():
    att = issue.mint_attestation(OP, pid="agent-1", token_sha="sha-abc", acl=ACL, nbf=1000, exp=2000, attestation_id="a")
    gb = {**_gbody(), "run_id": "R1", "plan_sha": "a" * 64}
    assert _exod()._acl_check({"attestation": att, "step": "1"}, gb, now=1500) is None   # M1-only back-compat
