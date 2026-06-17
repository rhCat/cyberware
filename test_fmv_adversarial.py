#!/usr/bin/env python3
"""Aggressive adversarial tests for FMV manipulation resistance.
Goal: Refute the claim that 20% adversarial volume moves the index <2%."""

import sys
sys.path.insert(0, '/Users/user/hunyuan/cyberware')

from decimal import Decimal
from infra.settle.fmv import fmv_index, _move_pct, _collapse_controls, _trim, _vw_median
from infra.settle.money import Money
import random


def baseline_naive_mean(trades):
    """A NON-robust baseline: plain volume-weighted mean of prices (NO control capping, NO trimming)."""
    total_price_vol = Decimal(0)
    total_vol = 0
    for t in trades:
        if int(t["volume"]) > 0:
            price = Money(t["price"])
            vol = int(t["volume"])
            total_price_vol += price.amount * Decimal(vol)
            total_vol += vol
    if total_vol == 0:
        return Money.zero()
    return Money(total_price_vol / Decimal(total_vol))


def test_weak_adversary():
    """Test (a): Confirm a naive baseline WOULD move significantly under the same 20% attack.
    If both naive and robust move ~0%, the test attack is too weak."""
    print("\n=== TEST A: Weak Adversary (20% volume at 3x price) ===")
    
    rng = random.Random(42)
    # Honest market: tight clustering around 1.0
    honest = []
    for c in range(24):
        price = Decimal("1.0000") + Decimal(rng.randint(-50, 50)) * Decimal("0.0001")
        honest.append({"skill": "s", "perk": "p", "price": str(price), "volume": rng.randint(8, 12),
                       "control": f"ctrl-{c}"})
    
    base_robust = fmv_index(honest)
    base_naive = baseline_naive_mean(honest)
    
    honest_vol = sum(t["volume"] for t in honest)
    adv_vol = max(1, honest_vol // 5)  # 20%
    attacked = honest + [{"skill": "s", "perk": "p", "price": "3.0000", "volume": adv_vol, "control": "adv"}]
    
    attacked_robust = fmv_index(attacked)
    attacked_naive = baseline_naive_mean(attacked)
    
    robust_move = _move_pct(base_robust["index"], attacked_robust["index"])
    naive_move = _move_pct(base_naive, attacked_naive)
    
    print(f"Honest market:")
    print(f"  Robust index: {base_robust['index'].amount}")
    print(f"  Naive mean:   {base_naive.amount}")
    print(f"  Distinct controls: {base_robust['distinct_controllers']}")
    print(f"\nAfter 20% adversarial volume at 3x price:")
    print(f"  Robust index move: {robust_move:.4f}%")
    print(f"  Naive mean move:   {naive_move:.4f}%")
    print(f"\nVERDICT: Weak attack. Naive is weak too? {naive_move < Decimal('2')}")
    if naive_move < Decimal('2'):
        print("  SUSPICIOUS: attack is too weak to distinguish robust from naive.")
    else:
        print(f"  OK: Naive moves {naive_move:.2f}%, robust {robust_move:.2f}% — capping works.")
    
    return {"robust_move": robust_move, "naive_move": naive_move, "adv_vol": adv_vol}


def test_strong_adversary_extreme_price():
    """Test (b): Push the adversary harder — use 10x/100x price, not 3x."""
    print("\n=== TEST B: Stronger Adversary (20% volume at 10x/100x price) ===")
    
    rng = random.Random(42)
    honest = []
    for c in range(24):
        price = Decimal("1.0000") + Decimal(rng.randint(-50, 50)) * Decimal("0.0001")
        honest.append({"skill": "s", "perk": "p", "price": str(price), "volume": rng.randint(8, 12),
                       "control": f"ctrl-{c}"})
    
    base_robust = fmv_index(honest)
    honest_vol = sum(t["volume"] for t in honest)
    adv_vol = max(1, honest_vol // 5)
    
    results = []
    for multiplier in [10, 100]:
        attacked = honest + [{"skill": "s", "perk": "p", 
                             "price": str(Decimal(multiplier)), 
                             "volume": adv_vol, "control": f"adv-{multiplier}x"}]
        attacked_idx = fmv_index(attacked)
        move = _move_pct(base_robust["index"], attacked_idx["index"])
        results.append((multiplier, move))
        print(f"  {multiplier}x price: move = {move:.4f}%")
    
    return results


def test_multiple_colluders():
    """Test (b): 2-3 colluding controllers splitting adversary volume.
    Even though each is capped individually, they collectively can push harder."""
    print("\n=== TEST B2: Multiple Colluding Controllers (20% split across 2-3 controllers) ===")
    
    rng = random.Random(42)
    honest = []
    for c in range(24):
        price = Decimal("1.0000") + Decimal(rng.randint(-50, 50)) * Decimal("0.0001")
        honest.append({"skill": "s", "perk": "p", "price": str(price), "volume": rng.randint(8, 12),
                       "control": f"ctrl-{c}"})
    
    base_robust = fmv_index(honest)
    honest_vol = sum(t["volume"] for t in honest)
    total_adv_vol = max(1, honest_vol // 5)  # 20% total
    
    results = []
    for num_colluders in [2, 3]:
        attacked = list(honest)
        adv_vol_per = total_adv_vol // num_colluders
        for i in range(num_colluders):
            attacked.append({
                "skill": "s", "perk": "p", 
                "price": "10.0000",  # extreme price
                "volume": adv_vol_per,
                "control": f"colluder-{i}"
            })
        
        attacked_idx = fmv_index(attacked)
        move = _move_pct(base_robust["index"], attacked_idx["index"])
        results.append((num_colluders, move))
        print(f"  {num_colluders} colluders: move = {move:.4f}%")
    
    return results


def test_threshold_gaming():
    """Test (c): Attack the trim & cap thresholds.
    Adversary places volume JUST UNDER the cap threshold or JUST INSIDE the trim boundaries."""
    print("\n=== TEST C: Threshold Gaming (volume placed at trim/cap boundaries) ===")
    
    rng = random.Random(42)
    honest = []
    for c in range(24):
        price = Decimal("1.0000") + Decimal(rng.randint(-50, 50)) * Decimal("0.0001")
        honest.append({"skill": "s", "perk": "p", "price": str(price), "volume": 10,
                       "control": f"ctrl-{c}"})
    
    base_robust = fmv_index(honest)
    honest_vol = sum(t["volume"] for t in honest)
    
    # The cap is total_vol // distinct (after collapsing)
    # The trim is top/bottom 10% by volume
    cap_threshold = honest_vol // 24
    trim_vol = Decimal(honest_vol) * Decimal("0.1")
    
    print(f"  Honest total vol: {honest_vol}")
    print(f"  Cap per controller: {cap_threshold}")
    print(f"  Trim fraction (10%): {trim_vol}")
    
    # Attack 1: Adversary volume just under the cap
    adv_vol_under_cap = max(1, cap_threshold - 1)
    attacked = honest + [{"skill": "s", "perk": "p", "price": "0.0001", 
                         "volume": adv_vol_under_cap, "control": "adv-under"}]
    move_under = _move_pct(base_robust["index"], fmv_index(attacked)["index"])
    print(f"  Adv volume {adv_vol_under_cap} (just under cap): move = {move_under:.4f}%")
    
    # Attack 2: Adversary volume exactly at the cap
    adv_vol_at_cap = cap_threshold
    attacked = honest + [{"skill": "s", "perk": "p", "price": "0.0001", 
                         "volume": adv_vol_at_cap, "control": "adv-at"}]
    move_at = _move_pct(base_robust["index"], fmv_index(attacked)["index"])
    print(f"  Adv volume {adv_vol_at_cap} (exactly at cap): move = {move_at:.4f}%")
    
    # Attack 3: Adversary volume exceeding the cap (should be capped)
    adv_vol_over_cap = cap_threshold + 100
    attacked = honest + [{"skill": "s", "perk": "p", "price": "0.0001", 
                         "volume": adv_vol_over_cap, "control": "adv-over"}]
    move_over = _move_pct(base_robust["index"], fmv_index(attacked)["index"])
    print(f"  Adv volume {adv_vol_over_cap} (well over cap): move = {move_over:.4f}%")
    
    return {"under": move_under, "at": move_at, "over": move_over}


def test_control_label_trust():
    """Test (d): Does the algorithm trust the adversary's 'control' label?
    The algorithm collapses by the control field — if adversary can forge a 'control' label,
    they can evade the common-control capping entirely."""
    print("\n=== TEST D: Control Label Trust (adversary supplies false control) ===")
    
    rng = random.Random(42)
    honest = []
    for c in range(24):
        price = Decimal("1.0000") + Decimal(rng.randint(-50, 50)) * Decimal("0.0001")
        honest.append({"skill": "s", "perk": "p", "price": str(price), "volume": 10,
                       "control": f"ctrl-{c}"})
    
    base_robust = fmv_index(honest)
    honest_vol = sum(t["volume"] for t in honest)
    adv_vol = max(1, honest_vol // 5)
    
    # Scenario 1: Adversary uses ONE control label (as per selftest)
    attacked_honest = honest + [{"skill": "s", "perk": "p", "price": "10.0000", 
                                 "volume": adv_vol, "control": "adv"}]
    move_honest = _move_pct(base_robust["index"], fmv_index(attacked_honest)["index"])
    print(f"  Adversary with single control 'adv': move = {move_honest:.4f}%")
    
    # Scenario 2: Adversary FORGES multiple control labels (splits volume across fake IDs)
    # This should NOT help if we detect sybils, but the algorithm doesn't have sybil detection
    attacked_sybil = list(honest)
    for i in range(5):
        attacked_sybil.append({
            "skill": "s", "perk": "p", "price": "10.0000",
            "volume": adv_vol // 5,
            "control": f"fake-ctrl-{i}"  # Forged ID
        })
    move_sybil = _move_pct(base_robust["index"], fmv_index(attacked_sybil)["index"])
    distinct_sybil = fmv_index(attacked_sybil)["distinct_controllers"]
    print(f"  Adversary with 5 forged controls (sybil split): move = {move_sybil:.4f}%")
    print(f"    (distinct controllers jumped to {distinct_sybil})")
    
    print("\n  VERDICT: The algorithm TRUSTS the control label. A sybil attacker with fake")
    print("  control IDs can bypass the common-control cap entirely.")
    
    return {"honest": move_honest, "sybil": move_sybil, "distinct_after_sybil": distinct_sybil}


def test_extreme_setup():
    """Test (b) extended: Absolute worst case — maximize all attack vectors simultaneously."""
    print("\n=== TEST B3: Worst-Case Scenario (all attack vectors at once) ===")
    
    rng = random.Random(42)
    # Minimal honest market: exactly 8 distinct controllers (minimum for admission)
    honest = []
    for c in range(8):
        price = Decimal("1.0000") + Decimal(rng.randint(-20, 20)) * Decimal("0.0001")
        honest.append({"skill": "s", "perk": "p", "price": str(price), "volume": 10,
                       "control": f"ctrl-{c}"})
    
    base_robust = fmv_index(honest)
    honest_vol = sum(t["volume"] for t in honest)
    total_adv_vol = honest_vol // 2  # 50% adversarial volume (even more aggressive)
    
    print(f"  Honest market: {len(honest)} trades, 8 controllers, volume {honest_vol}")
    print(f"  Adversary injects: {total_adv_vol} volume (50%)")
    
    results = []
    
    # Single high-price attacker
    attacked = honest + [{"skill": "s", "perk": "p", "price": "100.0000", 
                         "volume": total_adv_vol, "control": "adv-1"}]
    move = _move_pct(base_robust["index"], fmv_index(attacked)["index"])
    results.append(("1 controller, 100x price", move))
    print(f"  1 controller @ 100x: move = {move:.4f}%")
    
    # Two colluders, extreme price
    attacked = list(honest)
    for i in range(2):
        attacked.append({"skill": "s", "perk": "p", "price": "100.0000", 
                        "volume": total_adv_vol // 2, "control": f"adv-{i}"})
    move = _move_pct(base_robust["index"], fmv_index(attacked)["index"])
    results.append(("2 controllers @ 100x", move))
    print(f"  2 controllers @ 100x: move = {move:.4f}%")
    
    # Single low-price attacker (inverse attack)
    attacked = honest + [{"skill": "s", "perk": "p", "price": "0.0001", 
                         "volume": total_adv_vol, "control": "adv-low"}]
    move = _move_pct(base_robust["index"], fmv_index(attacked)["index"])
    results.append(("1 controller, 0.0001 price", move))
    print(f"  1 controller @ 0.0001: move = {move:.4f}%")
    
    return results


def test_trim_off_by_one():
    """Test (c): Check the trim+cap math for off-by-one or boundary issues.
    Specifically: does the trim correctly handle fractional volumes?"""
    print("\n=== TEST C2: Trim Math (fractional volume handling) ===")
    
    # Construct a portfolio with simple integer volumes
    simple_trades = [
        {"skill": "s", "perk": "p", "price": "1.0000", "volume": 10, "control": "a"},
        {"skill": "s", "perk": "p", "price": "2.0000", "volume": 10, "control": "b"},
        {"skill": "s", "perk": "p", "price": "3.0000", "volume": 10, "control": "c"},
        {"skill": "s", "perk": "p", "price": "4.0000", "volume": 10, "control": "d"},
        {"skill": "s", "perk": "p", "price": "5.0000", "volume": 10, "control": "e"},
        {"skill": "s", "perk": "p", "price": "6.0000", "volume": 10, "control": "f"},
        {"skill": "s", "perk": "p", "price": "7.0000", "volume": 10, "control": "g"},
        {"skill": "s", "perk": "p", "price": "8.0000", "volume": 10, "control": "h"},
    ]
    
    # After collapsing (8 controllers, 1 trade each), volumes are [10, 10, ..., 10] = 80 total
    collapsed = _collapse_controls(simple_trades)
    print(f"  After collapse: {len(collapsed)} entries, total vol = {sum(v for _, v in collapsed)}")
    
    # Trim: 10% bottom + 10% top = 8 volume on each side, leaving 64 in the middle
    trimmed = _trim(collapsed)
    trimmed_vol = sum(v for _, v in trimmed)
    print(f"  After trim: {len(trimmed)} entries, total vol = {trimmed_vol}")
    
    # The median should be at ~32 units (50% of 64), which is at price 4.5
    median = _vw_median(trimmed)
    print(f"  Trimmed median: {median.amount}")
    
    # Sanity check: was 20 units actually dropped?
    if sum(v for _, v in collapsed) - trimmed_vol == 20:
        print(f"  ✓ Trim removed exactly 20 units (10 + 10)")
    else:
        print(f"  ✗ Trim math issue: expected to remove 20, actually removed {sum(v for _, v in collapsed) - trimmed_vol}")
    
    return {"collapsed_vol": sum(v for _, v in collapsed), "trimmed_vol": trimmed_vol}


if __name__ == "__main__":
    print("=" * 70)
    print("FMV MANIPULATION RESISTANCE ADVERSARIAL TEST SUITE")
    print("=" * 70)
    
    results = {}
    results["test_a"] = test_weak_adversary()
    results["test_b"] = test_strong_adversary_extreme_price()
    results["test_b2"] = test_multiple_colluders()
    results["test_b3"] = test_extreme_setup()
    results["test_c"] = test_threshold_gaming()
    results["test_c2"] = test_trim_off_by_one()
    results["test_d"] = test_control_label_trust()
    
    print("\n" + "=" * 70)
    print("SUMMARY")
    print("=" * 70)
    
    # Check for refutation
    refuted = False
    issues = []
    
    if results["test_a"]["robust_move"] < Decimal("0.5") and results["test_a"]["naive_move"] < Decimal("2"):
        issues.append("Test A: Attack too weak (naive also <2%) — cannot distinguish robustness")
        refuted = True
    
    for mult, move in results["test_b"]:
        if move >= Decimal("2"):
            issues.append(f"Test B: {mult}x price move = {move:.2f}% >= 2% (refuted)")
            refuted = True
    
    for num, move in results["test_b2"]:
        if move >= Decimal("2"):
            issues.append(f"Test B2: {num} colluders move = {move:.2f}% >= 2% (refuted)")
            refuted = True
    
    for scenario, move in results["test_b3"]:
        if move >= Decimal("2"):
            issues.append(f"Test B3: {scenario} move = {move:.2f}% >= 2% (refuted)")
            refuted = True
    
    for scenario, move in results["test_c"].items():
        if move >= Decimal("2"):
            issues.append(f"Test C: Threshold {scenario} move = {move:.2f}% >= 2% (refuted)")
            refuted = True
    
    # Control label trust is a design assumption, not a refutation
    honest_move = results["test_d"]["honest"]
    sybil_move = results["test_d"]["sybil"]
    if sybil_move > honest_move * Decimal("1.5"):
        issues.append(f"Test D: Sybil attack {sybil_move:.2f}% >> honest {honest_move:.2f}% — control label is trusted")
    
    print("\nREFUTATION CHECK:")
    if refuted:
        print("✗ CLAIM REFUTED — Found attack vectors that move index >= 2%:")
        for issue in issues:
            print(f"  - {issue}")
    else:
        print("✓ Claim holds under these tests")
        if issues:
            print("  Design assumptions identified (not refutations):")
            for issue in issues:
                print(f"  - {issue}")
        else:
            print("  All attacks < 2%")

