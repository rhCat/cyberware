"""P6-T08 — attested meters become settleable + provider-receipt capture (infra/settle/metered.py).

Pins the settleability doctrine: exod-attested meter required; a reconciling provider receipt settles as a
pass-through reimbursement (clamped); a contradicting receipt is unsettleable; absent a receipt the exod
token count is the priced fallback; floor/cap clamp; the reimbursement posting is balanced double-entry."""
from __future__ import annotations

from infra.settle import metered as M
from infra.settle import reward_ledger as RL
from infra.settle.money import Money

RATE = {"in_per_1k": "0.50", "out_per_1k": "1.50"}
FLOOR, CAP = Money("0.0100", "USD"), Money("100.00", "USD")
METER = {"by": "exod", "in_tokens": 1000, "out_tokens": 500, "wall_ms": 12.3}


def test_reconcile_within_and_beyond_tolerance():
    assert M.reconcile(METER, {"in_tokens": 1010, "out_tokens": 495}) is True     # 1505 vs 1500, within 5%
    assert M.reconcile(METER, {"in_tokens": 5000, "out_tokens": 500}) is False    # 5500 vs 1500, way over
    assert M.reconcile({"in_tokens": 0, "out_tokens": 0}, {"in_tokens": 0, "out_tokens": 0}) is True
    # a zero-token receipt reconciles ONLY with a zero-token meter (rt==0 path -> requires mt==0)
    assert M.reconcile(METER, {"in_tokens": 0, "out_tokens": 0}) is False
    assert M.reconcile({"in_tokens": 5, "out_tokens": 0}, {"in_tokens": 0, "out_tokens": 0}) is False


def test_receipt_pass_through_reimbursement():
    s = M.settleable(METER, {"in_tokens": 1010, "out_tokens": 495, "cost": "1.2500"}, RATE, FLOOR, CAP)
    assert s["settleable"] and s["source"] == "receipt" and s["amount"] == "1.2500"
    posting = M.reimbursement_posting("payer", "provider", Money(s["amount"], "USD"))
    assert RL.is_balanced(posting)                                                # double-entry, sums to zero


def test_mismatched_tokens_unsettleable():
    s = M.settleable(METER, {"in_tokens": 5000, "out_tokens": 500, "cost": "9.99"}, RATE, FLOOR, CAP)
    assert s["settleable"] is False and s["reason"] == "receipt_meter_mismatch"   # never pay a disputed receipt


def test_cost_overbill_unsettleable():
    # tokens reconcile but the cost is ~8x the attested estimate -> rejected, NOT clamped-and-paid up to cap
    s = M.settleable(METER, {"in_tokens": 1010, "out_tokens": 495, "cost": "9.99"}, RATE, FLOOR, CAP)
    assert s["settleable"] is False and s["reason"] == "receipt_cost_exceeds_attested"


def test_foreign_currency_receipt_unsettleable():
    s = M.settleable(METER, {"in_tokens": 1010, "out_tokens": 495, "cost": "1.2500", "currency": "EUR"},
                     RATE, FLOOR, CAP)
    assert s["settleable"] is False and s["reason"] == "currency_mismatch"         # no silent relabel/FX


def test_float_cost_refused_at_the_boundary():
    # a binary float must not be laundered through str() — the float-ban holds at the untrusted receipt boundary
    s = M.settleable(METER, {"in_tokens": 1010, "out_tokens": 495, "cost": 1.25}, RATE, FLOOR, CAP)
    assert s["settleable"] is False and s["reason"] == "receipt_cost_not_exact"


def test_malformed_or_missing_cost_unsettleable():
    assert M.settleable(METER, {"in_tokens": 1010, "out_tokens": 495}, RATE, FLOOR, CAP)["reason"] \
        == "receipt_cost_not_exact"                                                # missing cost, no raw exception
    assert M.settleable(METER, {"in_tokens": 1010, "out_tokens": 495, "cost": "abc"}, RATE, FLOOR, CAP)["reason"] \
        == "receipt_cost_malformed"                                                # non-numeric, no raw exception


def test_absent_receipt_prices_the_attested_count():
    s = M.settleable(METER, None, RATE, FLOOR, CAP)                               # 0.50*1 + 1.50*0.5 = 1.2500
    assert s["settleable"] and s["source"] == "meter" and s["amount"] == "1.2500"


def test_floor_and_cap_clamp():
    lo = M.settleable(METER, {"in_tokens": 1000, "out_tokens": 500, "cost": "0.0001"}, RATE, FLOOR, CAP)
    assert lo["amount"] == "0.0100" and lo["clamped"] is True                     # receipt below floor -> floor
    big = {"by": "exod", "in_tokens": 1_000_000, "out_tokens": 0}                 # attested-count price 500 > cap
    hi = M.settleable(big, None, RATE, FLOOR, CAP)
    assert hi["amount"] == "100.0000" and hi["clamped"] is True                   # meter-path price over cap -> cap


def test_unattested_meter_is_never_settleable():
    s = M.settleable({"by": "agent", "in_tokens": 1000, "out_tokens": 500},
                     {"in_tokens": 1000, "out_tokens": 500, "cost": "1.25"}, RATE, FLOOR, CAP)
    assert s["settleable"] is False and s["reason"] == "meter_not_attested"


def test_selftest_ok():
    assert M.metered_selftest()["ok"] is True
