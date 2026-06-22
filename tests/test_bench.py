"""cws-bench (P2-T09): the sandbox/channel overhead meter, over exod's attested meters (P2-T07).

The bwrap budget (p95 <= 100 ms/step) is measured for real in the exec image; the microVM budgets need
/dev/kvm and are reported skipped (never faked) where there is no nested virtualization. The microVM
COLD/WARM pass is gated on a per-run-random marker actually appearing on the guest serial console — the
`_wait_marker` tests below verify that gate (and its no-hang behaviour) without needing /dev/kvm.
"""
from __future__ import annotations

import subprocess
import sys
import time

import pytest

from infra.exec import bench
from infra.exec.sandbox import is_available


@pytest.mark.skipif(not is_available(), reason="overhead meter needs a Linux host with bwrap")
def test_bwrap_p95_within_budget():
    b = bench.bench_bwrap(n=30)
    assert b["within"] is True, b
    assert b["p95"] <= bench.BWRAP_P95_BUDGET_MS
    assert b["n"] == 30 and b["p50"] is not None


def test_microvm_is_honestly_skipped_without_kvm():
    if bench.has_kvm():
        pytest.skip("host has /dev/kvm; the skip path is not exercised here")
    m = bench.bench_microvm()
    assert m["within"] is None and "skipped" in m            # the budget is left unmet, not fabricated
    assert m["cold_budget_ms"] == 1500 and m["warm_budget_ms"] == 250


def _emit(text: str, delay: float = 0.0) -> "subprocess.Popen[bytes]":
    """A subprocess that (optionally waits, then) prints `text` and lingers — stands in for a guest console."""
    code = (f"import time,sys; time.sleep({delay}); "
            f"sys.stdout.write({text!r}); sys.stdout.flush(); time.sleep(5)")
    return subprocess.Popen([sys.executable, "-c", code], stdout=subprocess.PIPE,
                            stderr=subprocess.STDOUT, bufsize=0)


def test_wait_marker_true_only_when_marker_appears():
    # the honesty core: a pass is gated on the exact per-run marker actually appearing on the console.
    marker = "CWS_BOOT_OK_deadbeefcafe1234"
    p = _emit("booting kernel...\n" + marker + "\n")
    try:
        assert bench._wait_marker(p, marker, time.monotonic() + 5.0) is True
    finally:
        p.kill()


def test_wait_marker_false_when_marker_absent_respects_deadline():
    # a guest that boots but NEVER prints our marker must NOT pass — and must not hang past the deadline.
    p = _emit("booting kernel...\nsome other console output\n")
    try:
        t0 = time.monotonic()
        assert bench._wait_marker(p, "CWS_BOOT_OK_absentmarker0000", t0 + 1.0) is False
        assert time.monotonic() - t0 < 3.0                   # deadline honoured (the select path, no hang)
    finally:
        p.kill()


def test_wait_marker_false_on_silent_exit():
    # a guest that produces no output and exits returns False promptly (no hang on a dead process).
    p = subprocess.Popen([sys.executable, "-c", "pass"], stdout=subprocess.PIPE,
                         stderr=subprocess.STDOUT, bufsize=0)
    try:
        assert bench._wait_marker(p, "CWS_NEVER", time.monotonic() + 2.0) is False
    finally:
        p.kill()
