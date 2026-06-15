#!/usr/bin/env python3
# infra/exec/exodverify.py: the step-result VERIFICATION surface (P2-T02), extracted from exod.py as a
# prose-clean executable core. exod.py re-exports these names (single source of truth); the R3 mutation
# gate (cws-mutate / mut-exod-verify) mutates this file. Comments here carry NO space-anchored operator
# tokens, so every surviving mutant is a real, test-killable comparison.
#
# A step-result is the ONLY status the ledger trusts. exod signs it with its own principal key; this surface
# decides whether a presented result actually came over exod's channel. A status that does not verify is a
# forged self-report and is refused — the spine no longer believes the executor about its own exit code.
from __future__ import annotations
import base64
import json

from cryptography.hazmat.primitives import serialization

from infra.cwp import sign
from infra.exec.grantverify import NonceCache  # the issuer-scoped single-use replay guard (single source)

STEP_RESULT_TYPE = "application/vnd.cyberware.step-result+json"
_STATUSES = ("ok", "error", "refused")


def _principal(public_key):
    # the keyid of the principal whose signature this result carries; scopes replay to that principal
    raw = public_key.public_bytes(serialization.Encoding.Raw, serialization.PublicFormat.Raw)
    return sign.keyid(raw)


def result_body(envelope):
    # the decoded step-result claim; does NOT verify the signature
    return json.loads(base64.b64decode(envelope["payload"]))


def verify_step_result(public_key, envelope, *, expect_run_id=None, expect_plan_sha=None, nonce_cache=None):
    # verify a step-result came over exod's channel. Returns (ok, reason). The signature is checked FIRST: a
    # status not signed by exod (a forged self-report) is refused as "forged_status" before any field is
    # read, and a fresh nonce is spent only after every other check passes.
    if not sign.verify(envelope, public_key):
        return False, "forged_status"
    if envelope.get("payloadType") != STEP_RESULT_TYPE:
        return False, "wrong_type"
    body = result_body(envelope)
    if expect_run_id is not None and body.get("run_id") != expect_run_id:
        return False, "wrong_run"
    if expect_plan_sha is not None and body.get("plan_sha") != expect_plan_sha:
        return False, "wrong_plan"
    if body.get("status") not in _STATUSES:
        return False, "malformed_status"
    nonce = body.get("nonce")
    if not (isinstance(nonce, str) and nonce):
        return False, "malformed_nonce"
    if nonce_cache is not None and not nonce_cache.spend(_principal(public_key), nonce):
        return False, "replay"
    return True, "ok"
