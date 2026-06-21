"""Credit-based usage billing (infra/settle/credits.py) — prepaid balance + per-call DEBITS, no per-call fee.

The model: one top-up (a single Stripe charge, flat fee amortized) funds a balance; each priced run debits its
real usage tax internally (zero-sum, the transparent split posted), refused if the balance can't cover it (the
gate), idempotent per run. No float touches it.
"""
from infra.settle import credits, price, rails, reward_ledger
from infra.settle.money import Money, float_ban_scan


def test_credits_selftest_all_true():
    assert all(credits.credits_selftest().values())


def test_topup_then_debit_draws_down_zero_sum():
    led = reward_ledger.open_ledger()
    credits.topup(led, "acme", Money("10.00"), ref="t1")
    assert credits.balance(led, "acme") == Money("10.00")
    ch = rails.charge_from_price(price.price_plan("http", "get"), "PSHA")
    r = credits.debit_usage(led, "acme", ch, "PSHA")
    assert r["status"] == "debited"
    assert credits.balance(led, "acme") == Money("10.00") - Money(ch["total"])    # real usage tax, no fee
    assert reward_ledger.global_zero(led)


def test_insufficient_credits_is_the_gate():
    led = reward_ledger.open_ledger()
    credits.topup(led, "acme", Money("0.0010"), ref="t1")                         # balance < the tax
    ch = rails.charge_from_price(price.price_plan("http", "get"), "PSHA")
    assert not credits.admits(led, "acme", ch["total"])
    r = credits.debit_usage(led, "acme", ch, "PSHA")
    assert r["status"] == "insufficient_credits"
    assert credits.balance(led, "acme") == Money("0.0010")                        # refused -> no draw-down


def test_debit_is_idempotent_per_run():
    led = reward_ledger.open_ledger()
    credits.topup(led, "acme", Money("1.00"), ref="t1")
    ch = rails.charge_from_price(price.price_plan("http", "get"), "PSHA")
    credits.debit_usage(led, "acme", ch, "PSHA")
    after = credits.balance(led, "acme")
    assert credits.debit_usage(led, "acme", ch, "PSHA")["status"] == "duplicate"
    assert credits.balance(led, "acme") == after                                  # no double debit


def test_topup_is_idempotent_per_ref():
    led = reward_ledger.open_ledger()
    credits.topup(led, "acme", Money("10.00"), ref="t1")
    assert credits.topup(led, "acme", Money("10.00"), ref="t1")["status"] == "duplicate"
    assert credits.balance(led, "acme") == Money("10.00")                         # not credited twice


def test_credit_rail_plugs_into_collect_run_tax():
    led = reward_ledger.open_ledger()
    credits.topup(led, "acme", Money("5.00"), ref="t1")
    out = rails.collect_run_tax("http", "get", "PSHA", rail=rails.CreditRail(led, "acme"))
    assert out["receipt"]["status"] == "debited" and Money(out["receipt"]["balance_after"]) < Money("5.00")


def test_no_float_in_credits():
    assert float_ban_scan([credits.__file__]) == []
