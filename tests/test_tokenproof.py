#!/usr/bin/env python3
"""tests/test_tokenproof.py — ACL M2: the client token-possession proof (aclverify.mint/verify_token_proof).
The proof binds a run/step to the token whose proof key the operator attested, so a compromised govd relaying a
DIFFERENT token's attestation cannot satisfy it — the run<->token misattribution close M1 deferred.
"""
from __future__ import annotations

from cryptography.hazmat.primitives import serialization as _s

from infra.cwp import sign
from infra.exec import aclverify
from infra.exec.grantverify import NonceCache

PK = sign.keygen_from_seed(b"proof-key".ljust(32, b"0"))           # the client's INDEPENDENT proof key
PPUB = PK.public_key().public_bytes(_s.Encoding.Raw, _s.PublicFormat.Raw)
RUN, PSHA = "R1", "a" * 64


def _proof(key=PK, run=RUN, plan=PSHA, step="1", tok="sha-T"):
    return aclverify.mint_token_proof(key, run_id=run, plan_sha=plan, step=step, token_sha=tok)


def _v(env, ppub=PPUB, *, run=RUN, plan=PSHA, step="1", tok="sha-T", **kw):
    return aclverify.verify_token_proof(ppub, env, expect_run_id=run, expect_plan_sha=plan, expect_step=step,
                                        expect_token_sha=tok, **kw)


def test_in_binding_proof_verifies():
    assert _v(_proof()) == (True, "ok")
    assert _v(_proof(step="3"), step="3") == (True, "ok")          # step is normalized both sides


def test_misattribution_to_a_different_token_is_rejected():
    # a compromised govd relays this token-T proof while claiming token P -> the bound token_sha won't match
    assert _v(_proof(tok="sha-T"), tok="sha-P")[1] == "proof_token_mismatch"


def test_replay_onto_another_run_or_step_is_rejected():
    assert _v(_proof(), step="2")[1] == "proof_wrong_step"
    assert _v(_proof(), run="R2")[1] == "proof_wrong_step"


def test_degenerate_pubkey_a_node_held_key_cannot_self_prove():
    # if the attested proof_pubkey were a key the node controls (grant/acl-issuer/exod), reject before verifying
    assert _v(_proof(), banned_pubkeys={PPUB})[1] == "proof_degenerate_pubkey"


def test_single_use_per_token_run_step():
    nc = NonceCache()
    assert _v(_proof(), nonce_cache=nc)[0] is True
    assert _v(_proof(), nonce_cache=nc)[1] == "proof_replay"        # same (token, run, step) -> spent
    assert _v(_proof(step="2"), step="2", nonce_cache=nc)[0] is True   # a different step is independent


def test_forged_or_wrong_key_signature_rejected():
    other = sign.keygen_from_seed(b"forger".ljust(32, b"0"))
    assert _v(_proof(key=other))[1] == "proof_bad_signature"        # signed by a non-attested key


def test_wrong_type_and_malformed_fail_closed():
    grant_typed = sign.sign({"run_id": RUN, "plan_sha": PSHA, "step": "1", "token_sha": "sha-T"}, PK,
                            payload_type=aclverify.ACL_ATTESTATION_TYPE)
    assert _v(grant_typed)[1] == "proof_wrong_type"
    bad_pub = aclverify.verify_token_proof(b"\x00" * 10, _proof(), expect_run_id=RUN, expect_plan_sha=PSHA,
                                           expect_step="1", expect_token_sha="sha-T")
    assert bad_pub[1] == "proof_bad_pubkey"                         # a malformed proof_pubkey fails closed
