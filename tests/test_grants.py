"""Ed25519-DSSE signed grants (P2-T01, SV-3 spine): offline-verifiable, replay-refused, expiry + ±60s skew.
The capability token the kernel boundary will later enforce; the crypto here is platform-agnostic."""
import base64
import json

from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

from infra.cwp import canonical, sign
from infra.exec.grants import NonceCache, mint_grant, verify_grant


def _kp():
    sk = Ed25519PrivateKey.generate()
    return sk, sk.public_key()


def _grant(sk, nbf, exp, nonce="n1"):
    return mint_grant(sk, run_id="r", plan_sha="p", nbf=nbf, exp=exp, nonce=nonce)


def test_valid_grant_verifies_offline():
    sk, pk = _kp()
    assert verify_grant(pk, _grant(sk, 990, 1100), now=1000) == (True, "ok")


def test_replay_refused():
    sk, pk = _kp()
    cache = NonceCache()
    env = _grant(sk, 990, 1100, nonce="abc")
    assert verify_grant(pk, env, now=1000, nonce_cache=cache)[0] is True
    assert verify_grant(pk, env, now=1000, nonce_cache=cache) == (False, "replay")   # second use


def test_expired_refused():
    sk, pk = _kp()
    assert verify_grant(pk, _grant(sk, 800, 900), now=1000) == (False, "expired")


def test_skew_honored_60s_boundaries():
    sk, pk = _kp()
    nbf, exp = 1000, 2000
    env = _grant(sk, nbf, exp)
    assert verify_grant(pk, env, now=exp + 60)[0] is True                  # +60s past exp: honored
    assert verify_grant(pk, env, now=exp + 61) == (False, "expired")       # +61s: refused
    assert verify_grant(pk, env, now=nbf - 60)[0] is True                  # -60s before nbf: honored
    assert verify_grant(pk, env, now=nbf - 61) == (False, "not_yet_valid")


def test_forged_grant_refused():
    sk, pk = _kp()
    env = _grant(sk, 990, 1100)
    body = json.loads(base64.b64decode(env["payload"]))
    body["capabilities"] = ["root"]                                       # tamper the claim, keep the old sig
    forged = {**env, "payload": base64.b64encode(canonical.canonical_bytes(body)).decode()}
    assert verify_grant(pk, forged, now=1000) == (False, "bad_signature")
    _sk2, pk2 = _kp()
    assert verify_grant(pk2, env, now=1000) == (False, "bad_signature")   # wrong key


def test_non_grant_envelope_refused():
    sk, pk = _kp()
    assert verify_grant(pk, sign.sign({"x": 1}, sk), now=1000) == (False, "wrong_type")
