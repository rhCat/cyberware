"""The dispute lifecycle for SV-6 (P6-T12): bond → m-of-n WebAuthn resolution → clawback/forfeit + reputation,
all ledgered and zero-sum. Fewer than m distinct valid approvals does not resolve; a tampered approval does
not count. Pure Python (Ed25519 via cryptography)."""
from __future__ import annotations

from infra.settle import disputes as D


def test_selftest():
    r = D.dispute_selftest()
    assert r["ok"], r


def test_m_of_n_and_clawback():
    r = D.dispute_selftest()
    assert r["bond_posted_and_upheld_clawback"] and r["insufficient_approvals_blocked"]
    assert r["tampered_approval_ignored"] and r["rejected_forfeits_bond"]
