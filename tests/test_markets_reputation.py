"""P6-T10 markets (bounty + reverse auction) and P6-T13 reputation — pure-logic settlement tail."""
from __future__ import annotations

from infra.settle import markets, reputation


def test_markets_bounty_one_winner_and_auction_clears_below_posted():
    r = markets.markets_selftest()
    assert r["ok"] is True, r
    assert r["bounty_one_winner"] is True               # exactly one validated winner, losers untouched
    assert r["bounty_refund_when_none_valid"] is True
    assert r["auction_clears_below_posted"] is True
    assert r["auction_no_clear_when_unqualified"] is True


def test_reputation_reproducible_signed_and_privacy_gated():
    r = reputation.reputation_selftest()
    assert r["ok"] is True, r
    assert r["third_party_reproducible"] is True        # recomputable from public ledger data alone
    assert r["scores_signed_and_verify"] is True        # signed; a tamper breaks the signature
    assert r["rep_privacy"] is True                      # counterparty detail vs aggregate-only
