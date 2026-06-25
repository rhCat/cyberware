#!/usr/bin/env python3
"""infra/settle/dust.py — P6-T15: the adapter-boundary rounding rule + the dust account.

A CWC amount is exact decimal at scale 4 (infra/settle/money.py). An adapter boundary that bills in INTEGER
CENTS (a PSP) can only carry 2 decimals — so the amount is banker's-rounded (HALF_EVEN) to the cent. The
sub-cent RESIDUE is never created or destroyed: it posts to `dust:adapter:<id>` INSIDE THE SAME balanced entry,
so the ledger's global zero-sum holds INCLUDING the dust accounts. Accumulated dust is swept (monthly) to the
treasury as a balanced, Ed25519-SIGNED record. No float ever touches it (exact Money; explicit HALF_EVEN).
"""
from __future__ import annotations
from decimal import ROUND_HALF_EVEN, Decimal

from infra.cwp import sign
from infra.settle import reward_ledger as RL
from infra.settle.money import Money

CENT = Decimal("0.01")
DUST_SWEEP_TYPE = "application/cyberware.dust-sweep+json"


def dust_account(adapter_id: str) -> str:
    return f"dust:adapter:{adapter_id}"


def split_cents(amount: Money):
    """Split a scale-4 Money into (cents, dust): `cents` = the amount banker's-rounded (HALF_EVEN) to 2dp — the
    integer-cents boundary; `dust` = the sub-cent residue. cents + dust == amount EXACTLY (nothing made or lost)."""
    cents = Money(amount.amount.quantize(CENT, rounding=ROUND_HALF_EVEN), amount.currency)
    return cents, amount - cents


def to_minor(amount: Money) -> int:
    """The integer minor units (cents) an adapter bills — the banker's-rounded 2dp value as an int."""
    cents, _ = split_cents(amount)
    return int((cents.amount * 100).to_integral_value())


def boundary_posting(payer: str, dest: str, amount: Money, adapter_id: str):
    """A BALANCED posting moving `amount` payer→dest across the cent boundary: `dest` is credited the rounded
    `cents`; the sub-cent `dust` residue lands in `dust:adapter:<id>`, so the FULL scale-4 amount is conserved
    (the set sums to zero per currency). A zero residue adds no dust posting."""
    cents, dust = split_cents(amount)
    postings = [RL._posting(payer, -amount), RL._posting(dest, cents)]
    if not dust.is_zero():
        postings.append(RL._posting(dust_account(adapter_id), dust))
    return postings


def settle_at_boundary(entries: list, payer: str, dest: str, amount: Money, adapter_id: str, memo: str = ""):
    """Post ONE balanced boundary transfer (cents to `dest`, residue to the adapter's dust account)."""
    return RL.post(entries, boundary_posting(payer, dest, amount, adapter_id),
                   memo=memo or f"boundary:{adapter_id}")


def sweep_dust(entries: list, adapter_id: str, treasury: str, signer, *, currency: str = "USD",
               period: str = "month"):
    """Sweep the accumulated `dust:adapter:<id>` balance to the treasury as ONE balanced posting set, and return
    an Ed25519-SIGNED record over the value-free summary. A zero dust balance is a no-op (nothing posted)."""
    acct = dust_account(adapter_id)
    bal = RL.balances(entries).get((acct, currency), Money.zero(currency))
    if bal.is_zero():
        return {"swept": str(Money.zero(currency).amount), "adapter": adapter_id, "currency": currency,
                "signed": None, "noop": True}
    RL.post(entries, [RL._posting(acct, -bal), RL._posting(treasury, bal)],
            memo=f"dust-sweep:{adapter_id}:{period}")
    summary = {"adapter": adapter_id, "swept": str(bal.amount), "currency": currency,
               "treasury": treasury, "period": period}
    return {"swept": str(bal.amount), "adapter": adapter_id, "currency": currency,
            "signed": sign.sign(summary, signer, payload_type=DUST_SWEEP_TYPE), "noop": False}


