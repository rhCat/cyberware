#!/usr/bin/env python3
"""infra/cwp/revoke_inflight.py — revocation-in-flight enforcement (P3-T13, SV-4 / M9).

A revocation that lands while a multi-step governed run is executing must take effect *during* the run, not
only at the next launch. The in-flight runner consults the signed revocation feed (P3-T03) at every step
boundary, and two policies bound the blast radius:

  * **boundary halt** (ordinary revocation) — a step already in progress under its existing grant is allowed
    to finish, but the *next* `step_request` is refused; the run halts cleanly.
  * **critical kill** (critical revocation) — the in-progress step is aborted immediately, mid-flight; the
    run does not wait for the boundary.

So a critical revocation always stops one step earlier than an ordinary one arriving at the same moment —
that gap is the observable proof that critical "kills immediately". The decision is the real feed gate:
`revocation.revocation_decision`, so a stale or rolled-back feed fails closed here too.
"""
from __future__ import annotations
import os

from infra.cwp import revocation

_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
PINNED_ROOT = os.path.join(_ROOT, "spec", "tuf", "publisher-root.pub")


def run_inflight(n_steps: int, artifact_id: str, clean_feed: dict, revoke_feed: dict, effective_at: int,
                 now: int, pinned_pub_pem: str, critical: bool = False, last_seq: int = 0) -> dict:
    """Execute `n_steps`, consulting the revocation feed at each boundary. `effective_at` is the step during
    whose execution the revocation lands (the feed is clean through that boundary, then revoking). Returns
    {status, completed, refused_next?}: status ∈ {completed, halted_revoked, killed_critical}."""
    completed = 0
    for i in range(n_steps):
        feed = revoke_feed if i > effective_at else clean_feed
        if not revocation.revocation_decision(feed, artifact_id, now, last_seq=last_seq,
                                              pinned_pub_pem=pinned_pub_pem)["allow"]:
            return {"status": "halted_revoked", "completed": completed, "refused_next": True}
        if i == effective_at and critical:                     # revocation arrives mid-step
            if not revocation.revocation_decision(revoke_feed, artifact_id, now, last_seq=last_seq,
                                                  pinned_pub_pem=pinned_pub_pem)["allow"]:
                return {"status": "killed_critical", "completed": completed}   # current step aborted
        completed += 1                                          # the in-progress step finished
    return {"status": "completed", "completed": completed}


def inflight_selftest() -> dict:
    """A hermetic P3-T13 demonstration with an EPHEMERAL key and a fixed clock: a clean run completes all
    steps; an ordinary revocation arriving during step 2 lets that step finish then refuses the next
    (boundary halt); a CRITICAL revocation arriving at the same moment aborts step 2 immediately — one step
    earlier than the boundary halt. `ok` iff all three hold and critical stops strictly sooner. Needs openssl.
    """
    import subprocess
    import tempfile
    d = tempfile.mkdtemp(prefix="inflight-")
    priv, pub = os.path.join(d, "p.key"), os.path.join(d, "p.pub")
    subprocess.run(["openssl", "genpkey", "-algorithm", "ed25519", "-out", priv], check=True, capture_output=True)
    subprocess.run(["openssl", "pkey", "-in", priv, "-pubout", "-out", pub], check=True, capture_output=True)
    T0 = 1_700_000_000
    art = "sha256:" + "a" * 64
    clean = revocation.sign_feed(1, [], T0, 3600, priv)
    revoke = revocation.sign_feed(2, [art], T0, 3600, priv)
    N, EFF = 5, 2

    normal = run_inflight(N, art, clean, clean, N, T0 + 1, pub, last_seq=0)
    boundary = run_inflight(N, art, clean, revoke, EFF, T0 + 1, pub, critical=False, last_seq=0)
    crit = run_inflight(N, art, clean, revoke, EFF, T0 + 1, pub, critical=True, last_seq=0)

    normal_completes = normal["status"] == "completed" and normal["completed"] == N
    boundary_halt = (boundary["status"] == "halted_revoked" and boundary.get("refused_next") is True
                     and boundary["completed"] == EFF + 1)
    critical_kill = crit["status"] == "killed_critical" and crit["completed"] == EFF
    critical_sooner = crit["completed"] < boundary["completed"]

    return {"normal_run_completes": normal_completes, "boundary_halt": boundary_halt,
            "critical_kills_immediately": critical_kill, "critical_stops_strictly_sooner": critical_sooner,
            "tuf_root_pinned": os.path.isfile(PINNED_ROOT),
            "ok": (normal_completes and boundary_halt and critical_kill and critical_sooner
                   and os.path.isfile(PINNED_ROOT))}
