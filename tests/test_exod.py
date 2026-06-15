"""exod daemon (P2-T02): the separate principal whose signature is the ONLY status the ledger trusts.

These pin the two acceptance criteria directly:
  * forged_status_rejected — a step-result not signed by exod (a forged self-report, an unsigned report, a
    tampered or replayed result) is refused AND recorded as evidence;
  * self_reports_replaced  — the only status that becomes authoritative carries exod's principal; exod runs
    the step and signs the outcome, so the executor no longer reports its own exit code.

The channel + crypto are platform-agnostic and run here; the sandboxed run itself needs Linux + bwrap, so
the real end-to-end is guarded by is_available() and runs in the exec image.
"""
from __future__ import annotations
import base64
import json
import os
import subprocess
import threading
import time

import pytest
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

from infra.cwp import sign
from infra.exec.exod import Exod, meter_of, record_step_result, request_step
from infra.exec.exodverify import STEP_RESULT_TYPE, NonceCache, result_body, verify_step_result
from infra.exec.grants import mint_grant
from infra.exec.sandbox import is_available


def _kp():
    sk = Ed25519PrivateKey.generate()
    return sk, sk.public_key()


class _Stub:
    """A fake confined runner — records the call and returns a chosen exit/stdout, no kernel needed. Lets the
    channel logic (grant-gate, signing, authority) be proven off-Linux."""
    def __init__(self, rc=0, out="hi"):
        self.rc, self.out, self.calls = rc, out, []

    def __call__(self, profile, argv):
        self.calls.append((profile, argv))
        return subprocess.CompletedProcess(argv, self.rc, self.out, "")


def _req(issuer_sk, *, run_id="R1", plan_sha="P1", nonce="r-nonce", now=1000, **kw):
    base = dict(run_id=run_id, plan_sha=plan_sha, step="1",
                argv=["bash", "-lc", "echo hi"], workspace="/ws", nonce=nonce)
    base.update(kw)
    base["grant"] = mint_grant(issuer_sk, run_id=run_id, plan_sha=plan_sha,
                               nbf=now - 10, exp=now + 100, nonce="g-" + nonce, capabilities=["run"])
    return base


# ── self_reports_replaced ───────────────────────────────────────────────────────────────────────────

def test_authentic_exod_result_is_authoritative(tmp_path):
    isk, ipub = _kp()
    exod = Exod(Ed25519PrivateKey.generate(), grant_issuer_pub=ipub, runner=_Stub(rc=0, out="ok-out"))
    env = exod.run_step(_req(isk), now=1000)
    assert env["payloadType"] == STEP_RESULT_TYPE
    body = result_body(env)
    assert body["status"] == "ok" and body["exit"] == 0
    lp = str(tmp_path / "run-ledger.json")
    accepted, rec = record_step_result(lp, exod.public_key, env, expect_run_id="R1", expect_plan_sha="P1")
    assert accepted
    assert rec["authority"] == "exod" and rec["status"] == "ok"      # the status came from exod's signature
    assert rec["exod_keyid"].startswith("ed25519:")


# ── forged_status_rejected ──────────────────────────────────────────────────────────────────────────

def test_forged_self_report_is_refused_and_recorded(tmp_path):
    isk, ipub = _kp()
    exod = Exod(Ed25519PrivateKey.generate(), grant_issuer_pub=ipub, runner=_Stub())
    forger = Ed25519PrivateKey.generate()                            # the executor trying to sign its own status
    body = {"run_id": "R1", "plan_sha": "P1", "step": "1", "exit": 0, "status": "ok",
            "output_sha": "x", "nonce": "n1", "ts": "t"}
    forged = sign.sign(body, forger, payload_type=STEP_RESULT_TYPE)
    lp = str(tmp_path / "run-ledger.json")
    accepted, rec = record_step_result(lp, exod.public_key, forged, expect_run_id="R1")
    assert not accepted
    assert rec["event"] == "forged_status_refused" and rec["reason"] == "forged_status"
    assert json.load(open(lp))["runs"][-1]["event"] == "forged_status_refused"   # recorded as evidence


