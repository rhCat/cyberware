#!/usr/bin/env python3
"""infra/settle/budget.py — per-ACTOR credit budgets: a prepaid CREDIT balance + per-run DEBITS + a shutoff.

The budget belongs to the ACTOR (the principal id), enforced wherever they fire. Same double-entry model as
credits.py, keyed by the actor and denominated in CREDITS (an internal allowance unit — exact-decimal Money,
never a float). `balance(actor) = seeded allowance + top-ups - debits`. A run is REFUSED (the shutoff) if the
balance can't cover the run's credit price. Credits enter the balance by being granted (operator) or
RECHARGED (a Stripe purchase mints credits — credits.py/rails.py model); per run there is only a DEBIT, never
a dollar charge.

`budget_ok` is the PURE gate decision (no I/O — unit-tested both-sides like principals.acl_allows/rate_ok).
The in-memory `seed`/`topup`/`debit` here are the posting logic + the selftest path; the durable, ATOMIC
debit that serializes concurrent same-actor claims lives on the store backend (`budget_debit_atomic`).
"""
from __future__ import annotations

from infra.settle import reward_ledger
from infra.settle.money import Money

CREDITS = "CREDITS"
_SEED_PREFIX = "bud-seed:"
_TOPUP_PREFIX = "bud-topup:"
_USAGE_PREFIX = "bud-usage:"


def account_of(actor: str) -> str:
    """The actor's credit-budget balance account."""
    return f"budget:{actor}"


def balance(entries: list, actor: str) -> Money:
    """The actor's current credit balance (zero if never seeded)."""
    return reward_ledger.balances(entries).get((account_of(actor), CREDITS), Money.zero(CREDITS))


def _posted(entries: list, prefix: str, idem: str) -> bool:
    tag = prefix + idem
    return any(e.get("type") == "posting_set" and e.get("memo") == tag for e in entries)


def seed(entries: list, actor: str, allowance: Money, ref: str = None) -> dict:
    """Mint the actor's opening allowance ONCE (idempotent on ref/actor — a re-seed is a no-op)."""
    ref = ref or actor
    if _posted(entries, _SEED_PREFIX, ref):
        return {"status": "duplicate", "balance": str(balance(entries, actor).amount)}
    reward_ledger.post(entries, [reward_ledger._posting(account_of(actor), allowance),
                                 reward_ledger._posting("budget:grant", -allowance)],
                       memo=_SEED_PREFIX + ref)
    return {"status": "seeded", "added": str(allowance.amount), "balance": str(balance(entries, actor).amount)}


def topup(entries: list, actor: str, amount: Money, source: str = "grant", ref: str = "") -> dict:
    """Add credits to the actor — an operator grant or a Stripe recharge. Idempotent on ref."""
    if ref and _posted(entries, _TOPUP_PREFIX, ref):
        return {"status": "duplicate", "ref": ref, "balance": str(balance(entries, actor).amount)}
    reward_ledger.post(entries, [reward_ledger._posting(account_of(actor), amount),
                                 reward_ledger._posting(f"budget:topup:{source}", -amount)],
                       memo=_TOPUP_PREFIX + (ref or source))
    return {"status": "credited", "added": str(amount.amount), "source": source,
            "balance": str(balance(entries, actor).amount)}


def debit(entries: list, actor: str, price: Money, idem: str) -> dict:
    """Debit a run's credit price from the actor — REFUSED (no posting) if the balance won't cover it;
    idempotent on idem (plan_sha). The non-atomic, in-memory form (tests/selftest); the durable, concurrency-
    safe form is store backend.budget_debit_atomic."""
    if _posted(entries, _USAGE_PREFIX, idem):
        return {"status": "duplicate", "idem": idem, "balance": str(balance(entries, actor).amount)}
    bal = balance(entries, actor)
    if bal < price:
        return {"status": "insufficient_credits", "need": str(price.amount),
                "have": str(bal.amount), "idem": idem}
    reward_ledger.post(entries, [reward_ledger._posting(account_of(actor), -price),
                                 reward_ledger._posting(f"budget:spent:{actor}", price)],
                       memo=_USAGE_PREFIX + idem)
    return {"status": "debited", "spent": str(price.amount),
            "balance": str(balance(entries, actor).amount), "idem": idem}


def budget_ok(actor: str, price: Money, bal, *, configured: bool):
    """The PURE, fail-closed budget decision (no I/O). Returns (ok, problem|None):
      - not configured -> reject (`budget_unmetered`) when budget enforcement is ON;
      - bal is None (balance unreadable — store partition) -> fail closed (`budget_unavailable`);
      - bal < price -> the shutoff (`insufficient_credits`);
      - else allow."""
    if not configured:
        return (False, {"id": "budget_unmetered", "detail": {"actor": actor}})
    if bal is None:
        return (False, {"id": "budget_unavailable", "detail": {"actor": actor}})
    if bal < price:
        return (False, {"id": "insufficient_credits",
                        "detail": {"price": str(price.amount), "balance": str(bal.amount), "currency": CREDITS}})
    return (True, None)


def budget_selftest() -> dict:
    """Value-free, no-network: seed an allowance, debit (drawn down + idempotent), refuse over-balance,
    top-up, and the pure gate (allow / shutoff / unmetered)."""
    led = reward_ledger.open_ledger()
    a = "alice"
    seed(led, a, Money("5.0000", CREDITS))
    d1 = debit(led, a, Money("2.0000", CREDITS), "P1")
    d2 = debit(led, a, Money("2.0000", CREDITS), "P1")            # idempotent
    over = debit(led, a, Money("99.0000", CREDITS), "P2")         # exceeds the balance -> refused
    topup(led, a, Money("3.0000", CREDITS), source="grant", ref="g1")
    bal = balance(led, a)
    return {
        "seeded": balance(reward_ledger.open_ledger(), a) == Money.zero(CREDITS)
                  and Money.zero(CREDITS) < bal,
        "debited": d1["status"] == "debited",
        "idempotent": d2["status"] == "duplicate",
        "balance_drawn_down": Money(d1["balance"], CREDITS) == Money("3.0000", CREDITS),
        "over_balance_refused": over["status"] == "insufficient_credits",
        "topup_added": bal == Money("6.0000", CREDITS),          # 3 left + 3 top-up
        "zero_sum": reward_ledger.global_zero(led),
        "gate_allows": budget_ok(a, Money("1.0000", CREDITS), bal, configured=True)[0],
        "gate_shutoff": not budget_ok(a, Money("9.0000", CREDITS), bal, configured=True)[0],
        "gate_unmetered": not budget_ok(a, Money("1.0000", CREDITS), None, configured=False)[0],
    }
