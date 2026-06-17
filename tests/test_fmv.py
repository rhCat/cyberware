"""FMV indices for SV-6 (P6-T11): a trimmed, control-capped, volume-weighted median. For an admitted
UNIMODAL market, 20% adversarial volume moves the index <2%; a MULTIMODAL market (two price clusters) is
refused as provisional (so a gap-positioning attack has no firm index to move); sub-admission is provisional;
sybils collapse to one controller. Pure stdlib."""
from __future__ import annotations
from decimal import Decimal

from infra.settle import fmv as F


def test_selftest():
    r = F.fmv_selftest()
    assert r["ok"], r


def test_unimodal_bound_and_multimodal_refusal():
    r = F.fmv_selftest()
    assert r["unimodal_market_admitted"]
    assert r["manipulation_bounded_under_2pct"] and Decimal(r["adversarial_move_pct"]) < Decimal("2")
    # the adversarial-review regression: a bimodal market is NOT published as a firm index, and a
    # gap-positioning attack cannot turn it into one
    assert r["multimodal_refused_as_provisional"] and r["gap_attack_refused"]
    assert r["sub_admission_provisional"] and r["common_control_collapsed"]


def test_bimodal_is_provisional_not_a_firm_index():
    bimodal = ([{"skill": "s", "perk": "p", "price": "1.0000", "volume": 10, "control": f"lo-{i}"} for i in range(12)]
               + [{"skill": "s", "perk": "p", "price": "5.0000", "volume": 10, "control": f"hi-{i}"} for i in range(12)])
    idx = F.fmv_index(bimodal)
    assert idx["multimodal"] and idx["provisional"] and idx["reason"] == "multimodal_needs_class_split"


def test_unimodal_admits_with_a_firm_index():
    unimodal = [{"skill": "s", "perk": "p", "price": str(Decimal("10.0000") + Decimal(i % 5) * Decimal("0.0100")),
                 "volume": 10, "control": f"c-{i}"} for i in range(24)]
    idx = F.fmv_index(unimodal)
    assert idx["admitted"] and not idx["multimodal"] and idx["index"].amount > 0