def test_unsigned_self_report_is_refused(tmp_path):
    exod_pub = Ed25519PrivateKey.generate().public_key()
    fake = {"payloadType": STEP_RESULT_TYPE,
            "payload": base64.b64encode(b'{"status":"ok","exit":0}').decode(), "signatures": []}
    accepted, rec = record_step_result(str(tmp_path / "l.json"), exod_pub, fake)
    assert not accepted and rec["reason"] == "forged_status"


def test_tampered_exod_result_is_refused():
    isk, ipub = _kp()
    exod = Exod(Ed25519PrivateKey.generate(), grant_issuer_pub=ipub, runner=_Stub(rc=1, out="x"))
    env = exod.run_step(_req(isk), now=1000)
    assert result_body(env)["status"] == "error"                    # a real failure...
    body = result_body(env)
    body["status"], body["exit"] = "ok", 0                          # ...rewritten to success
    env["payload"] = base64.b64encode(json.dumps(body).encode()).decode()   # without re-signing
    ok, reason = verify_step_result(exod.public_key, env, expect_run_id="R1")
    assert not ok and reason == "forged_status"


def test_replayed_result_is_refused():
    isk, ipub = _kp()
    exod = Exod(Ed25519PrivateKey.generate(), grant_issuer_pub=ipub, runner=_Stub())
    env = exod.run_step(_req(isk, nonce="once"), now=1000)
    nc = NonceCache()
    assert verify_step_result(exod.public_key, env, nonce_cache=nc)[0]
    assert verify_step_result(exod.public_key, env, nonce_cache=nc) == (False, "replay")


def test_wrong_run_or_type_binding_is_refused():
    isk, ipub = _kp()
    exod = Exod(Ed25519PrivateKey.generate(), grant_issuer_pub=ipub, runner=_Stub())
    env = exod.run_step(_req(isk, run_id="R1"), now=1000)
    assert verify_step_result(exod.public_key, env, expect_run_id="OTHER") == (False, "wrong_run")
    assert verify_step_result(exod.public_key, env, expect_plan_sha="OTHER") == (False, "wrong_plan")
    env["payloadType"] = "application/vnd.cyberware.grant+json"
    assert verify_step_result(exod.public_key, env)[1] in ("forged_status", "wrong_type")


# ── grant gating: exod never runs an ungranted step ──────────────────────────────────────────────────

def test_ungranted_step_is_refused_without_running():
    isk, ipub = _kp()
    stub = _Stub()
    exod = Exod(Ed25519PrivateKey.generate(), grant_issuer_pub=ipub, runner=stub)
    req = _req(isk)
    req["grant"] = mint_grant(isk, run_id="R1", plan_sha="P1", nbf=0, exp=10, nonce="expired",
                              capabilities=["run"])
    env = exod.run_step(req, now=100000)                            # long past the grant's exp
    assert result_body(env)["status"] == "refused"
    assert stub.calls == []                                         # the step NEVER ran
    assert verify_step_result(exod.public_key, env)[0]             # the refusal is itself on exod's channel


def test_replayed_grant_does_not_re_run_the_step():
    isk, ipub = _kp()
    stub = _Stub(rc=0, out="once")
    exod = Exod(Ed25519PrivateKey.generate(), grant_issuer_pub=ipub, runner=stub)
    req = _req(isk, nonce="grun")                                   # one grant (single-use nonce)
    first = exod.run_step(req, now=1000)
    second = exod.run_step(req, now=1000)                           # replay the SAME grant
    assert result_body(first)["status"] == "ok"
    assert result_body(second)["status"] == "refused"              # exod spent the grant nonce
    assert len(stub.calls) == 1                                     # the step ran exactly once


# ── platform-agnostic UDS channel + the real-kernel end to end ────────────────────────────────────────

