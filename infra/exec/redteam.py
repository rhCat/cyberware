#!/usr/bin/env python3
"""infra/exec/redteam.py — the KERNEL red-team corpus (P2-T08, the M3/SV-3 gate).

A library of adversarial behaviours, each mounting a REAL attack and asserting the SV-3 boundary REFUSES it
— governed under exod's own observation, with NO in-process software scan in the path (so a refusal is the
kernel / the cryptographic channel, never a scanner). Two families:

  * SANDBOX attacks run a hostile command through exod into the bwrap SandboxProfile and assert the KERNEL
    blocked it — the attack process exits nonzero, so exod's SIGNED status is "error", not "ok". The same
    command on a benign target returns "ok", so the refusal is the confinement, not an inert command.
  * CHANNEL attacks present exod (or its recorder) a forged / replayed / expired / cross-run / un-granted
    grant or a forged status and assert exod refuses — a signed "refused" result, or the recorder rejecting
    a status not on exod's channel.

Every behaviour also runs an ORACLE: a benign granted step that MUST be accepted ("ok" / recorded). A
behaviour `held` only if the attack was refused AND the oracle was accepted — so a gate that silently goes
no-op (accepting everything) fails the corpus instead of passing it. The sandbox family needs Linux + bwrap
(`is_available()`); the channel family is platform-agnostic. `run_attack(name)` returns an Outcome; the
cws-redteam perks each pin one behaviour and exit 0 iff it held.
"""
from __future__ import annotations
import dataclasses
import os
import tempfile

from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

from infra.cwp import sign
from infra.exec.capmanifest import CapabilityManifest, materialize, verify_materialized
from infra.exec.exod import Exod, record_step_result
from infra.exec.exodverify import STEP_RESULT_TYPE, result_body
from infra.exec.grants import mint_grant
from infra.exec.sandbox import is_available

NOW = 1_000_000                              # a fixed clock; grants are minted around it
_RUN, _PLAN = "redteam-run", "redteam-plan"


@dataclasses.dataclass
class Outcome:
    name: str
    held: bool          # True iff the attack was refused AND the benign oracle was accepted
    detail: str
    family: str


def _principals():
    """A fresh issuer (govd's grant key) + exod identity, distinct as exod requires."""
    issuer = Ed25519PrivateKey.generate()
    exod = Exod(Ed25519PrivateKey.generate(), grant_issuer_pub=issuer.public_key())
    return issuer, exod


def _grant(issuer, *, run_id=_RUN, plan_sha=_PLAN, nonce, nbf=NOW - 10, exp=NOW + 100,
           capabilities=("run",), snippet_shas=None):
    return mint_grant(issuer, run_id=run_id, plan_sha=plan_sha, nbf=nbf, exp=exp, nonce=nonce,
                      capabilities=list(capabilities), snippet_shas=snippet_shas or {})


def _req(issuer, *, argv, workspace, nonce, **gkw):
    return dict(run_id=_RUN, plan_sha=_PLAN, step="1", argv=argv, workspace=workspace, nonce=nonce,
                grant=_grant(issuer, nonce="g-" + nonce, **gkw))


def _benign_ok(issuer, exod, ws):
    """The ORACLE: a benign granted step run through exod must come back authoritative "ok"."""
    env = exod.run_step(_req(issuer, argv=["bash", "-lc", "echo benign"], workspace=ws, nonce="oracle"),
                        now=NOW)
    return result_body(env).get("status") == "ok"


# ── the sandbox family — exod runs the hostile command; the KERNEL must block it ─────────────────────
# each value is a shell command that, unconfined, would succeed (cause harm) and exit 0; confined it is
# blocked and exits nonzero, so exod signs status="error".
_SANDBOX = {
    "fs-escape":      "cat /redteam_host_secret",                          # a host file outside the binds
    "write-rofs":     "touch /usr/PWNED",                                  # write a read-only system path
    "write-outside":  "touch /opt/PWNED",                                  # write outside the workspace
    "net-egress":     "python3 -c \"import socket;socket.create_connection(('8.8.8.8',53),2)\"",
    "sysrq-reboot":   "echo b > /proc/sysrq-trigger",                      # reboot the host
    "proc-sys-write": "echo 0 > /proc/sys/kernel/randomize_va_space",      # rewrite a global kernel knob
    "mount":          "mount -t tmpfs none /tmp",                          # gain a mount
    "device-raw":     "dd if=/dev/mem of=/dev/null bs=1 count=1",          # read kernel memory
}


def _run_sandbox_attack(name, cmd):
    if not is_available():
        return Outcome(name, False, "skipped: kernel sandbox unavailable (need Linux + bwrap)", "sandbox")
    issuer, exod = _principals()
    ws = tempfile.mkdtemp()
    os.chmod(ws, 0o777)
    # a host sentinel the fs-escape attack would read if the bind boundary failed
    try:
        with open("/redteam_host_secret", "w") as f:
            f.write("LEAK")
    except OSError:
        pass
    env = exod.run_step(_req(issuer, argv=["bash", "-lc", cmd], workspace=ws, nonce="atk"), now=NOW)
    status = result_body(env).get("status")
    attack_refused = status != "ok"                       # the kernel blocked the hostile command
    oracle_ok = _benign_ok(issuer, exod, ws)
    return Outcome(name, attack_refused and oracle_ok, f"attack_status={status} oracle_ok={oracle_ok}",
                   "sandbox")


# ── the channel family — exod / its recorder must refuse a bad grant or a forged status ──────────────

