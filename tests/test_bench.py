"""cws-bench (P2-T09): the sandbox/channel overhead meter, over exod's attested meters (P2-T07).

The bwrap budget (p95 <= 100 ms/step) is measured for real in the exec image; the microVM budgets need
/dev/kvm and are reported skipped (never faked) where there is no nested virtualization.
"""
from __future__ import annotations

import pytest

from infra.exec import bench
from infra.exec.sandbox import is_available

pytestmark = pytest.mark.skipif(not is_available(), reason="overhead meter needs a Linux host with bwrap")


def test_bwrap_p95_within_budget():
    b = bench.bench_bwrap(n=30)
    assert b["within"] is True, b
    assert b["p95"] <= bench.BWRAP_P95_BUDGET_MS
    assert b["n"] == 30 and b["p50"] is not None


def test_microvm_is_honestly_skipped_without_kvm():
    m = bench.bench_microvm()
    if not bench.has_kvm():
        assert m["within"] is None and "skipped" in m   # the budget is left unmet, not fabricated
