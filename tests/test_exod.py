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
from infra.exec import vault as _vaultmod
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

    def __call__(self, profile, argv, backend=None):
        self.calls.append((profile, argv, backend))
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


def _stage_closure(ws, files):
    """Write a materialized SNIP dir under `ws` and return (snip_dir, {name: sha})."""
    import hashlib
    snip = os.path.join(ws, "snip")
    os.makedirs(snip, exist_ok=True)
    shas = {}
    for name, content in files.items():
        with open(os.path.join(snip, name), "w") as f:
            f.write(content)
        shas[name] = hashlib.sha256(content.encode()).hexdigest()
    return snip, shas


def test_exod_rehashes_the_materialized_closure_and_runs_the_blessed_one(tmp_path):
    """exod itself re-derives the staged digests at time of use and runs the step only when they match the
    grant's pin — the integrity check is exod's, not a digest govd computed."""
    isk, ipub = _kp()
    stub = _Stub(rc=0, out="x")
    exod = Exod(Ed25519PrivateKey.generate(), grant_issuer_pub=ipub, runner=stub)
    ws = str(tmp_path / "ws")
    os.makedirs(ws)
    snip, shas = _stage_closure(ws, {"a.sh": "echo a\n", "contracts.json": "{}"})
    g = mint_grant(isk, run_id="R1", plan_sha="P1", nbf=990, exp=1100, nonce="g1",
                   capabilities=["run"], snippet_shas={"a.sh": shas["a.sh"]})
    req = dict(run_id="R1", plan_sha="P1", step="1", argv=["bash", "x", "--step", "1"],
               workspace=ws, env={"SNIP": snip}, nonce="r1", grant=g)
    assert result_body(exod.run_step(req, now=1000))["status"] == "ok" and len(stub.calls) == 1


def test_exod_refuses_a_post_grant_porter_swap_toctou(tmp_path):
    """The grant pins the BLESSED porter; the staged file is swapped after the grant — exod re-hashes the
    bytes it is about to run and refuses, never executing the swapped porter (the P1-T06 TOCTOU class)."""
    isk, ipub = _kp()
    stub = _Stub()
    exod = Exod(Ed25519PrivateKey.generate(), grant_issuer_pub=ipub, runner=stub)
    ws = str(tmp_path / "ws")
    os.makedirs(ws)
    snip, shas = _stage_closure(ws, {"a.sh": "echo benign\n"})
    blessed = shas["a.sh"]
    with open(os.path.join(snip, "a.sh"), "w") as f:
        f.write("echo PWNED\n")                                          # swapped after the grant was minted
    g = mint_grant(isk, run_id="R1", plan_sha="P1", nbf=990, exp=1100, nonce="g1",
                   capabilities=["run"], snippet_shas={"a.sh": blessed})
    req = dict(run_id="R1", plan_sha="P1", step="1", argv=["bash", "x"], workspace=ws,
               env={"SNIP": snip}, nonce="r1", grant=g)
    assert result_body(exod.run_step(req, now=1000))["status"] == "refused"
    assert stub.calls == []                                              # the swapped porter NEVER ran


def test_exod_refuses_a_swapped_core_even_with_a_pristine_porter(tmp_path):
    """The grant pins the whole closure (.sh AND .py); the porter is untouched but the .py core it execs is
    swapped — exod checks every member, so the swapped core is refused (cooperative-parity)."""
    isk, ipub = _kp()
    stub = _Stub()
    exod = Exod(Ed25519PrivateKey.generate(), grant_issuer_pub=ipub, runner=stub)
    ws = str(tmp_path / "ws")
    os.makedirs(ws)
    snip, shas = _stage_closure(ws, {"c.sh": "python3 c.py\n", "c.py": "print('ok')\n"})
    pins = dict(shas)
    with open(os.path.join(snip, "c.py"), "w") as f:
        f.write("print('PWNED')\n")                                      # the core, swapped; the porter is pristine
    g = mint_grant(isk, run_id="R1", plan_sha="P1", nbf=990, exp=1100, nonce="g1",
                   capabilities=["run"], snippet_shas=pins)
    req = dict(run_id="R1", plan_sha="P1", step="1", argv=["bash", "x"], workspace=ws,
               env={"SNIP": snip}, nonce="r1", grant=g)
    assert result_body(exod.run_step(req, now=1000))["status"] == "refused" and stub.calls == []


