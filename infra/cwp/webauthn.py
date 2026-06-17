#!/usr/bin/env python3
"""infra/cwp/webauthn.py — WebAuthn approval for destructive grants (P3-T04, SV-4).

A destructive grant must carry a hardware-backed human approval, bound to the EXACT governed document. The
WebAuthn challenge is `sha256(JCS(doc))` — so an assertion approves one specific canonicalized doc and nothing
else. The authenticator (a roaming key / platform TPM) signs `authenticatorData || sha256(clientDataJSON)`
with its EdDSA (COSE alg -8) credential; we store the assertion + the COSE public key and **verify entirely
offline** — no live authenticator, no network — replaying the same checks a relying party would: the
clientData type + challenge + origin, the RP-ID hash, the User-Present and User-Verified flags, and the
signature. Any tamper (different doc, flipped signature, cleared UV bit, wrong origin) is refused, and a
destructive grant that lacks a verified approval does not proceed. Deleting the signature check makes a
tampered assertion verify — which the tests catch, so the check cannot be silently removed.
"""
from __future__ import annotations
import base64
import hashlib
import json
import struct

from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey, Ed25519PublicKey

from infra.cwp import canonical

_RAW = serialization.Encoding.Raw
_RAW_PUB = serialization.PublicFormat.Raw

FLAG_UP = 0x01                                                  # user present
FLAG_UV = 0x04                                                  # user verified
COSE_EDDSA = -8


def _b64url(b: bytes) -> str:
    return base64.urlsafe_b64encode(b).decode().rstrip("=")


def challenge_for(doc) -> bytes:
    """The approval is bound to the doc: the WebAuthn challenge is sha256 of the doc's canonical (JCS) bytes."""
    return hashlib.sha256(canonical.canonical_bytes(doc)).digest()


def _authenticator_data(rp_id: str, up: bool, uv: bool, sign_count: int = 1) -> bytes:
    flags = (FLAG_UP if up else 0) | (FLAG_UV if uv else 0)
    return hashlib.sha256(rp_id.encode()).digest() + bytes([flags]) + struct.pack(">I", sign_count)


def make_assertion(doc, priv: Ed25519PrivateKey, origin: str, rp_id: str,
                   up: bool = True, uv: bool = True) -> dict:
    """Produce a WebAuthn assertion over `doc` (a synthetic authenticator, for tests/drills). The real flow
    is identical — only the private key lives in hardware instead of here."""
    client_data = json.dumps({"type": "webauthn.get", "challenge": _b64url(challenge_for(doc)),
                              "origin": origin}, separators=(",", ":")).encode()
    auth_data = _authenticator_data(rp_id, up, uv)
    sig = priv.sign(auth_data + hashlib.sha256(client_data).digest())
    pub = priv.public_key().public_bytes(_RAW, _RAW_PUB)
    return {"clientDataJSON": _b64url(client_data), "authenticatorData": _b64url(auth_data),
            "signature": _b64url(sig), "cose_key": {"1": 1, "3": COSE_EDDSA, "-1": 6, "x": _b64url(pub)}}


def _unb64url(s: str) -> bytes:
    return base64.urlsafe_b64decode(s + "=" * (-len(s) % 4))


