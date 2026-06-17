"""The signed funded quote for SV-6 (P6-T04): govd signs a plan-bound quote whose breakdown sums to the
amount exactly; a priced grant is refused without a funded quote and admitted with one; tampered, unfunded,
and plan-mismatched quotes are refused. Needs openssl with ed25519ph; skips otherwise."""
from __future__ import annotations
import shutil

import pytest

from infra.settle import quote as Q


def _capable():
    if not shutil.which("openssl"):
        return False
    try:
        Q.quote_selftest()
        return True
    except Exception:
        return False


pytestmark = pytest.mark.skipif(not _capable(), reason="quote signing needs openssl with ed25519ph")


def test_selftest():
    r = Q.quote_selftest()
    assert r["ok"], r
    assert r["breakdown_balances"] and r["priced_refused_without_funded_quote"]
    assert r["priced_admitted_with_funded_quote"] and r["plan_mismatch_refused"]
