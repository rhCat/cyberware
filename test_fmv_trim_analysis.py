#!/usr/bin/env python3
"""Detailed analysis of the trim function to find edge cases."""

import sys
sys.path.insert(0, '/Users/user/hunyuan/cyberware')

from decimal import Decimal
from infra.settle.fmv import _trim, _vw_median, _collapse_controls, TRIM_FRACTION
from infra.settle.money import Money


def analyze_trim_detailed():
    """Deep dive into the trim function behavior."""
    print("\n=== DETAILED TRIM ANALYSIS ===\n")
    
    # Simple case: 8 items, 10 each, 80 total
    # Trim 10% = 8 units each side, should leave 64
    items = [(Money(str(i)), 10) for i in range(1, 9)]
    
    print("Input (8 items, 10 units each):")
    for p, v in items:
        print(f"  Price {p.amount}: vol {v}")
    
    total = sum(v for _, v in items)
    print(f"Total volume: {total}")
    
    # Manual trace through trim logic
    lo = Decimal(total) * TRIM_FRACTION  # 8.0
    hi = Decimal(total) * (1 - TRIM_FRACTION)  # 72.0
    print(f"\nTrim boundaries: lo={lo}, hi={hi}")
    print(f"TRIM_FRACTION = {TRIM_FRACTION}")
    
    trimmed = _trim(items)
    print(f"\nAfter trim:")
    for p, v in trimmed:
        print(f"  Price {p.amount}: vol {v}")
    
    trimmed_total = sum(v for _, v in trimmed)
    print(f"Trimmed total volume: {trimmed_total}")
    print(f"Volume removed: {total - trimmed_total} (expected 20)")
    
    if total - trimmed_total != 20:
        print(f"\n⚠️  MISMATCH: Expected to remove 20, but removed {total - trimmed_total}")
        print("Analyzing the discrepancy...")
        
        # Manually walk through the algorithm
        print("\nManual algorithm trace:")
        cum = 0
        for p, v in items:
            seg_start = Decimal(cum)
            seg_end = Decimal(cum + v)
            keep_lo = max(seg_start, lo)
            keep_hi = min(seg_end, hi)
            kept = keep_hi - keep_lo
            print(f"  Price {p.amount}: seg [{seg_start}, {seg_end}), keep [{keep_lo}, {keep_hi}) = {kept} units")
            cum += v


def analyze_trim_with_odd_volumes():
    """Trim with non-uniform volumes (edge case)."""
    print("\n=== TRIM WITH ODD VOLUMES ===\n")
    
    items = [(Money(str(i)), v) for i, v in enumerate([5, 10, 15, 20, 25, 30], start=1)]
    
    print("Input (non-uniform volumes):")
    for p, v in items:
        print(f"  Price {p.amount}: vol {v}")
    
    total = sum(v for _, v in items)
    lo = Decimal(total) * TRIM_FRACTION
    hi = Decimal(total) * (1 - TRIM_FRACTION)
    
    print(f"Total: {total}, Trim boundaries: lo={lo}, hi={hi}")
    
    trimmed = _trim(items)
    trimmed_total = sum(v for _, v in trimmed)
    print(f"Trimmed total: {trimmed_total}")
    print(f"Removed: {total - trimmed_total}")


def analyze_trim_single_item():
    """What happens if there's only one item?"""
    print("\n=== TRIM WITH SINGLE ITEM ===\n")
    
    items = [(Money("5.0000"), 100)]
    
    print("Input: 1 item, price 5.0000, volume 100")
    
    total = 100
    lo = Decimal(total) * TRIM_FRACTION  # 10
    hi = Decimal(total) * (1 - TRIM_FRACTION)  # 90
    
    print(f"Trim boundaries: lo={lo}, hi={hi}")
    
    trimmed = _trim(items)
    if trimmed:
        print(f"Trimmed: price {trimmed[0][0].amount}, volume {trimmed[0][1]}")
    else:
        print("Trimmed: empty (returns original)")


def test_adversary_at_trim_boundary():
    """Try to place adversary volume at the trim boundary to minimize removal."""
    print("\n=== ADVERSARY AT TRIM BOUNDARY ===\n")
    
    # Create a distribution where adversary volume lands exactly at trim boundary
    # to maximize survival through trimming
    
    items = []
    # Honest traders: prices 1-10, 10 units each = 100 total
    for i in range(1, 11):
        items.append((Money(str(i)), 10))
    
    base_total = 100
    lo = Decimal(base_total) * TRIM_FRACTION  # 10
    hi = Decimal(base_total) * (1 - TRIM_FRACTION)  # 90
    
    print(f"Honest market: 10 items @ 10 units each = {base_total} total")
    print(f"Trim lo={lo}, hi={hi}")
    
    trimmed = _trim(items)
    trimmed_vol = sum(v for _, v in trimmed)
    print(f"Trimmed: {trimmed_vol} units")
    
    # Now add adversary at very high price
    # The trim will drop the bottom 10, so if adversary is at the TOP (high price),
    # it will be trimmed away
    adv_items = list(items) + [(Money("1000.0000"), 20)]
    
    print(f"\nAdversary adds 20 units @ 1000.0000")
    trimmed_adv = _trim(adv_items)
    trimmed_adv_vol = sum(v for _, v in trimmed_adv)
    print(f"Trimmed with adversary: {trimmed_adv_vol} units")
    print(f"Adversary volume trimmed away: {20 - (trimmed_adv_vol - trimmed_vol)}")


def test_median_calculation_edge_case():
    """The _vw_median could be vulnerable if trim leaves a partial volume."""
    print("\n=== MEDIAN CALCULATION EDGE CASE ===\n")
    
    # A case where the median falls within a single price point's volume
    items = [
        (Money("1.0000"), 30),
        (Money("2.0000"), 5),
        (Money("3.0000"), 30),
    ]
    
    total = 65
    median_point = total / 2  # 32.5
    
    print(f"Items: 30@1.0000, 5@2.0000, 30@3.0000 (total 65)")
    print(f"Median point: {median_point}")
    print(f"Expected median: 1.0000 (first 30 + partial 2.5 of 5)")
    
    median = _vw_median(items)
    print(f"Actual median: {median.amount}")
    
    # The algorithm returns the price at the 50% cumulative point
    # For cumulative [30, 35, 65], the 50% point (32.5) falls in the 2.0000 band
    # So it should return 2.0000, not 1.0000


if __name__ == "__main__":
    print("=" * 70)
    print("TRIM FUNCTION ANALYSIS")
    print("=" * 70)
    
    analyze_trim_detailed()
    analyze_trim_with_odd_volumes()
    analyze_trim_single_item()
    test_adversary_at_trim_boundary()
    test_median_calculation_edge_case()

