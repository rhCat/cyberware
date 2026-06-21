#!/usr/bin/env python3
"""infra/settle/credits.py — credit-based usage billing: a prepaid balance + per-call DEBITS, not per-call fees.

Per-call card charges bleed Stripe's flat ~$0.30 fee — a $0.006 usage tax would cost ~50x its value to collect.
So the operator TOPS UP a credit balance with ONE Stripe charge (the flat fee amortizes over thousands of calls),
and each priced run DEBITS its usage tax from the balance INTERNALLY: a zero-sum reward-ledger posting set
(credit:operator drawn down; the transparent split — substrate / skill_author / marketplace — credited), with
NO Stripe call. A run is REFUSED if the balance can't cover the tax — so the tax is a structural gate, not an
after-the-fact fee. Idempotent per run (plan_sha). No float touches it (exact-decimal Money).

The boundary: Stripe sees only occasional TOP-UPS (real money in, fee amortized); per-call usage never touches
Stripe. The transparent split is recorded on every debit, so the operator sees where the credits went; real
disbursement of the split to connected accounts is a separate Connect step (the credit posting is the record).
"""
from __future__ import annotations

from infra.settle import reward_ledger
from infra.settle.money import Money

_USAGE_PREFIX = "usage:"
_TOPUP_PREFIX = "topup:"


def credit_account(operator: str) -> str:
    """The operator's prepaid balance account."""
    return f"credit:{operator}"


def balance(entries: list, operator: str, currency: str = "USD") -> Money:
    """Current prepaid balance for the operator."""
    return reward_ledger.balances(entries).get((credit_account(operator), currency), Money.zero(currency))


def _posted(entries: list, prefix: str, idem_key: str) -> bool:
    tag = prefix + idem_key
    return any(e.get("type") == "posting_set" and e.get("memo") == tag for e in entries)


def topup(entries: list, operator: str, amount: Money, source: str = "stripe", ref: str = "") -> dict:
    """Add prepaid credits (funded by ONE top-up — e.g. a single Stripe charge whose flat fee amortizes over
    many calls). A balanced posting: credit:operator += amount, against a funding account. Idempotent on ref."""
    if ref and _posted(entries, _TOPUP_PREFIX, ref):
        return {"status": "duplicate", "ref": ref, "balance": str(balance(entries, operator, amount.currency).amount)}
    reward_ledger.post(entries, [reward_ledger._posting(credit_account(operator), amount),
                                 reward_ledger._posting(f"topup:{source}", -amount)],
                       memo=_TOPUP_PREFIX + (ref or source))
    return {"status": "credited", "added": str(amount.amount), "source": source,
            "balance": str(balance(entries, operator, amount.currency).amount)}


def admits(entries: list, operator: str, tax_total, currency: str = "USD") -> bool:
    """The gate: a priced run is admitted only if the credit balance covers the usage tax."""
    return balance(entries, operator, currency) >= Money(tax_total, currency)


def debit_usage(entries: list, operator: str, charge: dict, idem_key: str) -> dict:
    """Debit the usage tax from the operator's credits, posting the transparent split — refused (no posting)
    if the balance is insufficient, idempotent per run. NO Stripe call: the credit balance is the meter."""
    cur = charge["currency"]
    if _posted(entries, _USAGE_PREFIX, idem_key):
        return {"status": "duplicate", "idem": idem_key,
                "balance_after": str(balance(entries, operator, cur).amount)}
    total = Money(charge["total"], cur)
    bal = balance(entries, operator, cur)
    if bal < total:
        return {"status": "insufficient_credits", "need": charge["total"],
                "have": str(bal.amount), "idem": idem_key}
    postings = [reward_ledger._posting(credit_account(operator), -total)]
    for b in charge["breakdown"]:
        postings.append(reward_ledger._posting(b["account"], Money(b["amount"], cur)))
    reward_ledger.post(entries, postings, memo=_USAGE_PREFIX + idem_key)
    return {"status": "debited", "total": charge["total"], "breakdown": charge["breakdown"],
            "balance_after": str(balance(entries, operator, cur).amount), "idem": idem_key}


def credits_selftest() -> dict:
    """Value-free, no-network: top-up credits, debit usage (split posted, balance drawn down, zero-sum),
    refuse over-balance, idempotent."""
    from infra.settle import price, rails
    led = reward_ledger.open_ledger()
    op = "acme"
    topup(led, op, Money("10.00"), source="stripe", ref="t1")
    charge = rails.charge_from_price(price.price_plan("http", "get"), "PSHA")   # tiny usage tax
    d1 = debit_usage(led, op, charge, "PSHA")
    d2 = debit_usage(led, op, charge, "PSHA")                                   # idempotent
    after = balance(led, op)
    big = dict(charge, total="999.00", breakdown=[{"account": "marketplace", "amount": "999.00"}])
    over = debit_usage(led, op, big, "OVER")                                    # exceeds balance -> refused
    return {
        "topup_credits_balance": balance(reward_ledger.open_ledger(), op) == Money("0")
                                  and after < Money("10.00"),
        "debited": d1["status"] == "debited",
        "idempotent": d2["status"] == "duplicate",
        "balance_drawn_down": Money(d1["balance_after"]) == Money("10.00") - Money(charge["total"]),
        "split_posted": reward_ledger.balances(led).get(("marketplace", "USD"), Money.zero())
                        == Money(next(b["amount"] for b in charge["breakdown"] if b["account"] == "marketplace")),
        "zero_sum": reward_ledger.global_zero(led),
        "over_balance_refused": over["status"] == "insufficient_credits",
        "admits_gate": admits(led, op, charge["total"]) and not admits(led, op, "999.00"),
    }