def test_exod_refuses_a_smuggled_unpinned_sibling(tmp_path):
    """A blessed porter cannot smuggle an unpinned sibling into the materialized closure — exod refuses any
    staged member the grant did not pin (skill_index-parity)."""
    isk, ipub = _kp()
    stub = _Stub()
    exod = Exod(Ed25519PrivateKey.generate(), grant_issuer_pub=ipub, runner=stub)
    ws = str(tmp_path / "ws")
    os.makedirs(ws)
    snip, shas = _stage_closure(ws, {"a.sh": "echo a\n", "evil.py": "import os\n"})
    g = mint_grant(isk, run_id="R1", plan_sha="P1", nbf=990, exp=1100, nonce="g1",
                   capabilities=["run"], snippet_shas={"a.sh": shas["a.sh"]})       # evil.py NOT pinned
    req = dict(run_id="R1", plan_sha="P1", step="1", argv=["bash", "x"], workspace=ws,
               env={"SNIP": snip}, nonce="r1", grant=g)
    assert result_body(exod.run_step(req, now=1000))["status"] == "refused" and stub.calls == []


def test_exod_refuses_staged_code_under_an_empty_pin(tmp_path):
    """A run grant that materialized code but pins NOTHING is fail-closed — the fail-open in the membership
    check is closed for any staged closure (a raw-argv run with no staged code still runs, tested elsewhere)."""
    isk, ipub = _kp()
    stub = _Stub()
    exod = Exod(Ed25519PrivateKey.generate(), grant_issuer_pub=ipub, runner=stub)
    ws = str(tmp_path / "ws")
    os.makedirs(ws)
    snip, _ = _stage_closure(ws, {"a.sh": "echo a\n"})
    g = mint_grant(isk, run_id="R1", plan_sha="P1", nbf=990, exp=1100, nonce="g1",
                   capabilities=["run"], snippet_shas={})                            # pins nothing
    req = dict(run_id="R1", plan_sha="P1", step="1", argv=["bash", "x"], workspace=ws,
               env={"SNIP": snip}, nonce="r1", grant=g)
    assert result_body(exod.run_step(req, now=1000))["status"] == "refused" and stub.calls == []


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
        c = _s.socket(_s.AF_UNIX, _s.SOCK_STREAM)
        for _ in range(200):                                      # the socket file exists at bind(), but
            try:                                                  # only accepts after listen() — retry past
                c.connect(sp); break                              # the race (same as request_step)
            except (ConnectionRefusedError, FileNotFoundError):
                time.sleep(0.02)
        else:
            raise RuntimeError("could not connect to the exod socket")
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


# ── P2-T12 (exod-delegation): server-side credential injection in the confined limb ──────────────────

def test_exod_injects_grant_authorized_credentials_into_the_confined_step():
    """The limb resolves the GRANT's credential NAMES via its vault and injects them into the CONFINED step's
    profile env (→ bwrap --setenv after --clearenv) — never the agent, never govd. Ungranted creds absent."""
    isk, ipub = _kp()
    secret = "SEKRET-" + "z" * 16
    vault = _vaultmod.EnvStubVault({"api-key": secret, "other": "nope"})
    stub = _Stub(rc=0, out="x")
    exod = Exod(Ed25519PrivateKey.generate(), grant_issuer_pub=ipub, runner=stub, vault=vault)
    g = mint_grant(isk, run_id="R1", plan_sha="P1", nbf=990, exp=1100, nonce="g1", tier="trusted",
                   capabilities=["run"], credentials=["api-key"])           # only api-key is granted (trusted tier)
    env = exod.run_step(dict(run_id="R1", plan_sha="P1", step="1", argv=["x"], workspace="/ws", grant=g),
                        now=1000)
    assert result_body(env)["status"] == "ok"
    prof, _argv, _backend = stub.calls[-1]
    assert prof.env.get("CWS_SECRET_API_KEY") == secret                      # the granted secret reached the step
    assert _vaultmod.secret_bytes_in(prof.env, secret) == 1                  # exactly once, in the step env only
    assert "CWS_SECRET_OTHER" not in prof.env                                # the ungranted credential is NOT injected


