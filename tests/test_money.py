"""The Money type for SV-6 (P6-T01): exact decimal at scale 4, HALF_EVEN, never a binary float. A float is
refused at construction, the float-ban lint finds zero intrusions in the settlement modules (and fires on a
seed), and a split re-sums to the total exactly. Pure stdlib; no skip guard."""
from __future__ import annotations
import random
from decimal import Decimal

import pytest

from infra.settle import money as M


def test_money_selftest():
    r = M.money_selftest()
    assert r["ok"], r
    assert r["half_even"] and r["float_refused"] and r["conserve"] and r["split_exact"]


def test_float_ban_clean_on_settle_and_fires_on_seed():
    r = M.float_ban_selftest()
    assert r["ok"], r
    assert r["settle_float_occurrences"] == 0 and r["settle_clean"]
    assert r["lint_fires_on_seed"] and set(r["seed_kinds"]) == {"float_literal", "float_call"}


def test_float_is_refused_everywhere():
    f = 1 / 4                                                  # a runtime float, no literal
    with pytest.raises(TypeError):
        M.Money(f)
    with pytest.raises(TypeError):
        M.Money("1.00").scale(f)
    with pytest.raises(TypeError):
        M.Money(True)                                         # bool is not a money amount


def test_half_even_at_scale4():
    assert M.Money("1.23455").amount == Decimal("1.2346")
    assert M.Money("1.23445").amount == Decimal("1.2344")
    assert M.Money("2.50005").amount == Decimal("2.5000")     # rounds to even


def test_currency_mismatch_rejected():
    with pytest.raises(ValueError):
        M.Money("1", "USD") + M.Money("1", "EUR")


@pytest.mark.parametrize("seed", range(5))
def test_split_always_resums_to_total(seed):
    rng = random.Random(seed)
    for _ in range(400):
        total = M.Money(Decimal(rng.randint(0, 5_000_000)) * M.QUANT)
        weights = [rng.randint(1, 50) for _ in range(rng.randint(2, 6))]
        parts = M.split(total, weights)
        s = parts[0]
        for p in parts[1:]:
            s = s + p
        assert s == total, (total, weights, parts)
