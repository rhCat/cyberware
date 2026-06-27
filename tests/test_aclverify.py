#!/usr/bin/env python3
"""tests/test_aclverify.py — ACL M1 attestation verifier (verify_acl_attestation) + the grant-body binding,
AND the M2 token-possession proof (mint_token_proof / verify_token_proof). This is the SINGLE ratchet slice
for infra/exec/aclverify.py — both verify surfaces are pinned here. The exod integration (3-way dual-control +
step-1b re-enforcement) is pinned in test_exod_acl.py.
"""
from __future__ import annotations
import base64

from cryptography.hazmat.primitives import serialization as _s

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


def test_malformed_window_fails_closed():
    # a signed attestation whose nbf/exp is not an int -> (False, malformed_window): kills the or-branch + the
    # False-literal return. Sign a hand-built body so the window is malformed but the signature is valid.
    body = {"pid": "p", "token_sha": "s", "acl_sha": principals.acl_sha("p", "s", ACL),
            "skills": ACL["skills"], "perks": ACL["perks"], "max_tier": ACL["max_tier"], "secrets": ACL["secrets"],
            "nbf": "soon", "exp": 5000, "attestation_id": "a"}
    env = sign.sign(body, OP, payload_type=TYPE)
    assert aclverify.verify_acl_attestation(OP_PUB, env, now=1500) == (False, "malformed_window")


def test_skew_window_boundaries():
    # exercise the +/- DEFAULT_SKEW (60) boundaries so the skew-sign mutants die: a `now` just inside the
    # window verifies; just outside is not_yet_valid / expired (nbf=1000, exp=1100).
    att = _att(now=1000, ttl=100)
    assert aclverify.verify_acl_attestation(OP_PUB, att, now=945)[0] is True          # just inside nbf-skew (940)
    assert aclverify.verify_acl_attestation(OP_PUB, att, now=935) == (False, "not_yet_valid")   # just outside
    assert aclverify.verify_acl_attestation(OP_PUB, att, now=1155)[0] is True         # just inside exp+skew (1160)
    assert aclverify.verify_acl_attestation(OP_PUB, att, now=1165) == (False, "expired")        # just outside


def test_malformed_signed_payload_fails_closed_never_raises():
    # putrefactio ErrorPropagation finding (aclverify.py:20): a VALIDLY-SIGNED but non-JSON payload must fail
    # CLOSED (return), never raise — verify_acl_attestation is TOTAL. Sign raw non-JSON bytes directly to reach
    # the guard (the normal mint API only ever emits JSON, so this path is not attacker-reachable).
    import base64
    raw = b"not-json-\x00\x01\xff"
    env = {"payload": base64.b64encode(raw).decode(), "payloadType": TYPE,
           "signatures": [{"keyid": "x", "sig": base64.b64encode(OP.sign(sign.pae(TYPE, raw))).decode()}]}
    assert aclverify.verify_acl_attestation(OP_PUB, env, now=1500) == (False, "malformed_body")


# --- M2: client token-possession proof (mint/verify_token_proof) ---------------------------------------------
PK = sign.keygen_from_seed(b"proof-key".ljust(32, b"0"))           # the client's INDEPENDENT proof key
PPUB = PK.public_key().public_bytes(_s.Encoding.Raw, _s.PublicFormat.Raw)
RUN, PSHA = "R1", "a" * 64


def _proof(key=PK, run=RUN, plan=PSHA, step="1", tok="sha-T"):
    return aclverify.mint_token_proof(key, run_id=run, plan_sha=plan, step=step, token_sha=tok)


def _v(env, ppub=PPUB, *, run=RUN, plan=PSHA, step="1", tok="sha-T", **kw):
    return aclverify.verify_token_proof(ppub, env, expect_run_id=run, expect_plan_sha=plan, expect_step=step,
                                        expect_token_sha=tok, **kw)


def test_proof_in_binding_verifies():
    assert _v(_proof()) == (True, "ok")
    assert _v(_proof(step="3"), step="3") == (True, "ok")          # step normalized both sides


def test_proof_misattribution_to_a_different_token_is_rejected():
    assert _v(_proof(tok="sha-T"), tok="sha-P") == (False, "proof_token_mismatch")


def test_proof_replay_onto_another_run_or_step_is_rejected():
    assert _v(_proof(), step="2") == (False, "proof_wrong_step")
    assert _v(_proof(), run="R2") == (False, "proof_wrong_step")
    assert _v(_proof(), plan="b" * 64) == (False, "proof_wrong_step")


def test_proof_degenerate_pubkey_a_node_held_key_cannot_self_prove():
    assert _v(_proof(), banned_pubkeys={PPUB}) == (False, "proof_degenerate_pubkey")


def test_proof_single_use_per_token_run_step():
    nc = grantverify.NonceCache()
    assert _v(_proof(), nonce_cache=nc) == (True, "ok")
    assert _v(_proof(), nonce_cache=nc) == (False, "proof_replay")       # same (token,run,step) -> spent
    assert _v(_proof(step="2"), step="2", nonce_cache=nc) == (True, "ok")   # a different step is independent


def test_proof_forged_or_wrong_key_signature_rejected():
    other = sign.keygen_from_seed(b"forger".ljust(32, b"0"))
    assert _v(_proof(key=other)) == (False, "proof_bad_signature")


def test_proof_wrong_type_bad_pubkey_and_malformed_fail_closed():
    grant_typed = sign.sign({"run_id": RUN, "plan_sha": PSHA, "step": "1", "token_sha": "sha-T"}, PK,
                            payload_type=aclverify.ACL_ATTESTATION_TYPE)
    assert _v(grant_typed) == (False, "proof_wrong_type")
    assert aclverify.verify_token_proof(b"\x00" * 10, _proof(), expect_run_id=RUN, expect_plan_sha=PSHA,
                                        expect_step="1", expect_token_sha="sha-T") == (False, "proof_bad_pubkey")
    raw = b"not-json-\x00\xff"
    env = {"payload": base64.b64encode(raw).decode(), "payloadType": aclverify.TOKEN_PROOF_TYPE,
           "signatures": [{"keyid": "x", "sig": base64.b64encode(PK.sign(sign.pae(aclverify.TOKEN_PROOF_TYPE, raw))).decode()}]}
    assert _v(env) == (False, "proof_malformed_body")
