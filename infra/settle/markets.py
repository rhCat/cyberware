#!/usr/bin/env python3
"""infra/settle/markets.py — competitive award mechanisms (P6-T10, SV-6 / M6).

Two ways the platform awards work, both over the reward ledger's escrow/posting machinery (so every move is
a balanced double-entry posting set, globally zero-sum):

  * **bounty** — a poster funds ONE prize escrow; among the competitors whose work VALIDATED, exactly one
    wins (first-validated, or best by score); the prize releases to that winner and NO loser's balance is
    touched. With no validated entry the prize refunds to the poster (no winner).
  * **reverse auction** — among the QUALIFIED bids at or below the posted ceiling, the LOWEST clears
    (first-price). Under genuine competition it clears strictly below the posted price.
"""
from __future__ import annotations

from infra.settle import reward_ledger
from infra.settle.money import Money


def award_bounty(entries, poster, prize: Money, competitors, bounty_id: str = "b1",
                 select: str = "first") -> dict:
    """Fund a prize escrow, then release it to exactly ONE winner among the validated competitors
    (`select`: "first" = first validated; "best" = highest `score`). Losers are never debited. Returns
    {winner, paid, validated_count}. competitors: [{name, validated: bool, score?}]."""
    acct = f"bounty:{bounty_id}"
    reward_ledger.fund_escrow(entries, poster, prize, escrow_acct=acct, memo=f"fund-bounty:{bounty_id}")
    valid = [c for c in competitors if c.get("validated")]
    if not valid:                                            # nobody passed → refund the poster, no winner
        reward_ledger.post(entries, [reward_ledger._posting(acct, -prize),
                                     reward_ledger._posting(poster, prize)],
                           memo=f"refund-bounty:{bounty_id}")
        return {"winner": None, "paid": "0", "validated_count": 0}
    winner = max(valid, key=lambda c: c.get("score", 0)) if select == "best" else valid[0]
    reward_ledger.post(entries, [reward_ledger._posting(acct, -prize),
                                 reward_ledger._posting(f"payee:{winner['name']}", prize)],
                       memo=f"award-bounty:{bounty_id}")
    return {"winner": winner["name"], "paid": str(prize.amount), "validated_count": len(valid)}


def clear_reverse_auction(posted: Money, bids) -> dict:
    """The lowest QUALIFIED bid at or below the posted ceiling clears (first-price). Returns
    {winner, clearing_price, below_posted, qualified_count}. bids: [{name, price, qualified: bool}]."""
    cur = posted.currency
    elig = [(b["name"], Money(b["price"], cur)) for b in bids
            if b.get("qualified") and Money(b["price"], cur).amount <= posted.amount]
    if not elig:
        return {"winner": None, "clearing_price": None, "below_posted": False, "qualified_count": 0}
    winner, price = min(elig, key=lambda np: np[1].amount)
    return {"winner": winner, "clearing_price": str(price.amount),
            "below_posted": price.amount < posted.amount, "qualified_count": len(elig)}


def markets_selftest() -> dict:
    """P6-T10: a bounty pays exactly one validated winner with losers' balances untouched and the prize
    escrow drained to zero (globally zero-sum); with no validated entry the prize refunds; a reverse
    auction clears at the lowest qualified bid strictly below the posted price, and does not clear when no
    bid qualifies. `ok` iff all hold."""
    led = reward_ledger.open_ledger()
    competitors = [{"name": "alice", "validated": False},
                   {"name": "bob", "validated": True},
                   {"name": "carol", "validated": True}]
    res = award_bounty(led, "poster", Money("100.0000"), competitors, bounty_id="x", select="first")
    bal = reward_ledger.balances(led)
    one_winner = res["winner"] == "bob"
    losers_untouched = all((f"payee:{n}", "USD") not in bal for n in ("alice", "carol"))
    winner_paid = bal.get(("payee:bob", "USD"), Money.zero()) == Money("100.0000")
    bounty_drained = bal.get(("bounty:x", "USD"), Money.zero()).is_zero()
    bounty_one_winner = one_winner and losers_untouched and winner_paid and bounty_drained \
        and reward_ledger.global_zero(led)

    led2 = reward_ledger.open_ledger()
    none_valid = award_bounty(led2, "poster", Money("50.0000"), [{"name": "z", "validated": False}],
                              bounty_id="y")
    refunded = (none_valid["winner"] is None
                and reward_ledger.balances(led2).get(("bounty:y", "USD"), Money.zero()).is_zero()
                and reward_ledger.global_zero(led2))

    a = clear_reverse_auction(Money("100.0000"), [
        {"name": "hi", "price": "95.0000", "qualified": True},
        {"name": "lo", "price": "80.0000", "qualified": True},
        {"name": "cheat", "price": "10.0000", "qualified": False}])
    auction_clears_below_posted = (a["winner"] == "lo" and a["clearing_price"] == "80.0000"
                                   and a["below_posted"] is True)
    a2 = clear_reverse_auction(Money("100.0000"), [{"name": "x", "price": "50.0000", "qualified": False}])
    no_clear_when_unqualified = a2["winner"] is None

    return {"bounty_one_winner": bounty_one_winner, "bounty_refund_when_none_valid": refunded,
            "auction_clears_below_posted": auction_clears_below_posted,
            "auction_no_clear_when_unqualified": no_clear_when_unqualified,
            "ok": (bounty_one_winner and refunded and auction_clears_below_posted
                   and no_clear_when_unqualified)}


if __name__ == "__main__":
    import json
    import sys
    r = markets_selftest()
    print(json.dumps(r, indent=2))
    sys.exit(0 if r.get("ok") else 1)
