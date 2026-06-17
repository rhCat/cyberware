#!/usr/bin/env python3
"""infra/settle/fmv.py — fair-market-value indices (P6-T11, SV-6 / M6).

The FMV index for a (skill, perk) is a **trimmed, control-capped, volume-weighted median** of settled trade
prices — a deliberately manipulation-resistant statistic:

  * **median, not mean** — a minority of extreme prices cannot drag it.
  * **common-control capping** — sybil parties under one controller (the P3 identity graph's `control` field)
    are collapsed to a single effective participant whose volume is capped at the average honest share, so an
    adversary cannot buy influence by splitting volume across fake identities or by sheer size.
  * **price-extreme trimming** — the top/bottom volume quantiles are dropped before the median.

Admission requires **n ≥ 20** trades from **≥ 8 distinct controllers**; below that the index is published
**provisional**. The manipulation bound the tests enforce: injecting **20% adversarial volume** at an extreme
price moves the index by **< 2%**.
"""
from __future__ import annotations
from decimal import Decimal

from infra.settle.money import Money

ADMISSION_N = 20
ADMISSION_DISTINCT = 8
TRIM_FRACTION = Decimal("0.10")        # trim the top & bottom 10% of volume by price before the median


def _vw_median(priced_volumes) -> Money:
    """Volume-weighted median of [(Money price, int volume)] — the price at the 50%-cumulative-volume point."""
    items = sorted(((p, v) for p, v in priced_volumes if v > 0), key=lambda pv: pv[0].amount)
    if not items:
        return Money.zero()
    total = sum(v for _, v in items)
    half = Decimal(total) / 2
    cum = 0
    for p, v in items:
        cum += v
        if Decimal(cum) >= half:
            return p
    return items[-1][0]