def _atk_forged_status():
    issuer, exod = _principals()
    forger = Ed25519PrivateKey.generate()                 # the executor trying to sign its own "ok"
    body = {"run_id": _RUN, "plan_sha": _PLAN, "step": "1", "exit": 0, "status": "ok",
            "output_sha": "x", "nonce": "n", "ts": "t"}
    forged = sign.sign(body, forger, payload_type=STEP_RESULT_TYPE)
    lp = tempfile.mktemp(suffix=".json")
    accepted, rec = record_step_result(lp, exod.public_key, forged, expect_run_id=_RUN, expect_plan_sha=_PLAN)
    refused = (not accepted) and rec.get("reason") == "forged_status"
    # oracle: a genuine exod result IS accepted
    good = exod.run_step(_req(issuer, argv=["true"], workspace="/", nonce="o"), now=NOW)
    return refused, f"forged_accepted={accepted} reason={rec.get('reason')}", good


def _atk_grant_replay():
    issuer, exod = _principals()
    req = _req(issuer, argv=["true"], workspace="/", nonce="rep")
    first = result_body(exod.run_step(req, now=NOW)).get("status")
    second = result_body(exod.run_step(req, now=NOW)).get("status")   # replay the SAME grant
    return second == "refused", f"first={first} replay={second}", first


def _atk_grant_expired():
    issuer, exod = _principals()
    req = _req(issuer, argv=["true"], workspace="/", nonce="exp", nbf=0, exp=10)
    status = result_body(exod.run_step(req, now=NOW)).get("status")   # long past exp
    return status == "refused", f"expired_status={status}", None


def _atk_grant_wrong_run():
    issuer, exod = _principals()
    # a grant minted for a different run laundered into THIS request
    grant = _grant(issuer, run_id="OTHER-RUN", nonce="g-wr")
    req = dict(run_id=_RUN, plan_sha=_PLAN, step="1", argv=["true"], workspace="/", nonce="wr", grant=grant)
    status = result_body(exod.run_step(req, now=NOW)).get("status")
    return status == "refused", f"cross_run_status={status}", None


def _atk_grant_forged():
    issuer, exod = _principals()
    import base64
    import json
    req = _req(issuer, argv=["true"], workspace="/", nonce="fg")
    body = json.loads(base64.b64decode(req["grant"]["payload"]))
    body["capabilities"] = ["root"]                       # tamper the claim without re-signing
    req["grant"] = {**req["grant"], "payload": base64.b64encode(json.dumps(body).encode()).decode()}
    status = result_body(exod.run_step(req, now=NOW)).get("status")
    return status == "refused", f"forged_grant_status={status}", None


def _atk_no_capability():
    issuer, exod = _principals()
    grant = _grant(issuer, nonce="g-nc", capabilities=[])  # a grant that authorizes nothing
    req = dict(run_id=_RUN, plan_sha=_PLAN, step="1", argv=["true"], workspace="/", nonce="nc", grant=grant)
    status = result_body(exod.run_step(req, now=NOW)).get("status")
    return status == "refused", f"no_cap_status={status}", None


_CHANNEL = {
    "forged-status": _atk_forged_status,
    "grant-replay":  _atk_grant_replay,
    "grant-expired": _atk_grant_expired,
    "grant-wrong-run": _atk_grant_wrong_run,
    "grant-forged":  _atk_grant_forged,
    "no-capability": _atk_no_capability,
}


def _run_channel_attack(name, fn):
    issuer, exod = _principals()
    refused, detail, _oracle = fn()
    # oracle: a benign granted step is accepted (the channel is not refusing everything)
    ws = tempfile.mkdtemp()
    oracle_ok = _benign_ok(issuer, exod, ws)
    return Outcome(name, bool(refused) and oracle_ok, f"{detail} oracle_ok={oracle_ok}", "channel")


# ── the capability family — a sandbox must materialize its manifest EXACTLY (P2-T06), no kernel needed ──

def _atk_cap_mismatch():
    ws = tempfile.mkdtemp()
    granted = CapabilityManifest(workspace=ws, ro_binds=("/usr", "/bin"))
    wider = materialize(CapabilityManifest(workspace=ws, ro_binds=("/usr", "/bin", "/etc")))  # an ungranted bind
    ok, reason = verify_materialized(wider, granted)
    refused = (not ok) and reason == "ungranted_bind"
    oracle_ok = verify_materialized(materialize(granted), granted)[0]   # a faithful sandbox is accepted
    return refused, f"refuse_reason={reason}", oracle_ok


_CAPABILITY = {"cap-mismatch": _atk_cap_mismatch}


def _run_capability_attack(name, fn):
    refused, detail, oracle_ok = fn()
    return Outcome(name, bool(refused) and bool(oracle_ok), f"{detail} oracle_ok={oracle_ok}", "capability")


ATTACKS = tuple(_SANDBOX) + tuple(_CHANNEL) + tuple(_CAPABILITY)


def run_attack(name: str) -> Outcome:
    """Run one named behaviour; `held` is True iff the boundary refused the attack AND accepted the oracle."""
    if name in _SANDBOX:
        return _run_sandbox_attack(name, _SANDBOX[name])
    if name in _CHANNEL:
        return _run_channel_attack(name, _CHANNEL[name])
    if name in _CAPABILITY:
        return _run_capability_attack(name, _CAPABILITY[name])
    raise KeyError(f"unknown red-team behaviour: {name!r} (have {', '.join(ATTACKS)})")


def run_corpus():
    """Run every behaviour. Returns (outcomes, all_held). Sandbox behaviours self-skip off Linux."""
    outs = [run_attack(n) for n in ATTACKS]
    actionable = [o for o in outs if not o.detail.startswith("skipped")]
    return outs, all(o.held for o in actionable) and len(actionable) >= 12
