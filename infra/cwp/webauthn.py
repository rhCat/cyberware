#!/usr/bin/env python3
"""infra/cwp/webauthn.py — WebAuthn approval for destructive grants (P3-T04, SV-4).

A destructive grant must carry a hardware-backed human approval, bound to the EXACT governed document. The
WebAuthn challenge is `sha256(JCS(doc))` — so an assertion approves one specific canonicalized doc and nothing
else. The authenticator (a roaming key / platform TPM) signs `authenticatorData || sha256(clientDataJSON)`
with its EdDSA (COSE alg -8) credential; the verifier **verifies entirely offline** — no live authenticator,
no network — replaying the checks a relying party would: the clientData type + challenge + origin, the RP-ID
hash, the User-Present and User-Verified flags, and the signature.

The signature is verified against the OPERATOR-REGISTERED credential public key that the caller supplies
(`credential_pubkey`), NEVER against the key the assertion carries about itself. A WebAuthn relying party
stores the credential's public key at registration time and checks every later assertion against THAT key;
trusting the key embedded in the assertion would let anyone mint a self-signed assertion over the doc with a
throwaway keypair. So the binding is two-fold: the challenge binds the approval to the doc, and the registered
credential key binds it to a specific authenticator. Any tamper (different doc, flipped signature, cleared UV
bit, wrong origin, or a key other than the registered one) is refused, and a destructive grant that lacks a
verified approval does not proceed.

Scope note (honest-when-broken): the live consumer of this surface today is the settlement dispute path
(infra/settle/disputes.py), which verifies m-of-n arbiter assertions against the operator-registered arbiter
keys. `grant_gate` below is the intended exec-path destructive gate but is not yet wired into govd's live
delegated path — govd currently gates destructive perks with its explicit --approve/push_back flow.
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
                     credential_pubkey: bytes, require_uv: bool = True):
    """Returns (ok, reason). Replays the relying-party checks offline against the stored assertion, verifying
    the signature against the OPERATOR-REGISTERED `credential_pubkey` (raw-32 Ed25519) — never the key the
    assertion carries about itself. An assertion presenting a key other than the registered credential is
    refused (credential_mismatch), so a self-signed forgery over the correct doc cannot pass. reason ∈ {ok,
    bad_client_data, bad_type, challenge_mismatch, origin_mismatch, rpid_mismatch, user_not_present,
    user_not_verified, credential_mismatch, bad_signature, bad_key}."""
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
    if pub_raw != credential_pubkey:                           # the assertion's key is NOT the registered credential
        return False, "credential_mismatch"
    try:                                                       # verify against the REGISTERED key, not the presented one
        Ed25519PublicKey.from_public_bytes(credential_pubkey).verify(
            sig, auth_data + hashlib.sha256(client_data).digest())
    except (InvalidSignature, Exception):
        return False, "bad_signature"
    return True, "ok"


def grant_gate(grant: dict, assertion, doc, expected_origin: str, expected_rp_id: str,
               credential_pubkey: bytes) -> dict:
    """The gate every grant passes: a DESTRUCTIVE grant must carry a verified WebAuthn approval bound to its
    doc AND signed by the operator-registered `credential_pubkey`; a non-destructive grant proceeds without
    one. Returns {allow, reason}."""
    if not grant.get("destructive"):
        return {"allow": True, "reason": "non_destructive"}
    if not assertion:
        return {"allow": False, "reason": "approval_missing"}
    ok, reason = verify_assertion(doc, assertion, expected_origin, expected_rp_id, credential_pubkey)
    return {"allow": ok, "reason": "approved" if ok else reason}


def _rawpub(priv: Ed25519PrivateKey) -> bytes:
    return priv.public_key().public_bytes(_RAW, _RAW_PUB)


def webauthn_selftest() -> dict:
    """A hermetic P3-T04 demonstration: a destructive grant with a valid, doc-bound approval signed by the
    REGISTERED credential is allowed and verifies OFFLINE; then a different doc (challenge mismatch), a flipped
    signature, a cleared UV bit, a wrong origin, and an assertion signed by an UNREGISTERED key (credential
    mismatch) are each refused; a destructive grant with NO approval is refused while a non-destructive one
    proceeds. `ok` iff every property holds."""
    origin, rp_id = "https://approve.cyberware", "cyberware"
    priv = Ed25519PrivateKey.generate()
    pub = _rawpub(priv)                                        # the operator-REGISTERED credential public key
    doc = {"action": "delete", "target": "ledger/shard-7", "destructive": True}
    assertion = make_assertion(doc, priv, origin, rp_id)

    valid = verify_assertion(doc, assertion, origin, rp_id, pub)[0]

    other_doc = {**doc, "target": "ledger/shard-8"}
    challenge_mismatch = verify_assertion(other_doc, assertion, origin, rp_id, pub)[1] == "challenge_mismatch"

    bad_sig = dict(assertion)
    raw = bytearray(_unb64url(assertion["signature"]))
    raw[0] ^= 0x01
    bad_sig["signature"] = _b64url(bytes(raw))
    sig_refused = verify_assertion(doc, bad_sig, origin, rp_id, pub)[1] == "bad_signature"

    no_uv = make_assertion(doc, priv, origin, rp_id, uv=False)
    uv_refused = verify_assertion(doc, no_uv, origin, rp_id, pub)[1] == "user_not_verified"

    origin_refused = verify_assertion(doc, assertion, "https://evil.example", rp_id, pub)[1] == "origin_mismatch"

    # a forgery: the CORRECT doc, signed by a throwaway key the operator never registered — refused because the
    # signature is checked against the registered credential, not the key the assertion presents about itself.
    forger = Ed25519PrivateKey.generate()
    forged = make_assertion(doc, forger, origin, rp_id)
    forged_key_refused = verify_assertion(doc, forged, origin, rp_id, pub)[1] == "credential_mismatch"

    grant = {"destructive": True}
    missing_refused = grant_gate(grant, None, doc, origin, rp_id, pub)["allow"] is False
    approved_allowed = grant_gate(grant, assertion, doc, origin, rp_id, pub)["allow"] is True
    forged_gate_refused = grant_gate(grant, forged, doc, origin, rp_id, pub)["allow"] is False
    nondestructive_ok = grant_gate({"destructive": False}, None, doc, origin, rp_id, pub)["allow"] is True

    return {"valid_approval_verifies_offline": valid, "challenge_bound_to_doc": challenge_mismatch,
            "tampered_signature_refused": sig_refused, "user_not_verified_refused": uv_refused,
            "wrong_origin_refused": origin_refused, "unregistered_key_refused": forged_key_refused,
            "destructive_without_approval_refused": missing_refused,
            "destructive_with_approval_allowed": approved_allowed,
            "destructive_with_forged_key_refused": forged_gate_refused,
            "non_destructive_proceeds": nondestructive_ok,
            "ok": (valid and challenge_mismatch and sig_refused and uv_refused and origin_refused
                   and forged_key_refused and missing_refused and approved_allowed and forged_gate_refused
                   and nondestructive_ok)}
