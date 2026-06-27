#!/usr/bin/env python3
"""tests/test_aclverify.py — ACL M1 foundational primitives: the operator attestation minter (issue.py),
its prose-clean verifier (aclverify.py), and the grant-body binding (grants.py). The exod integration (the
three-way dual-control + step-1b re-enforcement) is pinned separately once it lands.
"""
from __future__ import annotations

from infra.cwp import sign
from infra.exec import aclverify, grants, grantverify
from infra.govern import issue, principals

OP = sign.keygen_from_seed(b"acl-issuer".ljust(32, b"0"))      # the operator ACL-issuer key (deterministic, test-only)
OP_PUB = OP.public_key()
OTHER = sign.keygen_from_seed(b"other-key".ljust(32, b"0"))    # a different key (forgery probe)

ACL = {"skills": ["cws-fs"], "perks": {"cws-fs": ["read"]}, "max_tier": "verified", "secrets": False}
TYPE = aclverify.ACL_ATTESTATION_TYPE


def _att(now=1000, ttl=3600, acl=ACL, pid="agent-1", tok="sha-abc"):
    return issue.mint_attestation(OP, pid=pid, token_sha=tok, acl=acl, nbf=now, exp=now + ttl, attestation_id="att-1")


def test_roundtrip_verifies_and_rederives_acl_sha():
    env = _att()
    ok, why = aclverify.verify_acl_attestation(OP_PUB, env, now=1500)
    assert ok and why == "ok"
    # the JOIN: a matching grant acl_sha (recomputed from the live registry fields) passes
    live = principals.acl_sha("agent-1", "sha-abc", ACL)
    ok2, why2 = aclverify.verify_acl_attestation(OP_PUB, env, now=1500, expect_acl_sha=live)
    assert ok2 and why2 == "ok"


def test_forged_signature_rejected_first():
    ok, why = aclverify.verify_acl_attestation(OTHER.public_key(), _att(), now=1500)
    assert not ok and why == "bad_signature"


def test_inconsistent_acl_sha_is_rejected():
    # a VALIDLY-signed body whose stated acl_sha does not match its own fields -> re-derive catches it
    body = {"pid": "agent-1", "token_sha": "sha-abc", "acl_sha": "de" * 32,
            "skills": ["cws-fs"], "perks": {"cws-fs": ["read"]}, "max_tier": "verified", "secrets": False,
            "nbf": 1000, "exp": 5000, "attestation_id": "att-x"}
    env = sign.sign(body, OP, payload_type=TYPE)
    ok, why = aclverify.verify_acl_attestation(OP_PUB, env, now=1500)
    assert not ok and why == "acl_sha_mismatch"


def test_join_mismatch_when_grant_acl_sha_differs():
    ok, why = aclverify.verify_acl_attestation(OP_PUB, _att(), now=1500, expect_acl_sha="00" * 32)
    assert not ok and why == "acl_join_mismatch"


def test_expired_and_not_yet_valid():
    expired = aclverify.verify_acl_attestation(OP_PUB, _att(now=1000, ttl=100), now=2000)   # 2000 > 1100 + skew
    assert expired == (False, "expired")
    early = aclverify.verify_acl_attestation(OP_PUB, _att(now=1000, ttl=100), now=500)       # 500 < 1000 - skew
    assert early == (False, "not_yet_valid")


def test_wrong_payload_type_rejected():
    body = {"pid": "p", "token_sha": "s", "acl_sha": principals.acl_sha("p", "s", ACL),
            "skills": ACL["skills"], "perks": ACL["perks"], "max_tier": ACL["max_tier"], "secrets": ACL["secrets"],
            "nbf": 1000, "exp": 5000, "attestation_id": "a"}
    env = sign.sign(body, OP, payload_type=grantverify.GRANT_TYPE)   # a grant, not an attestation
    ok, why = aclverify.verify_acl_attestation(OP_PUB, env, now=1500)
    assert not ok and why == "wrong_type"


def test_grant_body_binds_acl_fields_only_when_set():
    g = grants.mint_grant(OP, run_id="r", plan_sha="a" * 64, nbf=1000, exp=5000, nonce="n1",
                          acl_sha="ab" * 32, skill="cws-fs", perk="read", destructive=False)
    gb = grantverify.grant_body(g)
    assert gb["acl_sha"] == "ab" * 32 and gb["skill"] == "cws-fs" and gb["perk"] == "read" and gb["destructive"] is False
    # a legacy (pre-ACL) grant body stays byte-identical: none of the new keys appear
    legacy = grantverify.grant_body(grants.mint_grant(OP, run_id="r", plan_sha="a" * 64, nbf=1, exp=9, nonce="n2"))
    assert not any(k in legacy for k in ("acl_sha", "skill", "perk", "destructive"))


def test_attestation_id_and_proof_pubkey_carried():
    env = issue.mint_attestation(OP, pid="p", token_sha="s", acl=ACL, nbf=1, exp=9,
                                 attestation_id="att-z", proof_pubkey="cHJvb2Y=")
    body = aclverify.attestation_body(env)
    assert body["attestation_id"] == "att-z" and body["proof_pubkey"] == "cHJvb2Y="