def test_uds_channel_round_trip():
    isk, ipub = _kp()
    exod = Exod(Ed25519PrivateKey.generate(), grant_issuer_pub=ipub, runner=_Stub(rc=0, out="sock"))
    sp = f"/tmp/exod-test-{os.getpid()}.sock"                       # short path (AF_UNIX length limit)
    t = threading.Thread(target=lambda: exod.serve(sp, now_fn=lambda: 1000, max_requests=1), daemon=True)
    t.start()
    try:
        env = request_step(sp, _req(isk))                          # retries the connect past the bind/listen race
        assert result_body(env)["status"] == "ok"
        assert verify_step_result(exod.public_key, env, expect_run_id="R1")[0]
    finally:
        t.join(timeout=2)
        if os.path.exists(sp):
            os.unlink(sp)


# ── grant↔request binding (the adversarial-probe HIGH finding) ───────────────────────────────────────

def test_grant_for_one_run_does_not_authorize_another():
    isk, ipub = _kp()
    stub = _Stub()
    exod = Exod(Ed25519PrivateKey.generate(), grant_issuer_pub=ipub, runner=stub)
    grant = mint_grant(isk, run_id="R-BENIGN", plan_sha="P-BENIGN", nbf=990, exp=1100,
                       nonce="g1", capabilities=["run"])
    evil = dict(run_id="R-EVIL", plan_sha="P-EVIL", step="7",
                argv=["bash", "-lc", "exfiltrate"], workspace="/ws", nonce="r", grant=grant)
    env = exod.run_step(evil, now=1000)
    assert result_body(env)["status"] == "refused"                 # grant minted for R-BENIGN, not R-EVIL
    assert stub.calls == []                                        # the laundered command NEVER ran


def test_grant_must_carry_the_run_capability():
    isk, ipub = _kp()
    stub = _Stub()
    exod = Exod(Ed25519PrivateKey.generate(), grant_issuer_pub=ipub, runner=stub)
    g = mint_grant(isk, run_id="R1", plan_sha="P1", nbf=990, exp=1100, nonce="g1", capabilities=[])
    req = dict(run_id="R1", plan_sha="P1", step="1", argv=["x"], workspace="/ws", nonce="r", grant=g)
    assert result_body(exod.run_step(req, now=1000))["status"] == "refused"   # capabilities=[] grants nothing
    assert stub.calls == []


def test_grant_binds_the_approved_snippet():
    isk, ipub = _kp()
    stub = _Stub()
    exod = Exod(Ed25519PrivateKey.generate(), grant_issuer_pub=ipub, runner=stub)
    g = mint_grant(isk, run_id="R1", plan_sha="P1", nbf=990, exp=1100, nonce="g1",
                   capabilities=["run"], snippet_shas={"1": "sha-approved"})
    base = dict(run_id="R1", plan_sha="P1", step="1", argv=["x"], workspace="/ws", grant=g)
    wrong = exod.run_step({**base, "snippet_sha": "sha-EVIL", "nonce": "r1"}, now=1000)
    assert result_body(wrong)["status"] == "refused" and stub.calls == []     # un-granted snippet refused
    good = exod.run_step({**base, "snippet_sha": "sha-approved", "nonce": "r2"}, now=1000)
    assert result_body(good)["status"] == "ok" and len(stub.calls) == 1       # the refusal did NOT burn the grant


def test_result_carries_an_exod_attested_meter():
    isk, ipub = _kp()
    exod = Exod(Ed25519PrivateKey.generate(), grant_issuer_pub=ipub, runner=_Stub(rc=0, out="x"))
    env = exod.run_step(_req(isk), now=1000)
    assert verify_step_result(exod.public_key, env, expect_run_id="R1")[0]   # the meter is inside the signature
    meter = meter_of(env)
    assert meter is not None and meter["by"] == "exod" and isinstance(meter["wall_ms"], (int, float))


