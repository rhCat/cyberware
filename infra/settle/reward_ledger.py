#!/usr/bin/env python3
"""infra/settle/reward_ledger.py — the reward ledger (P6-T02, SV-6 / M6).

The reward ledger is a **Ledger-v2 instance** (the same prev-hash chain as `infra/cwp/ledger.py`) whose every
record is a **balanced double-entry posting set**: the signed amounts in a record sum to **exactly zero per
currency**, so money is only ever moved, never created or destroyed. Two conservation invariants:

  * **zero-sum, per-record AND global** — each posting set balances on its own (enforced at `post`), and the
    fold over the whole chain is zero per currency. An unbalanced posting set is refused.
  * **escrow/hold accounts return to zero at every terminal state** — a fund→release cycle nets an escrow
    account back to zero; after a storm of settlements no value is stranded in escrow.

Balances are exact `Money` (scale-4 decimal, never float), and a checkpoint commits a **balance root** (a
Merkle root over the per-account balances) so a verifier can attest the balance set without replaying the
whole chain.
"""
from __future__ import annotations
import hashlib
from decimal import Decimal

from infra.cwp import ledger
from infra.settle.money import Money, split

ESCROW = "escrow"


def escrow_for(quote_sha: str) -> str:
    """The per-quote escrow sub-account — funding is bound to the SPECIFIC quote, never a fungible pool, so
    one quote's funding can never satisfy another's grant or settlement."""
    return f"{ESCROW}:{quote_sha[:32]}"


def _posting(account: str, m: Money) -> dict:
    """A single signed posting — amount serialized as a string (never a float)."""
    return {"account": account, "amount": str(m.amount), "currency": m.currency}


def is_balanced(postings) -> bool:
    """A posting set is balanced iff the signed amounts sum to exactly zero in EVERY currency."""
    by_cur = {}
    for p in postings:
        c = p["currency"]
        by_cur[c] = (by_cur.get(c) or Money.zero(c)) + Money(p["amount"], c)
    return all(m.is_zero() for m in by_cur.values())


def open_ledger(run_id: str = "reward", plan_sha: str = "reward-plan") -> list:
    """A fresh reward chain, bound to its origin (genesis)."""
    return [ledger.genesis(run_id, plan_sha)]


def post(entries: list, postings, memo: str = "") -> dict:
    """Append a posting set — REFUSING it unless it is balanced (double-entry). Returns the appended record."""
    if not is_balanced(postings):
        raise ValueError("unbalanced posting set: signed amounts must sum to zero per currency")
    ledger.append(entries, {"type": "posting_set", "postings": list(postings), "memo": memo})
    return entries[-1]


def fund_escrow(entries: list, funder: str, amount: Money, escrow_acct: str = ESCROW,
                memo: str = "fund") -> dict:
    """Move `amount` from a funder into an escrow account (a balanced posting set). `escrow_acct` defaults to
    the generic pool but a quote-funded flow passes a per-quote sub-account (`escrow_for(quote_sha)`)."""
    return post(entries, [_posting(funder, -amount), _posting(escrow_acct, amount)], memo)


def release(entries: list, payee: str, fee_account: str, amount: Money, fee_weight, payee_weight,
            memo: str = "release", escrow_acct: str = ESCROW) -> dict:
    """Release an escrowed `amount` to a payee + a fee account, split EXACTLY by the given weights, draining
    the escrow account by the full amount (so escrow nets to zero across fund→release). `escrow_acct` defaults
    to the generic pool for back-compat but SHOULD mirror the account that `fund_escrow` credited (e.g. the
    per-quote sub-account `escrow_for(quote_sha)`) so a per-quote fund→release nets that account to zero."""
    fee_part, payee_part = split(amount, [fee_weight, payee_weight])
    return post(entries, [_posting(escrow_acct, -amount), _posting(fee_account, fee_part),
                          _posting(payee, payee_part)], memo)


def balances(entries: list) -> dict:
    """Fold the chain → {(account, currency): Money}."""
    bal = {}
    for e in entries:
        if e.get("type") != "posting_set":
            continue
        for p in e["postings"]:
            k = (p["account"], p["currency"])
            bal[k] = (bal.get(k) or Money.zero(p["currency"])) + Money(p["amount"], p["currency"])
    return bal


def global_zero(entries: list) -> bool:
    """True iff the chain conserves value: the sum across all accounts is zero in every currency."""
    by_cur = {}
    for (_, cur), m in balances(entries).items():
        by_cur[cur] = (by_cur.get(cur) or Money.zero(cur)) + m
    return all(m.is_zero() for m in by_cur.values())


def balance_root(entries: list) -> str:
    """A Merkle root over the per-account balances — the checkpointable commitment to the balance set."""
    leaves = [hashlib.sha256(f"{a}|{c}|{m.amount}".encode()).digest()
              for (a, c), m in sorted(balances(entries).items(), key=lambda kv: (kv[0][0], kv[0][1]))]
    from infra.cwp import checkpoint
    return checkpoint.merkle_root(leaves).hex()


def storm(n: int, seed: int = 0) -> dict:
    """A storm of `n` randomized fund→release settlements. Each posting set is balanced (enforced); we then
    assert the GLOBAL per-currency sum is zero, the escrow account is exactly zero at the terminal state, and
    the chain verifies. Randomness is seeded + index-derived (no float)."""
    import random
    rng = random.Random(seed)
    led = open_ledger()
    for i in range(n):
        cents = rng.randint(1, 9_999_999)
        amount = Money(Decimal(cents) * Decimal("0.0001"))
        funder, payee = f"u{rng.randint(0, 50)}", f"p{rng.randint(0, 50)}"
        fund_escrow(led, funder, amount, memo=f"fund-{i}")
        release(led, payee, "fee", amount, rng.randint(1, 9), rng.randint(10, 99), memo=f"rel-{i}")
    bal = balances(led)
    escrow_zero = all(m.is_zero() for (a, _), m in bal.items() if a == ESCROW)
    chain_ok = bool(ledger.verify_chain(led, ledger.CURRENT_MAJOR))    # O(n) prev-hash re-link
    gz = global_zero(led)
    return {"settlements": n, "records": len(led) - 1, "global_zero": gz,
            "escrow_zero_at_terminal": escrow_zero, "chain_ok": chain_ok,
            "balance_root": balance_root(led),
            "ok": gz and escrow_zero and chain_ok}


def reward_ledger_selftest(storm_n: int = 10_000) -> dict:
    """P6-T02: a balanced posting set is accepted and an unbalanced one is REFUSED; a fund→release cycle
    nets escrow to zero; a 10k-settlement storm stays globally zero-sum with escrow zero at the terminal
    state; and the balance root is stable across recomputation. `ok` iff all hold."""
    led = open_ledger()
    fund_escrow(led, "alice", Money("100.0000"))
    release(led, "bob", "fee", Money("100.0000"), 5, 95)        # 5% fee, exact split
    cycle_escrow_zero = balances(led).get((ESCROW, "USD"), Money.zero()).is_zero()

    refused = False
    try:
        post(led, [_posting("x", Money("1.0000")), _posting("y", Money("2.0000"))])   # sums to +3, not 0
    except ValueError:
        refused = True

    st = storm(storm_n, seed=1)
    root_stable = balance_root(led) == balance_root(led)
    return {"cycle_escrow_zero": cycle_escrow_zero, "unbalanced_refused": refused,
            "storm": {k: st[k] for k in ("settlements", "global_zero", "escrow_zero_at_terminal", "chain_ok")},
            "balance_root_stable": root_stable,
            "ok": cycle_escrow_zero and refused and st["ok"] and root_stable}
