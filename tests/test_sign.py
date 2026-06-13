"""DSSE / Ed25519 signing over canonical bytes (infra/cwp/sign.py).

Pins the security properties: a good signature verifies, any tamper or wrong key fails, the signature is
deterministic (so an independent implementation reproduces it), and the key-id is stable. Skipped where
pyca/cryptography is absent.
"""
import pytest

pytest.importorskip("cryptography")

from infra.cwp import sign  # noqa: E402

SEED = bytes(range(32))                                       # a fixed seed → a deterministic test key


def _key():
    return sign.keygen_from_seed(SEED)


def test_roundtrip_verifies():
    k = _key()
    env = sign.sign({"b": 1, "a": 2}, k)
    assert sign.verify(env, k.public_key())
    assert env["payloadType"] == sign.PAYLOAD_TYPE
    assert env["signatures"][0]["keyid"].startswith("ed25519:")


def test_payload_tamper_is_rejected():
    k = _key()
    env = sign.sign({"x": 1}, k)
    import base64
    bad = dict(env, payload=base64.b64encode(b'{"x":2}').decode())   # swap the payload, keep the sig
    assert not sign.verify(bad, k.public_key())


def test_signature_tamper_is_rejected():
    k = _key()
    env = sign.sign({"x": 1}, k)
    sigs = [dict(env["signatures"][0])]
    raw = bytearray(__import__("base64").b64decode(sigs[0]["sig"]))
    raw[0] ^= 0xFF
    sigs[0]["sig"] = __import__("base64").b64encode(bytes(raw)).decode()
    assert not sign.verify(dict(env, signatures=sigs), k.public_key())


def test_wrong_key_is_rejected():
    env = sign.sign({"x": 1}, _key())
    other = sign.keygen_from_seed(bytes(range(1, 33)))
    assert not sign.verify(env, other.public_key())


def test_signature_is_deterministic_and_over_canonical_bytes():
    k = _key()
    # construction order must not matter — same canonical bytes → byte-identical Ed25519 signature
    a = sign.sign({"b": 1, "a": 2}, k)
    b = sign.sign({"a": 2, "b": 1}, k)
    assert a["payload"] == b["payload"] and a["signatures"][0]["sig"] == b["signatures"][0]["sig"]


def test_keyid_is_stable():
    pub = sign.public_raw(_key())
    assert sign.keyid(pub) == sign.keyid(pub)
    assert sign.keyid(pub) != sign.keyid(sign.public_raw(sign.keygen_from_seed(bytes(range(1, 33)))))
