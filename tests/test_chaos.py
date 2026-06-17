"""Fault-injection drills for V-CHAOS (P2-T10 + P6-T17): a govd↔exod partition refuses the next step closed
and resumes idempotently (zero dup records); an exod crash reaps the orphan sandbox, records an error (no
false pass), and the run stays resumable; a settle-engine crash mid-posting-set is all-or-nothing, replays
exactly once, and conserves value. Needs openssl with ed25519ph for the settle-crash drill; partition/crash
are pure stdlib."""
from __future__ import annotations
import shutil

import pytest

from infra import chaos as C


def test_partition_refuses_closed_and_resumes_idempotently():
    r = C.partition_drill()
    assert r["ok"] and r["running_step_completed"] and r["next_refused_closed"] and r["ws_resume_idempotent"]


def test_crash_exod_reaps_records_error_resumable():
    r = C.crash_exod_drill()
    assert r["ok"] and r["orphan_reaped"] and r["step_records_error"] and r["run_resumable"]
    assert r["no_false_pass"]


@pytest.mark.skipif(shutil.which("openssl") is None, reason="settle-crash drill needs openssl with ed25519ph")
def test_settle_crash_atomic_exactly_once_conserves():
    r = C.settle_crash_drill()
    assert r["ok"], r
    assert r["all_or_nothing"] and r["replay_exactly_once"] and r["conservation_holds_through_crash"]


@pytest.mark.skipif(shutil.which("openssl") is None, reason="needs openssl with ed25519ph")
def test_chaos_selftest():
    assert C.chaos_selftest()["ok"]
