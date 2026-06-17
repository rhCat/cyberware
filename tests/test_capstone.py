"""The SV-6 capstone (P6-T21) — the ladder closes: cyberware's real redeemed milestones settle as
internal-credit bounties (zero-sum), seed the first FMV index, and the plan's completion is a dual-signed,
TSA-anchored receipt that verifies offline end-to-end. Needs openssl with ed25519ph; skips otherwise."""
from __future__ import annotations
import shutil

import pytest

from infra.settle import capstone as C


def _capable():
    if not shutil.which("openssl"):
        return False
    try:
        C.capstone_selftest()
        return True
    except Exception:
        return False


pytestmark = pytest.mark.skipif(not _capable(), reason="capstone needs openssl with ed25519ph")


def test_the_ladder_closes():
    r = C.capstone_selftest()
    assert r["ok"], r
    assert r["settled_milestones"] >= 10 and r["ledger_zero_sum"]
    assert r["plan_completion_verifies_offline"] and r["tamper_caught"]
    assert r["THE_LADDER_CLOSES"]
