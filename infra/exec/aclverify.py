#!/usr/bin/env python3
# infra/exec/aclverify.py: the operator-ACL-attestation VERIFICATION surface (ACL M1), a prose-clean
# executable core mirrored on grantverify.py. exod calls it to re-enforce each actor's ACL ceiling off-node
# under three-way dual-control, so a compromised govd node cannot WIDEN a token beyond what the operator
# attested. Comments here carry NO space-anchored operator tokens, so every surviving mutant is a real,
# test-killable comparison.
from __future__ import annotations
import base64
import json

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
            "max_tier": body.get("max_tier"), "secrets": body.get("secrets")}


def verify_acl_attestation(acl_issuer_pub, envelope, *, now, expect_acl_sha=None, skew=DEFAULT_SKEW):
    # verify an operator ACL attestation OFFLINE. Returns (ok, reason). Signature is checked FIRST (a forged
    # attestation never reaches the join). acl_sha is RE-DERIVED from the body's own fields (pid, token_sha,
    # skills, perks, max_tier, secrets) and never trusted on faith: it must match the body's stated acl_sha,
    # AND, when the caller supplies one, the grant's acl_sha (the join that ties grant to attestation).
    if not sign.verify(envelope, acl_issuer_pub):
        return False, "bad_signature"
    if envelope.get("payloadType") != ACL_ATTESTATION_TYPE:
        return False, "wrong_type"
    body = attestation_body(envelope)
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
