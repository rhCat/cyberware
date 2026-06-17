"""The reward ledger for SV-6 (P6-T02): a Ledger-v2 instance of balanced double-entry posting sets. Every
record balances (per-currency zero), an unbalanced set is refused, a 10k-settlement storm stays globally
zero-sum with escrow zero at every terminal state, and a balance root is committed. Pure stdlib."""
from __future__ import annotations

import pytest

from infra.settle import reward_ledger as R
from infra.settle.money import Money


def test_selftest_10k_storm():
    r = R.reward_ledger_selftest(10_000)
    assert r["ok"], r
    assert r["cycle_escrow_zero"] and r["unbalanced_refused"]
    assert r["storm"]["global_zero"] and r["storm"]["escrow_zero_at_terminal"] and r["storm"]["chain_ok"]


def test_unbalanced_posting_set_refused():
    led = R.open_ledger()
    with pytest.raises(ValueError):
        R.post(led, [R._posting("x", Money("1.0000")), R._posting("y", Money("2.0000"))])
    assert len([e for e in led if e.get("type") == "posting_set"]) == 0


def test_fund_release_nets_escrow_zero_and_splits_exact():
    led = R.open_ledger()
    R.fund_escrow(led, "alice", Money("100.0000"))
    R.release(led, "bob", "fee", Money("100.0000"), 5, 95)
    bal = R.balances(led)
    assert bal[(R.ESCROW, "USD")].is_zero()
    # fee + payee == 100 exactly
    assert bal[("fee", "USD")] + bal[("bob", "USD")] == Money("100.0000")
    assert R.global_zero(led)


def test_balance_root_changes_with_balances():
    led = R.open_ledger()
    r0 = R.balance_root(led)
    R.fund_escrow(led, "alice", Money("5.0000"))
    assert R.balance_root(led) != r0                          # the committed balance root tracks the balances
