#!/usr/bin/env python3
"""sign.py — DSSE / Ed25519 signing over the canonical bytes (the CWP `sig` primitive; T02/T03).

A signature in cyberware is an Ed25519 signature over the DSSE Pre-Authentication Encoding (PAE) of a
message's JCS-canonical bytes (`infra/cwp/canonical.py`). Ed25519 is deterministic (RFC 8032), so the
same key over the same canonical payload yields the same signature in any conformant implementation —
the property the cross-language anchor (the Go verifier) checks.

  from infra.cwp import sign
  env = sign.sign(body_obj, private_key)        # → a DSSE envelope {payload, payloadType, signatures[]}
  sign.verify(env, public_key)                  # → True/False
  kid = sign.keyid(public_raw_bytes)            # the stable key-id carried in every signature + DSSE header

Key material rides the pyca/cryptography Ed25519 types; `keygen_from_seed` makes a deterministic key for
vectors/tests. Key custody (rotation, the offline root, PKCS#11) is `spec/keys.md` / the KeyStore seam.
"""
from __future__ import annotations
import base64
import hashlib

from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey, Ed25519PublicKey

from infra.cwp import canonical

PAYLOAD_TYPE = "application/cwp+json"


def _raw_pub(pub: Ed25519PublicKey) -> bytes:
    return pub.public_bytes(serialization.Encoding.Raw, serialization.PublicFormat.Raw)


def keyid(public_raw: bytes) -> str:
    """The stable key-id: a prefixed truncated sha256 of the raw public key (resolvable per spec/keys.md)."""
    return "ed25519:" + hashlib.sha256(public_raw).hexdigest()[:16]


def pae(payload_type: str, payload: bytes) -> bytes:
    """DSSE Pre-Authentication Encoding (what is actually signed) — binds the payload to its type."""
    pt = payload_type.encode()
    return b"DSSEv1 " + str(len(pt)).encode() + b" " + pt + b" " + str(len(payload)).encode() + b" " + payload


def sign(body, private_key: Ed25519PrivateKey, payload_type: str = PAYLOAD_TYPE) -> dict:
    """Sign a JSON value's canonical bytes; return a DSSE envelope. The payload is the canonical bytes,
    base64-encoded; the signature is over the PAE of those bytes."""
    payload = canonical.canonical_bytes(body)
    sig = private_key.sign(pae(payload_type, payload))
    kid = keyid(_raw_pub(private_key.public_key()))
    return {
        "payload": base64.b64encode(payload).decode(),
        "payloadType": payload_type,
        "signatures": [{"keyid": kid, "sig": base64.b64encode(sig).decode()}],
    }


def verify(envelope: dict, public_key: Ed25519PublicKey) -> bool:
    """True iff at least one signature in the envelope verifies against public_key over the PAE."""
    try:
        payload = base64.b64decode(envelope["payload"])
        message = pae(envelope["payloadType"], payload)
    except (KeyError, ValueError, TypeError):
        return False
    for s in envelope.get("signatures", []):
        try:
            public_key.verify(base64.b64decode(s["sig"]), message)
            return True
        except (InvalidSignature, ValueError, TypeError):
            continue
    return False


def keygen_from_seed(seed32: bytes) -> Ed25519PrivateKey:
    """A deterministic Ed25519 key from a 32-byte seed — for golden vectors + tests (never production)."""
    return Ed25519PrivateKey.from_private_bytes(seed32)


def public_raw(private_key: Ed25519PrivateKey) -> bytes:
    return _raw_pub(private_key.public_key())
