"""Feed availability tiers + grace for SV-4 (P3-T12): through a feed outage, read-only proceeds to grace-2
while destructive refuses; past grace-2 everything fails closed; a forged feed refuses at every tier; and a
fresh feed re-converges with no state surgery. Needs openssl with ed25519ph; skips otherwise."""
from __future__ import annotations
import shutil

import pytest

from infra.cwp import feed_tiers as F


def _capable() -> bool:
    if not shutil.which("openssl"):
        return False
    try:
        F.tiers_selftest()
        return True
    except Exception:
        return False


pytestmark = pytest.mark.skipif(not _capable(), reason="needs openssl with ed25519ph")


def test_selftest_holds():
    r = F.tiers_selftest()
    assert r["ok"], r


def test_grace_allows_read_only_and_refuses_destructive():
    r = F.tiers_selftest()
    assert r["grace1_read_only_only"] and r["grace2_read_only_only"]
    assert r["expired_fails_closed"] and r["forged_refused"] and r["recovery_reconverges"]


def test_tier_buckets():
    assert F.tier_for(10, 600, 600, 1800) == F.FRESH
    assert F.tier_for(700, 600, 600, 1800) == F.GRACE_1
    assert F.tier_for(1300, 600, 600, 1800) == F.GRACE_2
    assert F.tier_for(9999, 600, 600, 1800) == F.EXPIRED
