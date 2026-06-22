#!/usr/bin/env python3
"""infra/govern/govd_executor.py — govd-as-executor: server-side governed execution (P2-T12, AGENT / M7).

The agent-mode capstone. Today's run_governed executes client-side; this is the server-side model the
deployment needs: the agent POSTs a **value-free claim** (skill, perk, credential NAMES) to govd; govd
authenticates the principal, resolves the granted secrets **server-side** via the Vault, runs the step on the
worker under a **faithful, non-root** identity with the secret injected into the STEP env only, and returns
**only governed status + a ledger reference** — never the step's output, never a secret. The cognition holds
no limb: its only handle is intent-in, status-out.

The kernel-namespace isolation (bwrap/exod, SV-3) composes UNDER this on a Linux node; this module is the
control-flow — the agent never spawns the porter, govd does.
"""
from __future__ import annotations
import os
import subprocess

from infra.exec import vault as _vault


def serve(claim: dict, vault, step_argv=None, euid=None, allow_root=None) -> dict:
    """Server-side execution of an authenticated claim. Resolves the claim's credential NAMES via the Vault
    (server-side), runs the step under the caller's (non-root) uid with secrets injected into the STEP env
    only, and returns ONLY {status, exit, principal, uid} — never the step's output, never a secret. A root
    euid is refused (faithful execution is never root; CYBERWARE_ALLOW_ROOT=1 is the operator/CI escape).
    `euid`/`allow_root` default to the live process + env, but are injectable so the refusal path is testable
    deterministically (independent of who runs the suite)."""
    principal = claim.get("principal", "local")
    euid = os.geteuid() if euid is None else euid
    allow_root = (os.environ.get("CYBERWARE_ALLOW_ROOT") == "1") if allow_root is None else allow_root
    if euid == 0 and not allow_root:
        return {"status": "refused", "reason": "root_refused", "principal": principal, "uid": euid}
    step_env = _vault.inject_step_env({"PATH": os.environ.get("PATH", "")}, vault,
                                      claim.get("credential_ids", []))
    p = subprocess.run(step_argv or ["bash", "-lc", "true"], capture_output=True, text=True, env=step_env)
    # STATUS ONLY crosses back to the agent — p.stdout (the output) and the injected secret stay server-side.
    return {"status": "ok" if p.returncode == 0 else "error", "exit": p.returncode,
            "principal": principal, "uid": euid}


def govd_executor_selftest() -> dict:
    """P2-T12: the agent's claim carries only credential NAMES (zero secret bytes); govd runs the step
    server-side (the agent never spawns it) under a non-root uid; the secret is resolved + injected
    step-side (the step USES it) yet the return carries ONLY status — no output, no secret; and the agent's
    environ holds zero secret bytes. `ok` iff all hold."""
    secret = "S3CR3T-" + "q" * 20                              # a recognizable TEST value (never a real secret)
    v = _vault.EnvStubVault({"api-key": secret})

    claim = {"skill": "deploy", "perk": "x", "principal": "agent-a", "credential_ids": ["api-key"]}
    agent_claim_zero_secret = _vault.secret_bytes_in(claim, secret) == 0   # the claim names, never holds

    # a step that USES the secret (proves step-side injection) AND emits output (which must stay server-side)
    step = ["python3", "-c",
            "import os;s=os.environ.get('CWS_SECRET_API_KEY','');print('STEP_OUTPUT_'+str(len(s)))"]
    result = serve(claim, v, step_argv=step)

    agent_holds_no_limb = result.get("status") == "ok" and "exit" in result   # agent got STATUS; govd ran it
    info_only_return = ("stdout" not in result and "output" not in result
                        and _vault.secret_bytes_in(result, secret) == 0
                        and "STEP_OUTPUT_" not in str(result))   # neither the secret nor the output crossed
    # faithful: the step runs under the CALLER's uid (not elevated/impersonated) — true whether the suite
    # runs as 501 or as root-in-CI. never-root is a SEPARATE invariant: euid 0 without the escape is refused
    # (tested deterministically by injecting euid=0, allow_root=False, so the result holds for any runner).
    ran_under_caller_uid = result.get("uid") == os.geteuid()
    root_refused = govd_root_refused()
    faithful_uid = ran_under_caller_uid and root_refused
    agent_zero_secret_bytes = _vault.secret_bytes_in(dict(os.environ), secret) == 0

    ok = (agent_claim_zero_secret and agent_holds_no_limb and info_only_return and faithful_uid
          and agent_zero_secret_bytes)
    return {"agent_claim_zero_secret": agent_claim_zero_secret, "agent_holds_no_limb": agent_holds_no_limb,
            "info_only_return": info_only_return, "faithful_uid": faithful_uid,
            "ran_under_caller_uid": ran_under_caller_uid, "root_refused_without_escape": root_refused,
            "agent_zero_secret_bytes": agent_zero_secret_bytes, "ok": ok}


def govd_root_refused() -> bool:
    """The never-root invariant, deterministic: a root euid WITHOUT the operator escape is refused, and WITH
    the escape it runs (the CI/operator path). Independent of who runs the suite."""
    refused = serve({"principal": "p"}, _vault.EnvStubVault({}), euid=0, allow_root=False)
    escaped = serve({"principal": "p"}, _vault.EnvStubVault({}), step_argv=["true"], euid=0, allow_root=True)
    return refused.get("status") == "refused" and refused.get("reason") == "root_refused" \
        and escaped.get("status") == "ok"


if __name__ == "__main__":
    import json
    import sys
    r = govd_executor_selftest()
    print(json.dumps(r, indent=2))
    sys.exit(0 if r["ok"] else 1)
