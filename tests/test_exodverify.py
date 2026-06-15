"""Mutation-pinning slice for infra/exec/exodverify.py — the exod step-result verify surface.
Pins both sides of every comparison + and-arm so a single-token mutation flips an assertion (the ouroboros
ratchet, alongside grantverify). Imports cwd-relative (resolves to the mutator's sandbox copy)."""
import base64
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey  # noqa: E402

from infra.cwp import canonical, sign  # noqa: E402
from infra.exec import exodverify as E  # noqa: E402


def _kp():
    sk = Ed25519PrivateKey.generate()
    return sk, sk.public_key()


def _mint(sk, *, run_id="r", plan_sha="p", status="ok", nonce="n", payload_type=None):
    body = {"run_id": run_id, "plan_sha": plan_sha, "step": "1", "exit": 0, "status": status,
            "output_sha": "x", "nonce": nonce, "ts": "t"}
    return sign.sign(body, sk, payload_type=payload_type or E.STEP_RESULT_TYPE)


def test_valid_verifies():
    sk, pk = _kp()
    assert E.verify_step_result(pk, _mint(sk)) == (True, "ok")


def test_forged_status_both_ways():
    sk, pk = _kp()
    env = _mint(sk)
    body = json.loads(base64.b64decode(env["payload"]))
    body["status"] = "error"                                     # tamper the claim without re-signing
    forged = {**env, "payload": base64.b64encode(canonical.canonical_bytes(body)).decode()}
    assert E.verify_step_result(pk, forged) == (False, "forged_status")
    _sk2, pk2 = _kp()
    assert E.verify_step_result(pk2, env) == (False, "forged_status")   # a different principal


def test_wrong_type():
    sk, pk = _kp()
    env = _mint(sk, payload_type="application/vnd.cyberware.grant+json")  # signed, but the wrong type
    assert E.verify_step_result(pk, env) == (False, "wrong_type")


def test_run_and_plan_binding_both_ways():
    sk, pk = _kp()
    env = _mint(sk, run_id="r", plan_sha="p")
    assert E.verify_step_result(pk, env, expect_run_id="r") == (True, "ok")            # match -> ok
    assert E.verify_step_result(pk, env, expect_run_id="x") == (False, "wrong_run")    # mismatch -> refuse
    assert E.verify_step_result(pk, env, expect_plan_sha="p") == (True, "ok")
    assert E.verify_step_result(pk, env, expect_plan_sha="x") == (False, "wrong_plan")


def test_malformed_status_and_valid_set():
    sk, pk = _kp()
    for good in ("ok", "error", "refused"):
        assert E.verify_step_result(pk, _mint(sk, status=good))[0] is True
    assert E.verify_step_result(pk, _mint(sk, status="bogus")) == (False, "malformed_status")


def test_malformed_nonce_and_arm():
    sk, pk = _kp()
    for bad in (None, ["a"], "", 5):
        assert E.verify_step_result(pk, _mint(sk, nonce=bad)) == (False, "malformed_nonce")
    assert E.verify_step_result(pk, _mint(sk, nonce="ok"))[0] is True


def test_replay_and_cross_principal():
    skA, pkA = _kp()
    skB, pkB = _kp()
    cache = E.NonceCache()
    assert E.verify_step_result(pkA, _mint(skA, nonce="x"), nonce_cache=cache)[0] is True
    assert E.verify_step_result(pkA, _mint(skA, nonce="x"), nonce_cache=cache) == (False, "replay")
    assert E.verify_step_result(pkB, _mint(skB, nonce="x"), nonce_cache=cache)[0] is True   # other principal
