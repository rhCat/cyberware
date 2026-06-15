"""Mutation-pinning slice for infra/exec/grantverify.py — the R3 gate cws-mutate/mut-grant-verify.
Pins both sides of every comparison + and/or arm in the grant verifier so a single-token mutation flips
an assertion. Imports cwd-relative (resolves to the mutator's sandbox copy)."""
import base64
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey  # noqa: E402

from infra.cwp import canonical, sign  # noqa: E402
from infra.exec import grantverify as G  # noqa: E402


def _kp():
    sk = Ed25519PrivateKey.generate()
    return sk, sk.public_key()


def _mint(sk, nbf, exp, nonce="n"):
    return sign.sign({"run_id": "r", "plan_sha": "p", "snippet_shas": {}, "capabilities": [],
                      "credentials": [], "nbf": nbf, "exp": exp, "nonce": nonce}, sk, payload_type=G.GRANT_TYPE)


def test_valid_verifies():
    sk, pk = _kp()
    assert G.verify_grant(pk, _mint(sk, 990, 1100), now=1000) == (True, "ok")


def test_bad_signature_both_ways():
    sk, pk = _kp()
    env = _mint(sk, 990, 1100)
    body = json.loads(base64.b64decode(env["payload"]))
    body["capabilities"] = ["root"]
    forged = {**env, "payload": base64.b64encode(canonical.canonical_bytes(body)).decode()}
    assert G.verify_grant(pk, forged, now=1000) == (False, "bad_signature")
    _sk2, pk2 = _kp()
    assert G.verify_grant(pk2, env, now=1000) == (False, "bad_signature")


def test_wrong_type():
    sk, pk = _kp()
    assert G.verify_grant(pk, sign.sign({"x": 1}, sk), now=1000) == (False, "wrong_type")


def test_malformed_window_or_arm():
    sk, pk = _kp()
    assert G.verify_grant(pk, _mint(sk, "900", "1100"), now=1000) == (False, "malformed_window")  # both str
    assert G.verify_grant(pk, _mint(sk, 1000, "x"), now=1000) == (False, "malformed_window")       # one str (pins `or`)


def test_skew_window_both_sides():
    sk, pk = _kp()
    nbf, exp = 1000, 2000
    env = _mint(sk, nbf, exp)
    assert G.verify_grant(pk, env, now=exp + 60)[0] is True
    assert G.verify_grant(pk, env, now=exp + 61) == (False, "expired")
    assert G.verify_grant(pk, env, now=nbf - 60)[0] is True
    assert G.verify_grant(pk, env, now=nbf - 61) == (False, "not_yet_valid")


def test_malformed_nonce_and_arm():
    sk, pk = _kp()
    for bad in (None, ["a"], "", 5):
        assert G.verify_grant(pk, _mint(sk, 990, 1100, nonce=bad), now=1000) == (False, "malformed_nonce")


def test_run_and_plan_binding_both_ways():
    sk, pk = _kp()
    env = _mint(sk, 990, 1100)                                   # body run_id="r", plan_sha="p"
    assert G.verify_grant(pk, env, now=1000, expect_run_id="r") == (True, "ok")          # match -> ok
    assert G.verify_grant(pk, env, now=1000, expect_run_id="x") == (False, "wrong_run")  # mismatch -> refuse
    assert G.verify_grant(pk, env, now=1000, expect_plan_sha="p") == (True, "ok")
    assert G.verify_grant(pk, env, now=1000, expect_plan_sha="x") == (False, "wrong_plan")
    assert G.verify_grant(pk, env, now=1000, expect_run_id="r", expect_plan_sha="p") == (True, "ok")


def test_replay_and_cross_issuer():
    skA, pkA = _kp()
    skB, pkB = _kp()
    cache = G.NonceCache()
    assert G.verify_grant(pkA, _mint(skA, 990, 1100, nonce="x"), now=1000, nonce_cache=cache)[0] is True
    assert G.verify_grant(pkA, _mint(skA, 990, 1100, nonce="x"), now=1000, nonce_cache=cache) == (False, "replay")
    assert G.verify_grant(pkB, _mint(skB, 990, 1100, nonce="x"), now=1000, nonce_cache=cache)[0] is True