def test_exod_refuses_when_credentials_granted_but_no_vault():
    """Fail closed: a grant that authorizes credentials but no vault is attached -> refuse, never run."""
    isk, ipub = _kp()
    exod = Exod(Ed25519PrivateKey.generate(), grant_issuer_pub=ipub, runner=_Stub())   # no vault
    g = mint_grant(isk, run_id="R1", plan_sha="P1", nbf=990, exp=1100, nonce="g1", tier="trusted",
                   capabilities=["run"], credentials=["api-key"])
    env = exod.run_step(dict(run_id="R1", plan_sha="P1", step="1", argv=["x"], workspace="/ws", grant=g),
                        now=1000)
    assert result_body(env)["status"] == "refused"


def test_exod_refuses_when_selected_backend_is_unavailable():
    """P2-T04 backend selection is FAIL-CLOSED: if the chosen confinement backend cannot enforce on this host
    (e.g. exod configured for runsc/gVisor but runsc is absent), exod REFUSES the step (signed), never runs it
    unconfined, and never crashes the limb."""
    import hashlib as _h

    import pytest

    from infra.exec.sandbox import runsc_available
    if runsc_available():
        pytest.skip("runsc present — this exercises the unavailable-backend refusal")
    isk, ipub = _kp()
    # the operator FLOOR is runsc — the real runner can't enforce gVisor on this host, so the step is refused
    exod = Exod(Ed25519PrivateKey.generate(), grant_issuer_pub=ipub, backend_floor="runsc")
    g = mint_grant(isk, run_id="R1", plan_sha="P1", nbf=990, exp=1100, nonce="g1", capabilities=["run"])
    env = exod.run_step(dict(run_id="R1", plan_sha="P1", step="1", argv=["true"], workspace="/ws", grant=g),
                        now=1000)
    body = result_body(env)
    assert body["status"] == "refused"
    assert body["output_sha"] == _h.sha256(b"sandbox:unavailable").hexdigest()   # the right refusal reason


def test_exod_refuses_secrets_for_a_community_tier_grant():
    """P2-T04 no-secrets floor where secrets RESOLVE: a COMMUNITY-tier grant (the default) carrying credentials
    is refused by exod before any secret is touched — only a trusted-tier grant may resolve credentials."""
    isk, ipub = _kp()
    secret = "SEKRET-" + "z" * 16
    vault = _vaultmod.EnvStubVault({"api-key": secret})
    stub = _Stub(rc=0, out="x")
    exod = Exod(Ed25519PrivateKey.generate(), grant_issuer_pub=ipub, runner=stub, vault=vault)
    # community tier is the DEFAULT (no tier= passed) — requesting a credential must be refused
    g = mint_grant(isk, run_id="R1", plan_sha="P1", nbf=990, exp=1100, nonce="g1",
                   capabilities=["run"], credentials=["api-key"])
    env = exod.run_step(dict(run_id="R1", plan_sha="P1", step="1", argv=["x"], workspace="/ws", grant=g),
                        now=1000)
    import hashlib as _h
    body = result_body(env)
    # refused for the RIGHT reason: the tag is hashed into output_sha (value-free — the body never leaks text)
    assert body["status"] == "refused"
    assert body["output_sha"] == _h.sha256(b"tier:community_no_secrets").hexdigest()
    assert not stub.calls                                                     # the step never ran; no secret touched


def test_exod_no_credentials_runs_without_vault():
    """A grant with no credentials needs no vault — the step runs confined as before (back-compat)."""
    isk, ipub = _kp()
    exod = Exod(Ed25519PrivateKey.generate(), grant_issuer_pub=ipub, runner=_Stub(rc=0, out="x"))
    env = exod.run_step(_req(isk), now=1000)                                  # _req mints a no-credentials grant
    assert result_body(env)["status"] == "ok"