def _collapse_controls(trades) -> list:
    """Collapse each controller to ONE effective participant: its volume-weighted-median price, with volume
    capped at the average honest share (total / distinct_controllers). Sybils + whales cannot dominate."""
    by_ctrl = {}
    for t in trades:
        by_ctrl.setdefault(t["control"], []).append((Money(t["price"]), int(t["volume"])))
    distinct = len(by_ctrl)
    total_vol = sum(v for pvs in by_ctrl.values() for _, v in pvs)
    cap = max(1, total_vol // max(1, distinct))      # one controller's effective volume is capped at the mean share
    collapsed = []
    for _, pvs in by_ctrl.items():
        price = _vw_median(pvs)
        vol = min(sum(v for _, v in pvs), cap)
        collapsed.append((price, vol))
    return collapsed


def _trim(priced_volumes) -> list:
    """Drop the top & bottom TRIM_FRACTION of volume, ordered by price (robust to price extremes)."""
    items = sorted(((p, v) for p, v in priced_volumes if v > 0), key=lambda pv: pv[0].amount)
    total = sum(v for _, v in items)
    if total == 0:
        return items
    lo = (Decimal(total) * TRIM_FRACTION)
    hi = Decimal(total) * (1 - TRIM_FRACTION)
    out, cum = [], 0
    for p, v in items:
        seg_start = Decimal(cum)
        seg_end = Decimal(cum + v)
        keep_lo = max(seg_start, lo)
        keep_hi = min(seg_end, hi)
        kept = keep_hi - keep_lo
        if kept > 0:
            out.append((p, int(kept)))
        cum += v
    return out or items


GAP_FRACTION = Decimal("0.5")          # a splitting gap ≥ this fraction of the price range ⇒ multimodal


def _is_multimodal(collapsed) -> bool:
    """True iff the (control-collapsed) price distribution has a dominant GAP that splits volume into two
    substantial clusters — i.e. it is not a single good with one fair price. The volume-weighted median is a
    *positional* statistic and is unstable across such a gap (a 20% adversary at the gap can jump it), so a
    multimodal market must NOT publish a firm single index — it needs the class dimension to split first."""
    items = sorted(((p, v) for p, v in collapsed if v > 0), key=lambda pv: pv[0].amount)
    if len(items) < 2:
        return False
    prices = [p.amount for p, _ in items]
    prange = prices[-1] - prices[0]
    if prange == 0:
        return False
    total = sum(v for _, v in items)
    cum, max_split_gap = 0, Decimal(0)
    for i in range(len(items) - 1):
        cum += items[i][1]
        frac = Decimal(cum) / Decimal(total)
        if Decimal("0.25") <= frac <= Decimal("0.75"):        # this gap separates two substantial sides
            max_split_gap = max(max_split_gap, prices[i + 1] - prices[i])
    return (max_split_gap / prange) >= GAP_FRACTION


def fmv_index(trades) -> dict:
    """The FMV index over `trades` (each {skill, perk, price, volume, control}). A firm index is published
    only for an admitted, UNIMODAL market; a sub-admission OR multimodal market is `provisional` (and carries
    a `reason`). Returns {index, n, distinct_controllers, admitted, provisional, reason}."""
    distinct = len({t["control"] for t in trades})
    n = len(trades)
    collapsed = _collapse_controls(trades)
    index = _vw_median(_trim(collapsed))
    multimodal = _is_multimodal(collapsed)
    admitted = n >= ADMISSION_N and distinct >= ADMISSION_DISTINCT and not multimodal
    reason = ("multimodal_needs_class_split" if multimodal
              else ("ok" if admitted else "below_admission"))
    return {"index": index, "n": n, "distinct_controllers": distinct, "multimodal": multimodal,
            "admitted": admitted, "provisional": not admitted, "reason": reason}


def _move_pct(a: Money, b: Money) -> Decimal:
    if a.amount == 0:
        return Decimal(0)
    return (abs(b.amount - a.amount) / a.amount) * 100


def fmv_selftest() -> dict:
    """P6-T11 (scoped honestly after adversarial review): for an admitted **unimodal** market, injecting 20%
    adversarial volume moves the index **< 2%**; a **multimodal** market (two price clusters separated by a
    gap) is NOT published as a firm index — it is flagged **provisional** (`multimodal_needs_class_split`), so
    a positional-median attack at the gap has no firm index to move; a sub-admission market is provisional;
    and common-control sybils collapse to one controller. Deterministic (seeded, no float)."""
    import random
    rng = random.Random(11)
    # UNIMODAL honest market: 24 controllers, prices tightly clustered around 1.0000 (one good, one fair price)
    honest = []
    for c in range(24):
        price = Decimal("1.0000") + Decimal(rng.randint(-300, 300)) * Decimal("0.0001")   # ±0.03
        honest.append({"skill": "s", "perk": "p", "price": str(price), "volume": rng.randint(8, 12),
                       "control": f"ctrl-{c}"})
    base = fmv_index(honest)
    admitted = base["admitted"] and not base["multimodal"]

    # adversary floods 20% volume at a 3x price into the UNIMODAL market → median barely moves
    honest_vol = sum(t["volume"] for t in honest)
    adv_vol = max(1, honest_vol // 4)
    attacked = honest + [{"skill": "s", "perk": "p", "price": "3.0000", "volume": adv_vol, "control": "adv"}]
    move = _move_pct(base["index"], fmv_index(attacked)["index"])
    manipulation_bounded = move < Decimal("2")

    # BIMODAL market (the review's attack scenario): 12 controllers @1.0, 12 @5.0 — a gap-positioning attack
    # would jump a firm median, so the index MUST be refused as multimodal/provisional, not published firm.
    bimodal = ([{"skill": "s", "perk": "p", "price": "1.0000", "volume": 10, "control": f"lo-{i}"} for i in range(12)]
               + [{"skill": "s", "perk": "p", "price": "5.0000", "volume": 10, "control": f"hi-{i}"} for i in range(12)])
    bi = fmv_index(bimodal)
    multimodal_refused = bi["provisional"] is True and bi["reason"] == "multimodal_needs_class_split"
    # and the gap-positioning adversary cannot turn it into a firm manipulable index either
    bi_attacked = fmv_index(bimodal + [{"skill": "s", "perk": "p", "price": "3.0000", "volume": 30, "control": "adv"}])
    gap_attack_refused = bi_attacked["provisional"] is True

    # sub-admission market (only 5 controllers) → provisional
    provisional = fmv_index(honest[:5])["provisional"] is True

    # common-control: 50 sybils under ONE controller count as 1 distinct controller
    sybils = [{"skill": "s", "perk": "p", "price": "1.0000", "volume": 5, "control": "sybil"} for _ in range(50)]
    sybil_idx = fmv_index(honest + sybils)
    sybil_collapsed = sybil_idx["distinct_controllers"] == base["distinct_controllers"] + 1

    return {"unimodal_market_admitted": admitted, "index": str(base["index"].amount),
            "adversarial_move_pct": str(move), "manipulation_bounded_under_2pct": manipulation_bounded,
            "multimodal_refused_as_provisional": multimodal_refused, "gap_attack_refused": gap_attack_refused,
            "sub_admission_provisional": provisional, "common_control_collapsed": sybil_collapsed,
            "ok": (admitted and manipulation_bounded and multimodal_refused and gap_attack_refused
                   and provisional and sybil_collapsed)}
