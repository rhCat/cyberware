#!/usr/bin/env python3
"""infra/exec/grants.py — Ed25519-DSSE signed capability grants (SV-3 spine, P2-T01).

A grant is the capability token govd issues and (later) the exod execution daemon verifies before a step
runs: a DSSE envelope over the canonical bytes of {run_id, plan_sha, snippet_shas, capabilities,
credentials, nbf, exp, nonce}. Verification is OFFLINE — only the issuer's public key + the envelope, no
network — and rejects four ways:

  * bad signature        — the grant was forged or tampered (DSSE/Ed25519 over the canonical PAE),
  * wrong type           — the envelope is not a grant,
  * outside the window   — now < nbf-skew (not yet valid) or now > exp+skew (expired); ±60s skew honored,
  * replay               — the nonce was already spent (a monotonic, single-use nonce cache).

This is the first brick of the kernel-enforced boundary: the token whose authenticity the OS-isolated exod
(P2-T02) and sandbox (P2-T03) will enforce. The crypto here is platform-agnostic; the kernel enforcement is
not (Linux bwrap/seccomp), so it lands later in the compute image.
"""
from __future__ import annotations
import base64
import json

from infra.cwp import sign

GRANT_TYPE = "application/vnd.cyberware.grant+json"
DEFAULT_SKEW = 60


def mint_grant(private_key, *, run_id, plan_sha, nbf, exp, nonce,
               snippet_shas=None, capabilities=None, credentials=None):
    """Issue a signed grant (a DSSE envelope). The body is the value-free capability claim; the signature
    binds it so any holder can verify it offline."""
    body = {"run_id": run_id, "plan_sha": plan_sha, "snippet_shas": snippet_shas or {},
            "capabilities": capabilities or [], "credentials": credentials or [],
            "nbf": int(nbf), "exp": int(exp), "nonce": nonce}
    return sign.sign(body, private_key, payload_type=GRANT_TYPE)


def grant_body(envelope):
    """The decoded grant claim (the canonical JSON payload) — does NOT verify the signature."""
    return json.loads(base64.b64decode(envelope["payload"]))


class NonceCache:
    """A monotonic single-use nonce cache — the replay guard. A nonce verifies at most once."""
    def __init__(self):
        self._seen = set()

    def spend(self, nonce):
        """Return True if `nonce` is fresh (and record it); False if it was already spent."""
        if nonce in self._seen:
            return False
        self._seen.add(nonce)
        return True


def verify_grant(public_key, envelope, *, now, nonce_cache=None, skew=DEFAULT_SKEW):
    """Verify a grant OFFLINE. Returns (ok, reason). reason is 'ok' on success, else the refusal class.
    The signature is checked FIRST (a forged grant never reaches the time/replay checks). When a
    nonce_cache is supplied, a replayed nonce is refused (and a fresh one is spent only after every other
    check passes, so a refused grant never burns its nonce)."""
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
    if nonce_cache is not None and not nonce_cache.spend(body.get("nonce")):
        return False, "replay"
    return True, "ok"