def test_result_is_bound_to_the_grant_nonce():
    isk, ipub = _kp()
    exod = Exod(Ed25519PrivateKey.generate(), grant_issuer_pub=ipub, runner=_Stub())
    env = exod.run_step(_req(isk, nonce="caller-chosen"), now=1000)
    assert result_body(env)["nonce"] == "g-caller-chosen"          # the GRANT nonce, not the caller's request nonce


def test_ledger_is_a_durable_replay_guard_without_a_cache(tmp_path):
    isk, ipub = _kp()
    exod = Exod(Ed25519PrivateKey.generate(), grant_issuer_pub=ipub, runner=_Stub())
    env = exod.run_step(_req(isk), now=1000)
    lp = str(tmp_path / "run-ledger.json")
    a1, _ = record_step_result(lp, exod.public_key, env, expect_run_id="R1", expect_plan_sha="P1")
    a2, rec = record_step_result(lp, exod.public_key, env, expect_run_id="R1", expect_plan_sha="P1")
    assert a1 and not a2                                           # no nonce_cache passed, yet the 2nd is caught
    assert rec["reason"] == "replay" and rec["event"] == "forged_status_refused"


def test_recorder_binds_to_the_ledger_run_header(tmp_path):
    isk, ipub = _kp()
    exod = Exod(Ed25519PrivateKey.generate(), grant_issuer_pub=ipub, runner=_Stub())
    lp = str(tmp_path / "run-ledger.json")
    record_step_result(lp, exod.public_key, exod.run_step(_req(isk, run_id="R1"), now=1000),
                       expect_run_id="R1", expect_plan_sha="P1")   # this ledger is now stamped run R1
    foreign = exod.run_step(_req(isk, run_id="R2", plan_sha="P2", nonce="x"), now=1000)
    accepted, rec = record_step_result(lp, exod.public_key, foreign)   # no expect_* — derived from the header
    assert not accepted and rec["reason"] == "wrong_run"


def test_issuer_key_must_differ_from_identity():
    sk = Ed25519PrivateKey.generate()
    with pytest.raises(ValueError):
        Exod(sk, grant_issuer_pub=sk.public_key())                 # self-issued grants are a foot-gun, forbidden


def test_slowloris_client_does_not_wedge_the_listener():
    import socket as _s
    isk, ipub = _kp()
    exod = Exod(Ed25519PrivateKey.generate(), grant_issuer_pub=ipub, runner=_Stub())
    sp = f"/tmp/exod-slow-{os.getpid()}.sock"
    t = threading.Thread(target=lambda: exod.serve(sp, now_fn=lambda: 1000, max_requests=1, recv_timeout=0.4),
                         daemon=True)
    t.start()
    try:
        for _ in range(100):
            if os.path.exists(sp):
                break
            time.sleep(0.02)
        c = _s.socket(_s.AF_UNIX, _s.SOCK_STREAM)
        c.connect(sp)
        c.sendall(b'{"partial": "no newline')                     # open + withhold the newline forever
        t.join(timeout=3)
        assert not t.is_alive()                                   # the listener timed out + reaped, not wedged
        c.close()
    finally:
        if os.path.exists(sp):
            os.unlink(sp)


@pytest.mark.skipif(not is_available(), reason="needs a Linux host with bwrap")
def test_end_to_end_real_sandbox(tmp_path):
    isk, ipub = _kp()
    ws = tmp_path / "ws"
    ws.mkdir()
    os.chmod(ws, 0o777)
    exod = Exod(Ed25519PrivateKey.generate(), grant_issuer_pub=ipub)   # the REAL bwrap runner
    req = _req(isk, workspace=str(ws), argv=["bash", "-lc", "echo from-sandbox"])
    env = exod.run_step(req, now=1000)
    body = result_body(env)
    assert body["status"] == "ok" and body["exit"] == 0
    assert verify_step_result(exod.public_key, env, expect_run_id="R1")[0]
