"""The kernel red-team corpus (P2-T08): every behaviour must REFUSE its attack and ACCEPT its oracle.

The channel family is platform-agnostic and runs here; the sandbox family needs Linux + bwrap and runs in
the exec image (it self-skips otherwise). The whole-corpus assertion (>=12 behaviours held, scan disabled,
governed under exod) is the M3/SV-3 gate and is exercised in docker.
"""
from __future__ import annotations

import pytest

from infra.exec import redteam as RT
from infra.exec.sandbox import is_available

# the whole corpus is governed under exod and every behaviour's ORACLE (a benign granted step) runs through
# the bwrap sandbox — so this is inherently a Linux/bwrap artifact, exercised in the exec image. exod's
# channel logic itself is unit-covered off-Linux by test_exod.py.
pytestmark = pytest.mark.skipif(not is_available(), reason="kernel red-team needs a Linux host with bwrap")


def test_corpus_has_at_least_twelve_behaviours():
    assert len(RT.ATTACKS) >= 12


@pytest.mark.parametrize("name", list(RT._CHANNEL))
def test_channel_attack_is_refused_with_oracle(name):
    out = RT.run_attack(name)
    assert out.held, f"{name} did not hold: {out.detail}"


@pytest.mark.parametrize("name", list(RT._SANDBOX))
def test_sandbox_attack_is_kernel_refused(name):
    out = RT.run_attack(name)
    assert out.held, f"{name} did not hold: {out.detail}"


def test_full_corpus_holds_under_exod_scan_disabled():
    outs, ok = RT.run_corpus()
    failed = [(o.name, o.detail) for o in outs if not o.held and not o.detail.startswith("skipped")]
    assert ok and not failed, f"breaches: {failed}"
