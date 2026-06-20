"""The plan pricer (infra/settle/price.py) — price a governed run from its value-free shape, BEFORE it runs.

The product property under test: a deterministic, itemized, exact-decimal quote derived from the plan (no
execution, no generation), so a charge for `total` reconciles to the cent — and no float ever touches it.
"""
from decimal import Decimal

from infra.settle import price
from infra.settle.money import Money, float_ban_scan


def test_price_selftest_all_true():
    assert all(price.price_selftest().values())


def test_itemized_total_is_exact():
    q = price.price_plan("fs", "find_large")
    assert Money(q["subtotal"]) == Money(q["llm"]["cost"]) + Money(q["tool_fee"])   # subtotal = LLM + tool fee
    assert Money(q["total"]) == Money(q["subtotal"]) + Money(q["marketplace_fee"])  # total = subtotal + market fee
    assert Money(q["total"]) > Money("0") and q["currency"] == "USD"


def test_tool_fee_comes_from_the_gov_provider_config():
    pr = price.load_pricing()
    pr["tool_fees"] = {"_default": "0", "fs/find_large": "0.4200"}
    assert Money(price.price_plan("fs", "find_large", pricing=pr)["tool_fee"]) == Money("0.4200")


def test_structured_and_freeform_price_different_output():
    s = price.price_plan("fs", "find_large", mode="structured")
    f = price.price_plan("fs", "find_large", mode="freeform")
    assert f["llm"]["output_tokens"] != s["llm"]["output_tokens"]   # the model writes the script => more output


def test_no_float_touches_the_pricer():
    assert float_ban_scan([price.__file__]) == []


def test_pricing_json_amounts_are_strings_not_floats():
    pr = price.load_pricing()              # a JSON float would be refused at Money construction (float-ban)
    for r in pr["model_rates"].values():
        assert isinstance(r["in_per_1k"], str) and isinstance(r["out_per_1k"], str)
        Money(r["in_per_1k"]); Money(r["out_per_1k"])           # constructible as exact Money
    for v in pr["tool_fees"].values():
        assert isinstance(v, str); Money(v)


def test_quote_is_deterministic():
    a = price.price_plan("fs", "find_large")
    b = price.price_plan("fs", "find_large")
    assert a == b and Decimal(a["total"]) == Decimal(b["total"])   # same plan -> same price, every time
