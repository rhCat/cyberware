#!/usr/bin/env python3
"""infra/settle/metered.py — P6-T08 attested meters become settleable + provider-receipt capture.

An exod-ATTESTED usage meter (P2-T07: measured + signed BY exod, inside the result signature) becomes a
settleable amount for metered (llm/*) steps. The doctrine:

  * the meter must be exod-attested (`by == "exod"`) — an un-attested count is never settleable;
  * a provider RECEIPT (the upstream LLM's own billed tokens + cost) is captured and reconciled against the
    attested meter within a tolerance; if it agrees, the step settles at the receipt cost — a PASS-THROUGH
    reimbursement of the real provider cost (clamped to a metered [floor, cap]);
  * a receipt that does NOT reconcile with the attested meter is unsettleable (disputed — never silently pay
    a receipt the boundary's own meter contradicts);
  * absent a receipt, the step settles at the exod-attested token COUNT priced at the model rate (clamped) —
    the attested fallback, never the agent's word.

All amounts are exact Money (scale-4, never float). Comparison/clamp is on the Decimal `.amount`.
"""
from __future__ import annotations
from decimal import Decimal

from infra.settle import price
from infra.settle import reward_ledger as RL
from infra.settle.money import Money


def _tokens(d):
    return int((d or {}).get("in_tokens", 0)) + int((d or {}).get("out_tokens", 0))


def reconcile(meter, receipt, tol="0.05"):
    """Do exod's attested token meter and the provider receipt agree within RELATIVE tolerance `tol`?
    |meter_tokens - receipt_tokens| <= tol * receipt_tokens (exact Decimal; a zero receipt matches a zero meter)."""
    mt, rt = _tokens(meter), _tokens(receipt)
    if rt == 0:
        return mt == 0
    return abs(mt - rt) <= Decimal(str(tol)) * rt


def _clamp(amount, floor, cap):
    """Clamp an amount Money to [floor, cap] on the exact Decimal `.amount`."""
    if amount.amount < floor.amount:
        return floor
    if amount.amount > cap.amount:
        return cap
    return amount


def settleable(meter, receipt, rate, floor, cap, tol="0.05", cost_tol="0.10"):
    """Decide the settleable Money for a metered step. Returns a dict with `settleable` (bool), and when
    settleable: `amount` (str), `currency`, `source` ('receipt' pass-through | 'meter' attested-count),
    `clamped` (bool). When not: `reason`. A receipt is honoured only if it (a) is in the run's currency,
    (b) its TOKENS reconcile with the attested meter within `tol`, AND (c) its COST does not exceed the
    rate-implied cost of the attested token count by more than `cost_tol` — so a receipt cannot over-bill
    dollars while matching token volume. The cost is taken through Money's float-ban (str/int/Decimal only;
    a binary float is refused, not laundered through str())."""
    cur = floor.currency
    if not isinstance(meter, dict) or meter.get("by") != "exod":
        return {"settleable": False, "reason": "meter_not_attested", "source": None}
    if receipt is not None:
        if receipt.get("currency") and receipt["currency"] != cur:
            return {"settleable": False, "reason": "currency_mismatch", "source": "receipt"}
        if not reconcile(meter, receipt, tol):
            return {"settleable": False, "reason": "receipt_meter_mismatch", "source": "receipt"}
        cost = receipt.get("cost")
        if isinstance(cost, float) or cost is None:                 # float-ban: never launder a binary float
            return {"settleable": False, "reason": "receipt_cost_not_exact", "source": "receipt"}
        try:
            raw = Money(cost, cur)                                  # str/int/Decimal -> Money refuses a float
        except (TypeError, ValueError, ArithmeticError):
            return {"settleable": False, "reason": "receipt_cost_malformed", "source": "receipt"}
        est = price.llm_cost(meter.get("in_tokens", 0), meter.get("out_tokens", 0), rate)
        if raw.amount > est.amount * (Decimal(1) + Decimal(str(cost_tol))):   # cost bound to attested tokens x rate
            return {"settleable": False, "reason": "receipt_cost_exceeds_attested", "source": "receipt"}
        amount = _clamp(raw, floor, cap)                            # pass-through reimbursement of the real cost
        return {"settleable": True, "amount": str(amount.amount), "currency": cur, "source": "receipt",
                "within_tolerance": True, "clamped": amount.amount != raw.amount}
    raw = price.llm_cost(meter.get("in_tokens", 0), meter.get("out_tokens", 0), rate)   # attested-count fallback
    amount = _clamp(raw, floor, cap)
    return {"settleable": True, "amount": str(amount.amount), "currency": cur, "source": "meter",
            "within_tolerance": None, "clamped": amount.amount != raw.amount}


