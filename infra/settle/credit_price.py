#!/usr/bin/env python3
"""infra/settle/credit_price.py — the negotiable CREDIT price of one perk-run.

Credits are the internal allowance unit the per-actor budget meters (`budget.py`). This resolves a run's
CREDIT price the same shape `price.tool_fee` resolves the USD pay route, but on the credit axis:
  1. the OPERATOR's negotiable override — a `credit_prices` block in pricing.json, keyed `skill/perk` ->
     `skill` -> `namespace` -> `_default` (canonical id first, then bare leaf, so a legacy un-namespaced
     table still prices a namespaced claim);
  2. the SKILL's OWN declaration — the perk's metadata.json `credit_price` (the skill author sets the price
     per skill/perk, the same way the USD `price` is declared in the skill) — "pricing allowed in the skill";
  3. the `_default`.
Exact-decimal `Money(CREDITS)` throughout (no float). The USD `price_plan` (settle/marketplace economics) is
a separate axis and is untouched.
"""
from __future__ import annotations
import json
import os

from infra.settle.money import Money
from infra.settle.price import _perk_dir, _read, load_pricing

CREDITS = "CREDITS"


def _skill_declared(skill: str, perk: str):
    """The skill author's own declared credit price — the perk's metadata.json `credit_price` (a string
    amount, or `{"amount": ...}`). None if absent."""
    try:
        md = json.loads(_read(os.path.join(_perk_dir(skill, perk), "metadata.json")) or "{}")
    except (ValueError, AttributeError):
        return None
    cp = md.get("credit_price")
    if isinstance(cp, dict):
        cp = cp.get("amount")
    return cp if isinstance(cp, str) else None


def credit_price(skill: str, perk: str, pricing: dict = None) -> Money:
    """The CREDIT price for one (skill, perk) run: operator override -> skill declaration -> `_default`."""
    pricing = pricing if pricing is not None else load_pricing()
    table = pricing.get("credit_prices", {})
    leaf = skill.split(":", 1)[1] if ":" in skill else skill          # bare back-compat for a legacy table
    ns = skill.split(":", 1)[0] if ":" in skill else None
    keys = [f"{skill}/{perk}", f"{leaf}/{perk}", skill, leaf]
    if ns:
        keys.append(ns)                                              # a per-namespace operator default
    val = next((table[k] for k in keys if k in table), None)
    if val is None:
        val = _skill_declared(skill, perk)                          # the skill's own declared price
    if val is None:
        val = table.get("_default", "1.0000")
    return Money(val, CREDITS)
