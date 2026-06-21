"""The settlement rail (infra/settle/rails.py) — collect the platform tax at settle, TRANSPARENTLY.

Properties under test: the tax is the pricer's named split (substrate/skill-author/marketplace — the platform
tax is a VISIBLE line, not a hidden portal), collected by double entry (zero-sum), idempotent per plan_sha,
a skim is refused, Stripe is inert until the operator wires a key, and no float touches it.
"""
import pytest

from infra.settle import price, rails, reward_ledger
from infra.settle.money import Money, float_ban_scan


def test_rails_selftest_all_true():
    assert all(rails.rails_selftest().values())


def test_charge_is_transparent_named_split_that_balances():
    ch = rails.charge_from_price(price.price_plan("http", "get"), "PSHA")
    assert [b["account"] for b in ch["breakdown"]] == ["substrate", "skill_author", "marketplace"]
    assert rails.split_balances(ch)                                 # re-sums to total exactly — no skim


def test_ledger_rail_zero_sum_idempotent_and_lines_land():
    ch = rails.charge_from_price(price.price_plan("http", "get"), "PSHA")
    led = reward_ledger.open_ledger()
    rail = rails.LedgerRail(led)
    r1 = rails.collect_tax(ch, rail, "PSHA")
    r2 = rails.collect_tax(ch, rail, "PSHA")                        # same plan_sha -> at most once
    assert r1["status"] == "collected" and r2["status"] == "duplicate"
    assert reward_ledger.global_zero(led)                           # double-entry, nothing created
    bal = reward_ledger.balances(led)
    mkt = next(b["amount"] for b in ch["breakdown"] if b["account"] == "marketplace")
    assert bal[("marketplace", "USD")] == Money(mkt, "USD")         # the platform got EXACTLY its visible line
    assert bal[("operator", "USD")] == -Money(ch["total"], "USD")   # the operator paid exactly the quoted total


def test_a_skim_is_refused():
    ch = rails.charge_from_price(price.price_plan("http", "get"), "PSHA")
    skim = dict(ch, total=str((Money(ch["total"], "USD") + Money("5", "USD")).amount))   # claim more than the split
    with pytest.raises(ValueError):
        rails.collect_tax(skim, rails.LedgerRail(reward_ledger.open_ledger()), "X")


def test_stripe_rail_is_inert_until_keyed():
    ch = rails.charge_from_price(price.price_plan("http", "get"), "PSHA")
    r = rails.StripeRail().collect(ch, "X")                          # no key_file -> never charges
    assert r["status"] == "unconfigured" and r["would_charge"] == ch["total"]


def test_usd_to_minor_cents_and_subcent():
    assert rails.usd_to_minor("1.0000") == 100 and rails.usd_to_minor("0.5000") == 50
    assert rails.usd_to_minor("0.0072") == 0                        # sub-cent -> below Stripe's ~$0.50 minimum


def test_collect_run_tax_prices_then_collects():
    out = rails.collect_run_tax("http", "get", "PSHA", rail=rails.LedgerRail(reward_ledger.open_ledger()))
    assert out["receipt"]["status"] == "collected"
    assert Money(out["charge"]["total"], "USD") > Money("0") and "llm" in out["price"]


def test_stripe_charge_below_minimum_makes_no_network_call(tmp_path):
    keyf = tmp_path / "k"
    keyf.write_text("sk_test_dummy")                               # never read: below_minimum returns first
    ch = rails.charge_from_price(price.price_plan("fs", "find_large"), "PSHA")   # sub-cent total
    r = rails.StripeRail({"key_file": str(keyf)}).collect(ch, "PSHA")
    assert r["status"] == "below_minimum" and r["would_charge"] == ch["total"]


def test_no_float_in_rails():
    assert float_ban_scan([rails.__file__]) == []
