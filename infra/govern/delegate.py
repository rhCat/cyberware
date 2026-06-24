#!/usr/bin/env python3
"""infra/govern/delegate.py — govd-side server-side-execution delegation (P2-T12, the containment wiring).

In DELEGATED exec mode, govd does NOT run the step (its "never executes" invariant holds): on a WS step it
mints a single-use capability grant (govd's grant-issuer key), materializes a per-run CONFINED workspace from
its OWN trusted registry (the blessed wrapper + a copy of the perk src closure — the agent never provides or
touches any of it), and hands the grant + workspace to EXOD the limb over the UDS. exod runs the step
confined (bwrap, nobody, no net) and returns its SIGNED status-only result; govd verifies that signature
(exodverify) + a durable per-run replay guard and records exod's authoritative status — never the agent's
self-report. A forged/unverifiable result is recorded as evidence; an unreachable limb refuses the step
(fail-closed). The real bwrap confinement runs on the exec image; the channel logic is platform-agnostic.
"""
from __future__ import annotations
import os
import secrets
import shutil
import time

from infra import registry as _reg
from infra.exec import exod
from infra.exec import grants
from infra.exec.exodverify import _principal, result_body, verify_step_result


def materialize_workspace(rec, base, registry=None):
    """Build a per-run confined workspace SERVER-SIDE from govd's own trusted registry: the blessed wrapper +
    a COPY of the perk src closure (SNIP) + the record-store dir. Returns (workspace, env, run_sh)."""
    ws = os.path.join(base, rec["run_id"])
    snip, store = os.path.join(ws, "snip"), os.path.join(ws, "rec")
    os.makedirs(snip, exist_ok=True)
    os.makedirs(store, exist_ok=True)
    run_sh = os.path.join(ws, "run.sh")
    with open(run_sh, "w") as f:
        f.write(rec.get("wrapper") or "")
    os.chmod(run_sh, 0o755)
    src = os.path.join(_reg.skill_dir(rec["skill"], registry), "perks", rec["perk"], "src")
    if os.path.isdir(src):
        for name in os.listdir(src):
            sp = os.path.join(src, name)
            if os.path.isfile(sp):
                shutil.copy2(sp, os.path.join(snip, name))
    env = {"PATH": "/usr/bin:/bin:/usr/sbin:/sbin", "SNIP": snip, "RECORD_STORE": store}
    return ws, env, run_sh


def execute_step(rec, step, plan_sha, *, exod_socket, grant_key, exod_pub, base, registry=None,
                 request=exod.request_step, now=None, grant_ttl=60):
    """Delegate ONE step to exod. Returns (reply, event): `reply` is the status-only dict sent back to the
    agent; `event` is the ledger record to append (exod's signed step_result, or a refusal record, or None
    when nothing should be recorded). govd NEVER runs the step — exod does, confined.

    govd mints the grant pinning the perk's whole blessed src closure (snippet_shas) and hands exod the
    materialized workspace; exod ITSELF re-derives the digest of every staged file at time of use and refuses
    a swap, so govd does not attest to its own copy — the integrity check is exod's, against the signed pin."""
    now = int(time.time()) if now is None else now
    ws, env, run_sh = materialize_workspace(rec, base, registry)
    nonce = secrets.token_urlsafe(18)
    # P2-T04 tier: a grant that carries credentials is minted at the TRUSTED tier (govd authorized those
    # credentials from the plan); a credential-free grant stays at the COMMUNITY floor. exod refuses to resolve
    # a secret for any non-trusted grant, so a credentialed grant that is NOT trusted-tier (a malformed/foreign
    # grant) is rejected at the secret-resolution boundary.
    creds = rec.get("credential_ids") or []
    grant = grants.mint_grant(grant_key, run_id=rec["run_id"], plan_sha=plan_sha,
                              snippet_shas=rec.get("snippet_shas") or {}, capabilities=["run"],
                              credentials=creds, tier=("trusted" if creds else "community"),
                              nbf=now - 5, exp=now + grant_ttl, nonce=nonce)
    req = {"run_id": rec["run_id"], "plan_sha": plan_sha, "step": step,
           "argv": ["bash", run_sh, "--step", step], "workspace": ws, "env": env, "grant": grant}
    try:
        envl = request(exod_socket, req)
    except Exception:
        return {"status": "refused", "reason": "exod_unreachable"}, None
    ok, why = verify_step_result(exod_pub, envl, expect_run_id=rec["run_id"], expect_plan_sha=plan_sha)
    if not ok:
        return ({"status": "refused", "reason": "exod_verify:" + why},
                {"type": "forged_status_refused", "step": step, "reason": why, "authority": "exod"})
    body = result_body(envl)
    seen = {e.get("result_nonce") for e in (rec.get("events") or []) if e.get("result_nonce")}
    if body.get("nonce") in seen:                                    # durable per-run replay guard
        return {"status": "refused", "reason": "result_replay"}, None
    status = body.get("status")
    # a step exod RAN (ok/error) is a terminal step_result that consumes the step's at-most-once budget; a
    # step exod REFUSED (closure mismatch, vault unavailable, ...) never ran, so it is recorded under a
    # DISTINCT type — audited as evidence, yet outside the done-set, so a transient refusal can be retried
    # rather than wedging the run.
    etype = "step_result" if status in ("ok", "error") else "step_delegation_refused"
    event = {"type": etype, "step": step, "status": status, "exit": body.get("exit"),
             "authority": "exod", "exod_keyid": _principal(exod_pub), "meter": exod.meter_of(envl),
             "result_nonce": body.get("nonce")}
    return {"status": status, "exit": body.get("exit"), "authority": "exod"}, event
