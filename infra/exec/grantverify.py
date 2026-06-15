#!/usr/bin/env python3
# infra/exec/grantverify.py: the grant-VERIFICATION surface (P2-T01), extracted from grants.py as a
# prose-clean executable core. grants.py re-exports these names (single source of truth); the R3 mutation
# gate (cws-mutate / mut-grant-verify) mutates this file. Comments here carry NO space-anchored operator
# tokens, so every surviving mutant is a real, test-killable comparison.
from __future__ import annotations
import base64
import json

from cryptography.hazmat.primitives import serialization

from infra.cwp import sign

GRANT_TYPE = "application/vnd.cyberware.grant+json"
DEFAULT_SKEW = 60


def _issuer(public_key):
    # the keyid of the VERIFYING key (the issuer the signature proves), used to scope replay
    raw = public_key.public_bytes(serialization.Encoding.Raw, serialization.PublicFormat.Raw)
    return sign.keyid(raw)


def grant_body(envelope):
    # the decoded grant claim; does NOT verify the signature
    return json.loads(base64.b64decode(envelope["payload"]))


class NonceCache:
    # a monotonic single-use replay guard: an (issuer, nonce) pair verifies at most once. Scoping by issuer
    # keeps one issuer from spending another's nonces in a shared cache.
    def __init__(self):
        self._seen = set()

    def spend(self, issuer, nonce):
        key = (issuer, nonce)
        if key in self._seen:
            return False
        self._seen.add(key)
        return True


def verify_grant(public_key, envelope, *, now, nonce_cache=None, skew=DEFAULT_SKEW,
                 expect_run_id=None, expect_plan_sha=None):
    # verify a grant OFFLINE. Returns (ok, reason). Signature is checked FIRST (a forged grant never reaches
    # the time/replay checks); the grant's bound run_id/plan_sha must match the caller's expectation when one
    # is supplied (a grant minted for one run never authorizes another); a fresh nonce is spent only after
    # every other check passes (a grant that fails to match its run is NOT consumed).
    if not sign.verify(envelope, public_key):
        return False, "bad_signature"
    if envelope.get("payloadType") != GRANT_TYPE:
        return False, "wrong_type"
    body = grant_body(envelope)
    nbf, exp = body.get("nbf"), body.get("exp")
    if not isinstance(nbf, int) or not isinstance(exp, int):
        return False, "malformed_window"
    if now < nbf - skew:
        return False, "not_yet_valid"
    if now > exp + skew:
        return False, "expired"
    if expect_run_id is not None and body.get("run_id") != expect_run_id:
        return False, "wrong_run"
    if expect_plan_sha is not None and body.get("plan_sha") != expect_plan_sha:
        return False, "wrong_plan"
    nonce = body.get("nonce")
    if not (isinstance(nonce, str) and nonce):
        return False, "malformed_nonce"
    if nonce_cache is not None and not nonce_cache.spend(_issuer(public_key), nonce):
        return False, "replay"
    return True, "ok"
