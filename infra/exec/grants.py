#!/usr/bin/env python3
"""infra/exec/grants.py — Ed25519-DSSE signed capability grants (SV-3 spine, P2-T01).

A grant is the capability token govd issues and (later) the OS-isolated exod daemon verifies before a step
runs: a DSSE envelope over the canonical bytes of {run_id, plan_sha, snippet_shas, capabilities,
credentials, nbf, exp, nonce}. The VERIFICATION surface (offline signature check + ±60s skew window +
issuer-scoped replay cache, refusing bad_signature / wrong_type / malformed_window / not_yet_valid /
expired / malformed_nonce / replay) lives in grantverify.py — a prose-clean executable core that is the R3
mutation target (cws-mutate / mut-grant-verify) and the single source of truth. This module mints grants
and re-exports the verifier so callers keep one import site.

The crypto here is platform-agnostic; the KERNEL enforcement of the grant (the OS-isolated exod, P2-T02,
and the bwrap/seccomp sandbox, P2-T03) is Linux-only and lands later in the compute image.
"""
from __future__ import annotations

from infra.cwp import sign
from infra.exec.grantverify import (  # noqa: F401  (single source of truth for the verify surface)
    DEFAULT_SKEW, GRANT_TYPE, NonceCache, grant_body, verify_grant,
)


def mint_grant(private_key, *, run_id, plan_sha, nbf, exp, nonce,
               snippet_shas=None, capabilities=None, credentials=None):
    """Issue a signed grant (a DSSE envelope). The body is the value-free capability claim; the signature
    binds it so any holder can verify it offline. The nonce MUST be a non-empty string (the replay key)."""
    if not (isinstance(nonce, str) and nonce):
        raise ValueError("grant nonce must be a non-empty string")
    body = {"run_id": run_id, "plan_sha": plan_sha, "snippet_shas": snippet_shas or {},
            "capabilities": capabilities or [], "credentials": credentials or [],
            "nbf": int(nbf), "exp": int(exp), "nonce": nonce}
    return sign.sign(body, private_key, payload_type=GRANT_TYPE)