def test_grant_sandbox_tier_selects_the_backend():
    """P3-T11 — tier_enforced_at_grant: the grant's `sandbox_tier` deterministically selects the confinement
    backend exod hands the runner. A community grant DEMANDS gVisor (runsc); core/undeclared takes the operator
    floor (bwrap); and the floor is MONOTONE — a runsc floor is never downgraded by a core grant."""
    isk, ipub = _kp()
    seen = []

    def rec(profile, argv, backend=None):
        seen.append(backend)
        return subprocess.CompletedProcess(argv, 0, "ok", "")

    def mk(stier, n):
        return mint_grant(isk, run_id="R1", plan_sha="P1", nbf=990, exp=1100, nonce="g-" + n,
                          capabilities=["run"], sandbox_tier=stier)

    exod = Exod(Ed25519PrivateKey.generate(), grant_issuer_pub=ipub, runner=rec, backend_floor="bwrap")
    for stier, want, n in (("community", "runsc", "c"), ("core", "bwrap", "k"), (None, "bwrap", "u")):
        seen.clear()
        env = exod.run_step(dict(run_id="R1", plan_sha="P1", step="1", argv=["true"], workspace="/ws",
                                 grant=mk(stier, n)), now=1000)
        assert result_body(env)["status"] == "ok"
        assert seen == [want], (stier, seen)                       # the tier picked the backend, at the grant

    # the operator floor only ratchets UP: a runsc-floored limb never downgrades a core grant to bwrap
    hardened = Exod(Ed25519PrivateKey.generate(), grant_issuer_pub=ipub, runner=rec, backend_floor="runsc")
    seen.clear()
    hardened.run_step(dict(run_id="R1", plan_sha="P1", step="1", argv=["true"], workspace="/ws",
                           grant=mk("core", "h")), now=1000)
    assert seen == ["runsc"]                                        # monotone floor — never weakened


def test_sandbox_tier_selftest_passes():
    """The pure tier→backend selection logic (P3-T11): community→runsc, trusted family→bwrap, monotone floor."""
    from infra.exec.sandbox import tier_backend_selftest
    r = tier_backend_selftest()
    assert r["ok"], r


def test_load_vault_dispatches_each_kind():
    """load_vault: the spec KIND selects the backend — file->FileVault, sops->SopsAgeVault (age key split on
    '#'), empty->None (fail-closed later, at secret resolution), unknown->SystemExit. Pins the kind
    comparisons so a flipped == cannot silently mis-dispatch a vault spec."""
    from infra.exec.exod import load_vault
    assert load_vault(None) is None and load_vault("") is None
    fv = load_vault("file:/run/secrets.json")
    assert isinstance(fv, _vaultmod.FileVault) and fv.path == "/run/secrets.json"
    sv = load_vault("sops:/run/enc.json#/run/age.key")
    assert isinstance(sv, _vaultmod.SopsAgeVault) and sv.path == "/run/enc.json" and sv.age_key_file == "/run/age.key"
    sv2 = load_vault("sops:/run/enc.json")                       # no '#': the age key file stays None
    assert isinstance(sv2, _vaultmod.SopsAgeVault) and sv2.age_key_file is None
    with pytest.raises(SystemExit):
        load_vault("hashicorp:/whatever")


def test_main_backend_floor_warning_tracks_the_selected_backend(tmp_path, monkeypatch, capsys):
    """The startup floor check consults the availability probe FOR THE CONFIGURED backend (runsc floor ->
    runsc_available, bwrap floor -> is_available). Pins the selector so a flipped comparison cannot warn on
    the wrong probe (or stay silent when the actual floor is unenforceable)."""
    from cryptography.hazmat.primitives import serialization as _ser
    from infra.exec import exod as exod_mod
    raw_priv = lambda k: k.private_bytes(_ser.Encoding.Raw, _ser.PrivateFormat.Raw, _ser.NoEncryption())
    raw_pub = lambda k: k.public_key().public_bytes(_ser.Encoding.Raw, _ser.PublicFormat.Raw)
    key = tmp_path / "exod.key"; key.write_bytes(raw_priv(Ed25519PrivateKey.generate()))
    ipub = tmp_path / "issuer.pub"; ipub.write_bytes(raw_pub(Ed25519PrivateKey.generate()))
    monkeypatch.setattr(exod_mod.Exod, "serve", lambda self, sock: None)   # never enter the UDS loop
    argv = ["--key", str(key), "--issuer-pub", str(ipub), "--socket", str(tmp_path / "exod.sock")]
    # runsc floor, runsc enforceable (bwrap NOT): the runsc probe answers -> NO warning
    monkeypatch.setattr(exod_mod, "runsc_available", lambda: True)
    monkeypatch.setattr(exod_mod, "is_available", lambda: False)
    exod_mod.main(argv + ["--backend", "runsc"])
    assert "NOT enforceable" not in capsys.readouterr().err
    # bwrap floor on the same host: the bwrap probe answers -> warning (fail-closed refusals ahead)
    exod_mod.main(argv + ["--backend", "bwrap"])
    assert "NOT enforceable" in capsys.readouterr().err