def verify_assertion(doc, assertion: dict, expected_origin: str, expected_rp_id: str,
                     require_uv: bool = True):
    """Returns (ok, reason). Replays the relying-party checks offline against the stored assertion + COSE
    key. reason ∈ {ok, bad_client_data, bad_type, challenge_mismatch, origin_mismatch, rpid_mismatch,
    user_not_present, user_not_verified, bad_signature, bad_key}."""
    try:
        client_data = _unb64url(assertion["clientDataJSON"])
        cd = json.loads(client_data)
        auth_data = _unb64url(assertion["authenticatorData"])
        sig = _unb64url(assertion["signature"])
        pub_raw = _unb64url(assertion["cose_key"]["x"])
    except Exception:
        return False, "bad_client_data"

    if cd.get("type") != "webauthn.get":
        return False, "bad_type"
    if cd.get("challenge") != _b64url(challenge_for(doc)):      # the approval is for THIS doc only
        return False, "challenge_mismatch"
    if cd.get("origin") != expected_origin:
        return False, "origin_mismatch"
    if auth_data[:32] != hashlib.sha256(expected_rp_id.encode()).digest():
        return False, "rpid_mismatch"
    flags = auth_data[32]
    if not (flags & FLAG_UP):
        return False, "user_not_present"
    if require_uv and not (flags & FLAG_UV):
        return False, "user_not_verified"
    try:
        Ed25519PublicKey.from_public_bytes(pub_raw).verify(sig, auth_data + hashlib.sha256(client_data).digest())
    except (InvalidSignature, Exception):
        return False, "bad_signature"
    return True, "ok"


def grant_gate(grant: dict, assertion, doc, expected_origin: str, expected_rp_id: str) -> dict:
    """The gate every grant passes: a DESTRUCTIVE grant must carry a verified WebAuthn approval bound to its
    doc; a non-destructive grant proceeds without one. Returns {allow, reason}."""
    if not grant.get("destructive"):
        return {"allow": True, "reason": "non_destructive"}
    if not assertion:
        return {"allow": False, "reason": "approval_missing"}
    ok, reason = verify_assertion(doc, assertion, expected_origin, expected_rp_id)
    return {"allow": ok, "reason": "approved" if ok else reason}


def webauthn_selftest() -> dict:
    """A hermetic P3-T04 demonstration: a destructive grant with a valid, doc-bound approval is allowed and
    verifies OFFLINE; then a different doc (challenge mismatch), a flipped signature, a cleared UV bit, and a
    wrong origin are each refused; a destructive grant with NO approval is refused while a non-destructive one
    proceeds. `ok` iff every property holds."""
    origin, rp_id = "https://approve.cyberware", "cyberware"
    priv = Ed25519PrivateKey.generate()
    doc = {"action": "delete", "target": "ledger/shard-7", "destructive": True}
    assertion = make_assertion(doc, priv, origin, rp_id)

    valid = verify_assertion(doc, assertion, origin, rp_id)[0]

    other_doc = {**doc, "target": "ledger/shard-8"}
    challenge_mismatch = verify_assertion(other_doc, assertion, origin, rp_id)[1] == "challenge_mismatch"

    bad_sig = dict(assertion)
    raw = bytearray(_unb64url(assertion["signature"]))
    raw[0] ^= 0x01
    bad_sig["signature"] = _b64url(bytes(raw))
    sig_refused = verify_assertion(doc, bad_sig, origin, rp_id)[1] == "bad_signature"

    no_uv = make_assertion(doc, priv, origin, rp_id, uv=False)
    uv_refused = verify_assertion(doc, no_uv, origin, rp_id)[1] == "user_not_verified"

    origin_refused = verify_assertion(doc, assertion, "https://evil.example", rp_id)[1] == "origin_mismatch"

    grant = {"destructive": True}
    missing_refused = grant_gate(grant, None, doc, origin, rp_id)["allow"] is False
    approved_allowed = grant_gate(grant, assertion, doc, origin, rp_id)["allow"] is True
    nondestructive_ok = grant_gate({"destructive": False}, None, doc, origin, rp_id)["allow"] is True

    return {"valid_approval_verifies_offline": valid, "challenge_bound_to_doc": challenge_mismatch,
            "tampered_signature_refused": sig_refused, "user_not_verified_refused": uv_refused,
            "wrong_origin_refused": origin_refused, "destructive_without_approval_refused": missing_refused,
            "destructive_with_approval_allowed": approved_allowed,
            "non_destructive_proceeds": nondestructive_ok,
            "ok": (valid and challenge_mismatch and sig_refused and uv_refused and origin_refused
                   and missing_refused and approved_allowed and nondestructive_ok)}
