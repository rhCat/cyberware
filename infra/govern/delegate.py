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
import json
import os
import secrets
import shutil
import time

from infra import registry as _reg
from infra.exec import exod
from infra.exec import grants
from infra.exec import sandbox as _sandbox
from infra.exec.exodverify import _principal, result_body, verify_step_result


def perk_sandbox_tier(skill, perk, registry=None):
    """The perk's DECLARED catalog sandbox tier (core/verified/community), read from the registry's perks.json,
    or None when undeclared (P3-T11). It selects the confinement BACKEND at the limb: a perk that declares
    `community` is gVisor-confined; an undeclared perk takes the operator floor (no regression). An
    UNRECOGNIZED declared tier is treated as `community` (fail-safe — the strongest box for a tier we cannot
    vouch for). Names/hashes only ever cross the wire; this reads govd's OWN trusted registry."""
    if not skill or not perk:
        return None
    pj = os.path.join(_reg.skill_dir(skill, registry), "perks.json")
    if not os.path.isfile(pj):
        return None
    try:
        perks = (json.load(open(pj)) or {}).get("perks", [])
    except Exception:
        return None
    for p in perks:
        if p.get("id") == perk:
            t = p.get("tier")
            if t is None:
                return None
            return t if t in _sandbox.SANDBOX_TIERS else "community"
    return None


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
                 request=exod.request_step, now=None, grant_ttl=60, attestation=None):
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
    # P3-T11: the perk's declared catalog tier flows into the grant's sandbox_tier — exod uses it to select the
    # confinement backend (community → gVisor/runsc; trusted family → bwrap; undeclared → the operator floor).
    # Orthogonal to the SECRET tier above: a credentialed grant is still minted trusted regardless of backend.
    # ACL M1: bind the per-actor ACL digest + the canonical claim into the grant — ALL-OR-NOTHING, gated on
    # acl_sha. An UNSCOPED (non-ACL'd) actor's rec has no acl_sha, so NONE of acl_sha/skill/perk/destructive is
    # passed and the grant body stays BYTE-IDENTICAL to the pre-ACL form (exod skips its acl check when acl_sha
    # is absent, so it never needs them). For an ACL'd actor all four travel together; exod JOINs acl_sha
    # against the operator attestation and re-runs acl_allows on skill/perk/destructive, enforcing off-node.
    acl_sha = rec.get("acl_sha")
    grant = grants.mint_grant(grant_key, run_id=rec["run_id"], plan_sha=plan_sha,
                              snippet_shas=rec.get("snippet_shas") or {}, capabilities=["run"],
                              credentials=creds, tier=("trusted" if creds else "community"),
                              sandbox_tier=perk_sandbox_tier(rec.get("skill"), rec.get("perk"), registry),
                              acl_sha=acl_sha,
                              skill=rec.get("skill") if acl_sha else None,
                              perk=rec.get("perk") if acl_sha else None,
                              destructive=rec.get("destructive") if acl_sha else None,
                              nbf=now - 5, exp=now + grant_ttl, nonce=nonce)
    # the operator attestation (held + relayed by the agent) rides verbatim to exod; govd holds neither the
    # operator key nor the client proof key, so it cannot forge it — it only relays what the agent presents.
    req = {"run_id": rec["run_id"], "plan_sha": plan_sha, "step": step,
           "argv": ["bash", run_sh, "--step", step], "workspace": ws, "env": env, "grant": grant,
           "attestation": attestation}
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
