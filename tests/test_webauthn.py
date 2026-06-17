"""WebAuthn approval for destructive grants (P3-T04, SV-4): the challenge is sha256(JCS(doc)), so an approval
is bound to one canonical doc; verification is fully offline from the stored assertion + COSE key. A different
doc, a flipped signature, a cleared User-Verified bit, or a wrong origin are each refused, and a destructive
grant without a verified approval does not proceed. The tampered-signature test is the mutation guard: delete
the signature check and it fails."""
from __future__ import annotations

from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

from infra.cwp import webauthn as W

ORIGIN, RP = "https://approve.cyberware", "cyberware"


def test_selftest_holds():
    r = W.webauthn_selftest()
    assert r["ok"], r
    assert r["valid_approval_verifies_offline"] and r["destructive_without_approval_refused"]


def test_challenge_is_bound_to_the_canonical_doc():
    priv = Ed25519PrivateKey.generate()
    doc = {"action": "delete", "target": "x", "destructive": True}
    a = W.make_assertion(doc, priv, ORIGIN, RP)
    assert W.verify_assertion(doc, a, ORIGIN, RP)[0]
    # a doc with the same fields in different insertion order canonicalizes identically → still valid
    assert W.verify_assertion({"destructive": True, "target": "x", "action": "delete"}, a, ORIGIN, RP)[0]
    # a genuinely different doc → challenge mismatch
    assert W.verify_assertion({**doc, "target": "y"}, a, ORIGIN, RP)[1] == "challenge_mismatch"


def test_tampered_signature_is_refused():
    priv = Ed25519PrivateKey.generate()
    doc = {"action": "delete", "destructive": True}
    a = W.make_assertion(doc, priv, ORIGIN, RP)
    raw = bytearray(W._unb64url(a["signature"]))
    raw[0] ^= 0x01
    a2 = {**a, "signature": W._b64url(bytes(raw))}
    assert W.verify_assertion(doc, a2, ORIGIN, RP)[1] == "bad_signature"


def test_user_verification_and_origin_are_enforced():
    priv = Ed25519PrivateKey.generate()
    doc = {"destructive": True}
    no_uv = W.make_assertion(doc, priv, ORIGIN, RP, uv=False)
    assert W.verify_assertion(doc, no_uv, ORIGIN, RP)[1] == "user_not_verified"
    good = W.make_assertion(doc, priv, ORIGIN, RP)
    assert W.verify_assertion(doc, good, "https://evil.example", RP)[1] == "origin_mismatch"


def test_grant_gate_requires_approval_only_for_destructive():
    priv = Ed25519PrivateKey.generate()
    doc = {"destructive": True}
    a = W.make_assertion(doc, priv, ORIGIN, RP)
    assert W.grant_gate({"destructive": True}, None, doc, ORIGIN, RP)["allow"] is False
    assert W.grant_gate({"destructive": True}, a, doc, ORIGIN, RP)["allow"] is True
    assert W.grant_gate({"destructive": False}, None, doc, ORIGIN, RP)["allow"] is True