def reimbursement_posting(payer, provider, amount):
    """A pass-through reimbursement lane: the metered provider cost flows payer -> provider, balanced
    double-entry (so the reimbursement re-sums to zero per currency)."""
    return [RL._posting(payer, -amount), RL._posting(provider, amount)]


def metered_selftest():
    """meter+matching receipt -> settle at the receipt cost (reimbursement, balanced); meter+mismatched
    receipt -> unsettleable; no receipt -> the exod-count priced fallback; floor/cap clamp; an un-attested
    meter is refused. `ok` iff all hold."""
    rate = {"in_per_1k": "0.50", "out_per_1k": "1.50"}
    floor, cap = Money("0.0100", "USD"), Money("100.00", "USD")
    meter = {"by": "exod", "in_tokens": 1000, "out_tokens": 500, "wall_ms": 12}

    # receipt agrees within tolerance -> pass-through reimbursement at the receipt cost
    rcpt = {"in_tokens": 1010, "out_tokens": 495, "cost": "1.2500", "provider": "anthropic"}
    s_rcpt = settleable(meter, rcpt, rate, floor, cap)
    receipt_settles = s_rcpt["settleable"] and s_rcpt["source"] == "receipt" and s_rcpt["amount"] == "1.2500"
    posting = reimbursement_posting("payer", "provider", Money(s_rcpt["amount"], "USD"))
    reimbursement_balanced = RL.is_balanced(posting)

    # receipt that contradicts the attested meter (3x the tokens) -> unsettleable
    bad = {"in_tokens": 5000, "out_tokens": 500, "cost": "9.99"}
    mismatch_refused = settleable(meter, bad, rate, floor, cap)["reason"] == "receipt_meter_mismatch"

    # tokens match but the cost over-bills the attested estimate (~8x) -> unsettleable (not paid up to cap)
    overbill = {"in_tokens": 1010, "out_tokens": 495, "cost": "9.99"}
    overbill_refused = settleable(meter, overbill, rate, floor, cap)["reason"] == "receipt_cost_exceeds_attested"

    # a foreign-currency receipt is not silently relabeled
    foreign = {"in_tokens": 1010, "out_tokens": 495, "cost": "1.2500", "currency": "EUR"}
    currency_checked = settleable(meter, foreign, rate, floor, cap)["reason"] == "currency_mismatch"

    # a missing/non-numeric cost is refused as unsettleable, never a raw exception (float-cost refusal is
    # exercised in tests/test_metered.py — a float LITERAL cannot live in infra/settle under the float-ban)
    malformed_refused = (settleable(meter, {"in_tokens": 1010, "out_tokens": 495}, rate, floor, cap)["reason"]
                         == "receipt_cost_not_exact")

    # no receipt -> exod token COUNT priced (0.50*1 + 1.50*0.5 = 1.2500)
    s_meter = settleable(meter, None, rate, floor, cap)
    meter_fallback = s_meter["settleable"] and s_meter["source"] == "meter" and s_meter["amount"] == "1.2500"

    # floor clamp (receipt within cost tolerance but below floor) + cap clamp (attested-count price over cap)
    tiny = {"in_tokens": 1000, "out_tokens": 500, "cost": "0.0001"}
    clamp_floor = settleable(meter, tiny, rate, floor, cap)["amount"] == "0.0100"
    big_meter = {"by": "exod", "in_tokens": 1_000_000, "out_tokens": 0}      # 0.50*1000 = 500.00 > cap
    clamp_cap = settleable(big_meter, None, rate, floor, cap)["amount"] == "100.0000"

    # an un-attested meter is never settleable
    unattested = settleable({"by": "agent", "in_tokens": 1000, "out_tokens": 500}, rcpt, rate, floor, cap)
    attested_required = unattested["settleable"] is False and unattested["reason"] == "meter_not_attested"

    ok = bool(receipt_settles and reimbursement_balanced and mismatch_refused and overbill_refused
              and currency_checked and malformed_refused and meter_fallback and clamp_floor and clamp_cap
              and attested_required)
    return {"receipt_settles": receipt_settles, "reimbursement_balanced": reimbursement_balanced,
            "mismatch_refused": mismatch_refused, "overbill_refused": overbill_refused,
            "currency_checked": currency_checked, "malformed_refused": malformed_refused,
            "meter_fallback": meter_fallback, "clamp_floor": clamp_floor, "clamp_cap": clamp_cap,
            "attested_required": attested_required, "ok": ok}


if __name__ == "__main__":
    import json
    import sys
    r = metered_selftest()
    print(json.dumps(r, indent=2))
    sys.exit(0 if r["ok"] else 1)
