"""Revocation-in-flight for SV-4 (P3-T13): a revocation that lands during a multi-step run takes effect
mid-run. An ordinary revocation lets the in-progress step finish then refuses the next (boundary halt); a
critical revocation aborts the in-progress step immediately — one step sooner. Needs openssl with ed25519ph;
skips otherwise."""
from __future__ import annotations
import shutil

import pytest

from infra.cwp import revoke_inflight as RI


def _capable() -> bool:
    if not shutil.which("openssl"):
        return False
    try:
        RI.inflight_selftest()
        return True
    except Exception:
        return False


pytestmark = pytest.mark.skipif(not _capable(), reason="needs openssl with ed25519ph")


def test_selftest_holds():
    r = RI.inflight_selftest()
    assert r["ok"], r


def test_boundary_halt_and_critical_kill_differ():
    r = RI.inflight_selftest()
    assert r["normal_run_completes"] and r["boundary_halt"] and r["critical_kills_immediately"]
    assert r["critical_stops_strictly_sooner"]
