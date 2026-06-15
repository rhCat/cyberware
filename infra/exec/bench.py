#!/usr/bin/env python3
"""infra/exec/bench.py — the channel/sandbox overhead meter (P2-T09 cws-bench, over P2-T07's attested meters).

Drives N benign steps through exod into the bwrap SandboxProfile and reads exod's OWN signed meter for each
(never the agent's stopwatch), then reports the per-step wall-time distribution against the plan's budget.

  * the bwrap budget (p95 <= 100 ms/step) is measurable wherever bwrap runs;
  * the microVM budgets (cold <= 1500 ms, warm <= 250 ms) need /dev/kvm + a microVM backend. On a host
    without nested virtualization there is none, so `bench_microvm` reports `skipped` — the budget is left
    HONESTLY unmet, never faked.
"""
from __future__ import annotations
import os

from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

from infra.exec.exod import Exod, meter_of
from infra.exec.exodverify import result_body, verify_step_result
from infra.exec.grants import mint_grant
from infra.exec.sandbox import is_available

BWRAP_P95_BUDGET_MS = 100
MICROVM_COLD_BUDGET_MS = 1500
MICROVM_WARM_BUDGET_MS = 250


def _percentile(xs, q):
    s = sorted(xs)
    if not s:
        return None
    i = min(len(s) - 1, max(0, round((q / 100.0) * (len(s) - 1))))
    return s[i]


def bench_bwrap(n: int = 30, workspace: str | None = None) -> dict:
    """Run `n` benign steps through exod+sandbox, collecting exod's ATTESTED wall_ms per step. Returns the
    distribution + whether p95 is within budget. `within` is None when the boundary is unavailable."""
    if not is_available():
        return {"backend": "bwrap", "skipped": "kernel sandbox unavailable (need Linux + bwrap)",
                "within": None}
    import tempfile
    ws = workspace or tempfile.mkdtemp()
    os.chmod(ws, 0o777)
    issuer = Ed25519PrivateKey.generate()
    exod = Exod(Ed25519PrivateKey.generate(), grant_issuer_pub=issuer.public_key())
    samples = []
    for i in range(n):
        grant = mint_grant(issuer, run_id="bench", plan_sha="bench", nbf=0, exp=10**12,
                           nonce=f"g{i}", capabilities=["run"])
        req = {"run_id": "bench", "plan_sha": "bench", "step": str(i),
               "argv": ["bash", "-lc", "true"], "workspace": ws, "nonce": f"r{i}", "grant": grant}
        env = exod.run_step(req, now=1000)
        ok, _ = verify_step_result(exod.public_key, env, expect_run_id="bench")
        assert ok and result_body(env)["status"] == "ok"
        samples.append(meter_of(env)["wall_ms"])          # exod-attested, not measured by us
    p95 = _percentile(samples, 95)
    return {"backend": "bwrap", "n": n, "p50": _percentile(samples, 50), "p95": p95,
            "max": max(samples), "budget_ms": BWRAP_P95_BUDGET_MS, "within": p95 <= BWRAP_P95_BUDGET_MS}


def has_kvm() -> bool:
    return os.path.exists("/dev/kvm")


def bench_microvm() -> dict:
    """The microVM backend (Firecracker/cloud-hypervisor) needs /dev/kvm. Without it there is nothing to
    time — reported skipped, the budgets left honestly unmet."""
    if not has_kvm():
        return {"backend": "microvm", "skipped": "no /dev/kvm (no nested virtualization / microVM backend)",
                "cold_budget_ms": MICROVM_COLD_BUDGET_MS, "warm_budget_ms": MICROVM_WARM_BUDGET_MS,
                "within": None}
    # a microVM backend is not built yet; when one lands, time a cold boot + a warm reuse here.
    return {"backend": "microvm", "skipped": "microVM backend not built", "within": None}
