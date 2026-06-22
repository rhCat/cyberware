#!/usr/bin/env python3
"""infra/settle/escrow_expiry.py — escrow liveness: expiry + auto-refund (P6-T03, SV-6 / M6, V-LIVE).

Every escrow funding carries an `expires_at`. A stalled escrow — funded but never settled — must NOT strand
value: a sweep at/after `expires_at` auto-refunds it to the funder as a balanced posting set, so **no escrow
older than its bound holds value at any audit**. A settled escrow (already drained by the engine) and a
not-yet-expired escrow are both left untouched. Deterministic `now` (no wall clock — passed in)."""
from __future__ import annotations

from infra.settle import reward_ledger
from infra.settle.money import Money

_FUND = "escrow-fund:"           # memo: escrow-fund:<key>:exp=<ts>:funder=<id>
_REFUND = "escrow-refund:"       # memo: escrow-refund:<key>
_SETTLE = "settle:quote:"        # the engine's settlement memo prefix (a drained escrow)


def fund_with_expiry(entries, funder, amount: Money, key: str, expires_at: int) -> dict:
    """Fund a per-key escrow that carries an expiry. Balanced: funder -> escrow:<key>."""
    acct = reward_ledger.escrow_for(key)
    return reward_ledger.post(entries, [reward_ledger._posting(funder, -amount),
                                        reward_ledger._posting(acct, amount)],
                              memo=f"{_FUND}{key}:exp={expires_at}:funder={funder}")


def _fundings(entries):
    """Parse the escrow fundings → {key: (expires_at, funder)} (last funding per key wins)."""
    out = {}
    for e in entries:
        if e.get("type") != "posting_set":
            continue
        m = str(e.get("memo", ""))
        if m.startswith(_FUND):
            rest = m[len(_FUND):]
            key, exp, funder = rest.split(":exp=")[0], rest.split(":exp=")[1].split(":funder=")[0], \
                rest.split(":funder=")[1]
            out[key] = (int(exp), funder)
    return out


def _settled_or_refunded(entries) -> set:
    """Keys whose escrow has already been drained — by a settlement or a prior refund — so the sweep skips
    them (idempotent: a swept key is not refunded twice)."""
    done = set()
    for e in entries:
        m = str(e.get("memo", "")) if e.get("type") == "posting_set" else ""
        if m.startswith(_SETTLE):
            done.add(m[len(_SETTLE):])
        elif m.startswith(_REFUND):
            done.add(m[len(_REFUND):])
    return done


def sweep_expired(entries, now: int) -> dict:
    """Auto-refund every funded, unsettled, un-refunded escrow whose expires_at <= now. Returns
    {refunded: [keys], count}. Each refund is a balanced posting set escrow:<key> -> funder."""
    done = _settled_or_refunded(entries)
    bal = reward_ledger.balances(entries)
    refunded = []
    for key, (exp, funder) in sorted(_fundings(entries).items()):
        if key in done or exp > now:
            continue
        held = bal.get((reward_ledger.escrow_for(key), "USD"), Money.zero())
        if held.is_zero():
            continue
        reward_ledger.post(entries, [reward_ledger._posting(reward_ledger.escrow_for(key), -held),
                                     reward_ledger._posting(funder, held)], memo=f"{_REFUND}{key}")
        refunded.append(key)
    return {"refunded": refunded, "count": len(refunded)}


def stale_escrow_keys(entries, now: int, bound: int = 0) -> list:
    """Audit: keys whose escrow STILL holds value past expires_at + bound (must be empty after a sweep)."""
    done = _settled_or_refunded(entries)
    bal = reward_ledger.balances(entries)
    stale = []
    for key, (exp, _funder) in _fundings(entries).items():
        if key in done or now < exp + bound:
            continue
        if not bal.get((reward_ledger.escrow_for(key), "USD"), Money.zero()).is_zero():
            stale.append(key)
    return sorted(stale)


def escrow_expiry_selftest() -> dict:
    """P6-T03: three escrows funded with expiries; one is settled, one expires unsettled, one is not yet due.
    A sweep refunds ONLY the expired-unsettled one (balanced, globally zero-sum), leaves the settled and the
    live one untouched, is idempotent (a second sweep refunds nothing), and after the sweep NO escrow older
    than its bound holds value. `ok` iff all hold."""
    led = reward_ledger.open_ledger()
    fund_with_expiry(led, "u1", Money("100.0000"), "a", expires_at=10)
    fund_with_expiry(led, "u1", Money("50.0000"), "b", expires_at=20)
    fund_with_expiry(led, "u1", Money("30.0000"), "c", expires_at=30)
    # key b settles (the engine drains its escrow) — model the settlement posting
    reward_ledger.post(led, [reward_ledger._posting(reward_ledger.escrow_for("b"), -Money("50.0000")),
                             reward_ledger._posting("payee", Money("50.0000"))], memo=f"{_SETTLE}b")

    swept = sweep_expired(led, now=25)                      # a (exp10) expired+unsettled; b settled; c not due
    bal = reward_ledger.balances(led)
    only_a_refunded = swept["refunded"] == ["a"]
    a_drained = bal.get((reward_ledger.escrow_for("a"), "USD"), Money.zero()).is_zero()
    a_refunded_to_funder = bal.get(("u1", "USD"), Money.zero()) == Money("-80.0000")  # funded 180, a(100) refunded
    c_untouched = bal.get((reward_ledger.escrow_for("c"), "USD"), Money.zero()) == Money("30.0000")
    global_zero = reward_ledger.global_zero(led)
    no_stale = stale_escrow_keys(led, now=25) == []
    idempotent = sweep_expired(led, now=25)["count"] == 0

    return {"only_expired_unsettled_refunded": only_a_refunded, "expired_escrow_drained": a_drained,
            "refunded_to_funder": a_refunded_to_funder, "live_escrow_untouched": c_untouched,
            "global_zero": global_zero, "no_stale_escrow_after_sweep": no_stale, "sweep_idempotent": idempotent,
            "ok": (only_a_refunded and a_drained and a_refunded_to_funder and c_untouched and global_zero
                   and no_stale and idempotent)}


if __name__ == "__main__":
    import json
    import sys
    r = escrow_expiry_selftest()
    print(json.dumps(r, indent=2))
    sys.exit(0 if r.get("ok") else 1)
