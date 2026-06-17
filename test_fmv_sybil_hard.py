#!/usr/bin/env python3
"""Aggressive sybil attack on the FMV index.
The algorithm trusts the 'control' label — an adversary can forge many fake controls
and bypass the per-controller cap entirely."""

import sys
sys.path.insert(0, '/Users/ruihe/hunyuan/cyberware')

from decimal import Decimal
from infra.settle.fmv import fmv_index, _move_pct
from infra.settle.money import Money
import random


def test_sybil_scaling():
    """Push the sybil attack to the limit: adversary with N forged controls.
    Each control gets its own cap; more controls = more total adversary influence."""
    print("\n=== SYBIL ATTACK: Scaling the Number of Forged Controls ===")
    
    rng = random.Random(42)
    honest = []
    for c in range(24):
        price = Decimal("1.0000") + Decimal(rng.randint(-50, 50)) * Decimal("0.0001")
        honest.append({"skill": "s", "perk": "p", "price": str(price), "volume": 10,
                       "control": f"ctrl-{c}"})
    
    base = fmv_index(honest)
    base_idx = base["index"]
    honest_vol = sum(t["volume"] for t in honest)
    avg_cap = honest_vol // 24  # ~10 per controller after collapse
    
    print(f"Honest market: {len(honest)} trades, 24 controllers, vol {honest_vol}, cap ~{avg_cap}")
    print(f"Base index: {base_idx.amount}\n")
    
    # Adversary: inject 20% total volume across N forged controls at extreme price
    total_adv_vol = honest_vol // 5
    
    for num_fakes in [1, 5, 10, 20, 50, 100]:
        vol_per_fake = total_adv_vol // num_fakes
        
        attacked = list(honest)
        for i in range(num_fakes):
            attacked.append({
                "skill": "s", "perk": "p",
                "price": "10.0000",  # 10x price
                "volume": vol_per_fake,
                "control": f"fake-{i}"  # Forged, unique control label
            })
        
        result = fmv_index(attacked)
        move = _move_pct(base_idx, result["index"])
        new_distinct = result["distinct_controllers"]
        
        print(f"{num_fakes:3d} forged controls: move = {move:7.4f}%, distinct now = {new_distinct}")
    
    print("\nVERDICT: More forged controls = more index movement. The algorithm trusts")
    print("the control label and caps each separately, allowing a sybil attacker to")
    print("effectively bypass the per-controller cap by splitting volume across fakes.")


def test_sybil_with_price_spread():
    """Sybil attack with a spread of extreme prices (not just one price)."""
    print("\n=== SYBIL ATTACK: Extreme Prices Across Multiple Fakes ===")
    
    rng = random.Random(42)
    honest = []
    for c in range(24):
        price = Decimal("1.0000") + Decimal(rng.randint(-50, 50)) * Decimal("0.0001")
        honest.append({"skill": "s", "perk": "p", "price": str(price), "volume": 10,
                       "control": f"ctrl-{c}"})
    
    base = fmv_index(honest)
    base_idx = base["index"]
    honest_vol = sum(t["volume"] for t in honest)
    
    # Adversary: 20% volume across 10 fakes, at prices [0.0001, 5, 10, 50, 100, ...]
    total_adv_vol = honest_vol // 5
    vol_per_fake = total_adv_vol // 10
    
    attacked = list(honest)
    prices = ["0.0001", "5.0000", "10.0000", "50.0000", "100.0000", 
              "0.0001", "5.0000", "10.0000", "50.0000", "100.0000"]
    for i in range(10):
        attacked.append({
            "skill": "s", "perk": "p",
            "price": prices[i],
            "volume": vol_per_fake,
            "control": f"fake-spread-{i}"
        })
    
    result = fmv_index(attacked)
    move = _move_pct(base_idx, result["index"])
    
    print(f"Base index: {base_idx.amount}")
    print(f"After sybil attack with 10 fakes at varied extreme prices:")
    print(f"  Index move: {move:.4f}%")
    print(f"  New distinct controllers: {result['distinct_controllers']}")


def test_sybil_inverse():
    """Sybil attack with very LOW prices (inverse of the above)."""
    print("\n=== SYBIL ATTACK: Extreme Low Prices (0.0001) Across Multiple Fakes ===")
    
    rng = random.Random(42)
    honest = []
    for c in range(24):
        price = Decimal("1.0000") + Decimal(rng.randint(-50, 50)) * Decimal("0.0001")
        honest.append({"skill": "s", "perk": "p", "price": str(price), "volume": 10,
                       "control": f"ctrl-{c}"})
    
    base = fmv_index(honest)
    base_idx = base["index"]
    honest_vol = sum(t["volume"] for t in honest)
    
    total_adv_vol = honest_vol // 5
    
    for num_fakes in [1, 10, 20, 50]:
        vol_per_fake = total_adv_vol // num_fakes
        
        attacked = list(honest)
        for i in range(num_fakes):
            attacked.append({
                "skill": "s", "perk": "p",
                "price": "0.0001",  # Extreme low price
                "volume": vol_per_fake,
                "control": f"fake-low-{i}"
            })
        
        result = fmv_index(attacked)
        move = _move_pct(base_idx, result["index"])
        
        print(f"{num_fakes:3d} forged controls @ 0.0001: move = {move:7.4f}%")


def test_sybil_with_higher_volume():
    """What if the adversary has MORE than 20% total volume, split as sybils?"""
    print("\n=== SYBIL ATTACK: Higher Adversary Volume (50% split across fakes) ===")
    
    rng = random.Random(42)
    honest = []
    for c in range(24):
        price = Decimal("1.0000") + Decimal(rng.randint(-50, 50)) * Decimal("0.0001")
        honest.append({"skill": "s", "perk": "p", "price": str(price), "volume": 10,
                       "control": f"ctrl-{c}"})
    
    base = fmv_index(honest)
    base_idx = base["index"]
    honest_vol = sum(t["volume"] for t in honest)
    
    # 50% adversary volume split across 20 fakes at 100x price
    total_adv_vol = honest_vol // 2
    vol_per_fake = total_adv_vol // 20
    
    attacked = list(honest)
    for i in range(20):
        attacked.append({
            "skill": "s", "perk": "p",
            "price": "100.0000",
            "volume": vol_per_fake,
            "control": f"sybil-heavy-{i}"
        })
    
    result = fmv_index(attacked)
    move = _move_pct(base_idx, result["index"])
    
    print(f"Base index: {base_idx.amount}")
    print(f"50% adversary volume, 20 forged controls @ 100x:")
    print(f"  Index move: {move:.4f}%")
    print(f"  New distinct controllers: {result['distinct_controllers']}")


if __name__ == "__main__":
    print("=" * 70)
    print("SYBIL ATTACK: EXPLOITING TRUSTED CONTROL LABELS")
    print("=" * 70)
    
    test_sybil_scaling()
    test_sybil_with_price_spread()
    test_sybil_inverse()
    test_sybil_with_higher_volume()

