#!/usr/bin/env python3
"""infra/govern/issue.py — the OPERATOR-side ACL attestation minter (ACL M1).

The operator who owns principals.json signs an actor->ACL attestation with the ACL-ISSUER key — a THIRD key,
distinct from every node's grant key and every exod key, whose private half lives OFF every body (offline /
HSM, the same custody root as principals.json). exod pins the operator's public half and, under three-way
dual-control (acl-issuer != grant-issuer != exod), re-enforces the actor's ACL ceiling so a COMPROMISED govd
node cannot WIDEN a token beyond what the operator attested. This tool is NEVER run by govd.

  # mint one attestation per non-trivial-ACL principal (exp in MINUTES-to-hours: it is the revocation bound)
  python3 -m infra.govern.issue mint --principals principals.json --pid agent-1 \
      --key acl-issuer.key --ttl 3600 --out agent-1.attestation.json

The attestation is value-free: canonical skill/perk ids + tier labels + the sha-keyed identity only, NEVER a
token value. acl_sha is recomputed here the SAME way govd recomputes it at allow-time (principals.acl_sha), so
exod's re-derive-and-join check holds.
"""
from __future__ import annotations
import argparse
import json
import os
import sys
import time
import uuid

from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

from infra.cwp import sign
from infra.exec.aclverify import ACL_ATTESTATION_TYPE
from infra.govern import principals


def mint_attestation(operator_key, *, pid, token_sha, acl, nbf, exp, attestation_id, proof_pubkey=None):
    """A signed operator ACL attestation (DSSE envelope) binding {pid, token_sha, acl}. acl_sha is recomputed
    from the live acl fields via principals.acl_sha (pid+token_sha folded in), so exod can re-derive + join it.
    `proof_pubkey` (raw32 base64 of the client's INDEPENDENT proof public key) is carried for M2; omit at M1."""
    a = acl or {}
    body = {"pid": pid, "token_sha": token_sha,
            "acl_sha": principals.acl_sha(pid, token_sha, a),
            "skills": a.get("skills"), "perks": a.get("perks"),
            "max_tier": a.get("max_tier"), "secrets": a.get("secrets"),
            "nbf": int(nbf), "exp": int(exp), "attestation_id": attestation_id}
    if proof_pubkey is not None:
        body["proof_pubkey"] = proof_pubkey
    return sign.sign(body, operator_key, payload_type=ACL_ATTESTATION_TYPE)


def _load_operator_key(path: str) -> Ed25519PrivateKey:
    """Load the ACL-issuer private key — raw 32 bytes (the body deploy's keygen convention)."""
    raw = open(path, "rb").read()
    if len(raw) != 32:
        raise ValueError(f"acl-issuer key must be 32 raw bytes (got {len(raw)})")
    return Ed25519PrivateKey.from_private_bytes(raw)


def _cmd_mint(a) -> int:
    reg = principals.load_principals(a.principals)
    spec = reg.get(a.pid)
    if not isinstance(spec, dict):
        print(f"issue: principal {a.pid!r} not found in {a.principals}", file=sys.stderr)
        return 2
    acl = spec.get("acl")
    if not isinstance(acl, dict):
        print(f"issue: principal {a.pid!r} has no acl block (nothing to attest)", file=sys.stderr)
        return 2
    now = int(a.now if a.now is not None else time.time())
    env = mint_attestation(_load_operator_key(a.key), pid=a.pid, token_sha=spec.get("token_sha"), acl=acl,
                           nbf=now, exp=now + int(a.ttl), attestation_id=a.id or ("att-" + uuid.uuid4().hex),
                           proof_pubkey=a.proof_pubkey)
    out = json.dumps(env, separators=(",", ":"))
    if a.out:
        with open(a.out, "w") as f:
            f.write(out)
        os.chmod(a.out, 0o644)                          # an attestation is signed + public — no secret to guard
        print(f"issue: wrote attestation for {a.pid} (exp in {a.ttl}s) -> {a.out}")
    else:
        print(out)
    return 0


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="operator-side ACL attestation minter (never run by govd)")
    sub = ap.add_subparsers(dest="cmd", required=True)
    m = sub.add_parser("mint", help="sign an actor->ACL attestation from principals.json")
    m.add_argument("--principals", required=True, help="path to principals.json")
    m.add_argument("--pid", required=True, help="the principal id to attest")
    m.add_argument("--key", required=True, help="the ACL-issuer private key (raw 32 bytes; off-body)")
    m.add_argument("--ttl", type=int, default=3600, help="lifetime in seconds (the revocation bound; keep short)")
    m.add_argument("--id", default=None, help="attestation_id (default: a fresh ulid-like id)")
    m.add_argument("--proof-pubkey", dest="proof_pubkey", default=None, help="M2: client proof public key (raw32 b64)")
    m.add_argument("--now", type=int, default=None, help="override the clock (testing)")
    m.add_argument("--out", default=None, help="write the attestation here (default: stdout)")
    m.set_defaults(fn=_cmd_mint)
    a = ap.parse_args(argv)
    return a.fn(a)


if __name__ == "__main__":
    sys.exit(main())