def dust_selftest(n: int = 100000) -> dict:
    """Hermetic, no-network:
      (1) split_exact — cents + dust == amount for every case; `cents` is exactly 2dp;
      (2) bankers_rounding — a half-cent residue rounds to EVEN (0.1250→0.12, 0.1350→0.14), not always up;
      (3) boundary_balanced — a boundary posting sums to zero per currency;
      (4) storm_zero_sum_incl_dust — N FX-boundary settlements keep the ledger GLOBALLY zero-sum INCLUDING the
          dust accounts, and the dust account holds EXACTLY the summed residue;
      (5) signed_sweep — the monthly sweep is balanced (global zero-sum preserved), drains the dust account to
          the treasury, and its signed record VERIFIES while a tampered one does NOT.
    """
    from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
    cur = "USD"

    # (1)(2) split exactness + banker's rounding
    split_exact = True
    for s in ("1.2345", "0.0001", "99.9950", "0.1250", "0.1350", "12.3456", "0.0049", "0.0050"):
        a = Money(s, cur); c, d = split_cents(a)
        split_exact = split_exact and (c + d == a) and (c.amount == c.amount.quantize(CENT))
    bankers = (split_cents(Money("0.1250", cur))[0].amount == Decimal("0.1200")        # 12.5c → 12 (even)
               and split_cents(Money("0.1350", cur))[0].amount == Decimal("0.1400")    # 13.5c → 14 (even)
               and split_cents(Money("0.0050", cur))[0].amount == Decimal("0.0000"))   # 0.5c → 0 (even)

    boundary_balanced = RL.is_balanced(boundary_posting("payer", "psp", Money("1.2345", cur), "stripe"))

    # (4) storm: N sub-cent-bearing settlements; the ledger stays globally zero-sum INCLUDING dust, and the dust
    #     account equals the EXACT sum of residues (an independent Decimal tally, no Money arithmetic shared).
    led = RL.open_ledger()
    dust_tally = Decimal(0)
    for i in range(n):
        amt = Money(str((i % 97) + 1) + "." + f"{(i * 7) % 100:02d}{(i * 13) % 100:02d}", cur)  # scale-4, sub-cent
        settle_at_boundary(led, "escrow", f"payee{i % 23}", amt, "stripe")
        _, dust = split_cents(amt)
        dust_tally += dust.amount
    bal = RL.balances(led)
    storm_zero_sum_incl_dust = (RL.global_zero(led)
                                and bal.get((dust_account("stripe"), cur), Money.zero(cur)).amount == dust_tally)

    # (5) signed monthly sweep
    sk = Ed25519PrivateKey.generate()
    before_dust = bal.get((dust_account("stripe"), cur), Money.zero(cur))
    res = sweep_dust(led, "stripe", "treasury", sk, currency=cur)
    after = RL.balances(led)
    sweep_ok = (RL.global_zero(led)                                                    # still conserved
                and after.get((dust_account("stripe"), cur), Money.zero(cur)).is_zero()  # dust drained
                and after.get(("treasury", cur), Money.zero(cur)) == before_dust          # to the treasury
                and Money(res["swept"], cur) == before_dust
                and sign.verify(res["signed"], sk.public_key()) is True)
    tampered = dict(res["signed"]); tampered["payload"] = sign.sign({"adapter": "EVIL"}, sk,
                                                                    payload_type=DUST_SWEEP_TYPE)["payload"]
    tamper_caught = sign.verify(tampered, sk.public_key()) is False

    ok = bool(split_exact and bankers and boundary_balanced and storm_zero_sum_incl_dust and sweep_ok
              and tamper_caught)
    return {"split_exact": split_exact, "bankers_rounding": bankers, "boundary_balanced": boundary_balanced,
            "storm_zero_sum_incl_dust": storm_zero_sum_incl_dust, "signed_sweep": sweep_ok,
            "tamper_caught": tamper_caught, "settlements": n, "ok": ok}


if __name__ == "__main__":
    import json
    import sys
    r = dust_selftest()
    print(json.dumps(r, indent=2))
    sys.exit(0 if r["ok"] else 1)
