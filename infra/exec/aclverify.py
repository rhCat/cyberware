#!/usr/bin/env python3
# infra/exec/aclverify.py: the operator-ACL-attestation VERIFICATION surface (ACL M1), a prose-clean
# executable core mirrored on grantverify.py. exod calls it to re-enforce each actor's ACL ceiling off-node
# under three-way dual-control, so a compromised govd node cannot WIDEN a token beyond what the operator
# attested. Comments here carry NO space-anchored operator tokens, so every surviving mutant is a real,
# test-killable comparison.
from __future__ import annotations
import base64
import json

from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey

from infra.cwp import sign
from infra.govern import principals    # the SAME pure decision core govern() uses; exod re-runs acl_allows

ACL_ATTESTATION_TYPE = "application/vnd.cyberware.acl-attestation+json"
DEFAULT_SKEW = 60


def attestation_body(envelope):
    # the decoded attestation claim; does NOT verify the signature
    return json.loads(base64.b64decode(envelope["payload"]))


def attested_acl(body):
    # the actor ACL block reconstructed from the attestation's own fields (the ceiling exod re-enforces)
    return {"skills": body.get("skills"), "perks": body.get("perks"),
            "max_tier": body.get("max_tier"), "secrets": body.get("secrets"), "params": body.get("params"),
            "cargo": body.get("cargo")}


def verify_acl_attestation(acl_issuer_pub, envelope, *, now, expect_acl_sha=None, skew=DEFAULT_SKEW):
    # verify an operator ACL attestation OFFLINE. Returns (ok, reason). Signature is checked FIRST (a forged
    # attestation never reaches the join). acl_sha is RE-DERIVED from the body's own fields (pid, token_sha,
    # skills, perks, max_tier, secrets), never trusted on faith: it must match the body's stated acl_sha,
    # AND, when the caller supplies one, the grant's acl_sha (the join that ties grant to attestation).
    if not sign.verify(envelope, acl_issuer_pub):
        return False, "bad_signature"
    if envelope.get("payloadType") != ACL_ATTESTATION_TYPE:
        return False, "wrong_type"
    try:                                                     # a signed-but-unparseable payload fails CLOSED:
        body = attestation_body(envelope)                    # verify_acl_attestation is TOTAL, it never raises
    except Exception:
        return False, "malformed_body"
    nbf, exp = body.get("nbf"), body.get("exp")
    if not isinstance(nbf, int) or not isinstance(exp, int):
        return False, "malformed_window"
    if now < nbf - skew:
        return False, "not_yet_valid"
    if now > exp + skew:
        return False, "expired"
    derived = principals.acl_sha(body.get("pid"), body.get("token_sha"), attested_acl(body))
    if body.get("acl_sha") != derived:
        return False, "acl_sha_mismatch"
    if expect_acl_sha is not None and expect_acl_sha != derived:
        return False, "acl_join_mismatch"
    return True, "ok"


# --- M2: the CLIENT token-possession proof — binds a run to the token that ACTUALLY holds it -----------------
# The operator binds a client's INDEPENDENT proof public key into the attestation (proof_pubkey). The client
# signs a per-step proof with the matching private key. exod verifies it against the attested proof_pubkey, so a
# compromised govd relaying a DIFFERENT, more-privileged token's attestation cannot satisfy it (it does not hold
# that token's proof key). This closes the run<->token misattribution residual M1 left open.
TOKEN_PROOF_TYPE = "application/vnd.cyberware.token-proof+json"


def mint_token_proof(proof_key, *, run_id, plan_sha, step, token_sha):
    """The client signs a per-step token-possession proof with its proof PRIVATE key (whose public half the
    operator bound into the attestation). Binds (run_id, plan_sha, step, token_sha) — values the client knows at
    step-send time, with NO dependence on govd's grant nonce (minted inside govd, after the step arrives)."""
    body = {"run_id": run_id, "plan_sha": plan_sha, "step": str(step), "token_sha": token_sha}
    return sign.sign(body, proof_key, payload_type=TOKEN_PROOF_TYPE)


def token_proof_body(envelope):
    return json.loads(base64.b64decode(envelope["payload"]))


def verify_token_proof(proof_pubkey_raw, envelope, *, expect_run_id, expect_plan_sha, expect_step,
                       expect_token_sha, banned_pubkeys=(), nonce_cache=None):
    # (ok, reason). proof_pubkey_raw is the raw-32 proof key the OPERATOR bound into the attestation. The
    # DEGENERATE guard runs FIRST: a proof key equal to one the node controls (grant-issuer/acl-issuer/exod)
    # is rejected, so a compromised govd holding one of those cannot mint a self-satisfying proof. The signature
    # is checked against THAT operator-bound key; the proof must bind this run/plan/step to the attestation's
    # token_sha; single-use per (token_sha, run, step) defeats a replay onto a different run/step.
    if proof_pubkey_raw in banned_pubkeys:
        return False, "proof_degenerate_pubkey"
    try:
        pub = Ed25519PublicKey.from_public_bytes(proof_pubkey_raw)
    except Exception:
        return False, "proof_bad_pubkey"
    if not sign.verify(envelope, pub):
        return False, "proof_bad_signature"
    if envelope.get("payloadType") != TOKEN_PROOF_TYPE:
        return False, "proof_wrong_type"
    try:
        b = token_proof_body(envelope)
    except Exception:
        return False, "proof_malformed_body"
    if b.get("token_sha") != expect_token_sha:
        return False, "proof_token_mismatch"
    if (b.get("run_id") != expect_run_id or b.get("plan_sha") != expect_plan_sha
            or b.get("step") != str(expect_step)):
        return False, "proof_wrong_step"
    if nonce_cache is not None and not nonce_cache.spend(expect_token_sha, f"{expect_run_id}:{expect_step}"):
        return False, "proof_replay"
    return True, "ok"
