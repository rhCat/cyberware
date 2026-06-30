#!/usr/bin/env python3
"""infra/settle/price.py — price a governed run from its value-free PLAN, BEFORE it runs.

cyberware holds the plan — the priming CONTEXT (the SKILL.md + blueprint + perk metadata/manifesto/contract
the model reads to pick + configure a perk) and the structured OUTPUT shape (the claim/contract it emits), or
for a free-form run the wrapper + its `${VAR}` placeholders. So it can quote a run's cost DETERMINISTICALLY,
without generating a single token: you price the *shape*, not the content. That is what turns cyberware's
value-free boundary into a billing primitive — the quote IS the plan's price, so a Stripe charge for the
quoted total reconciles to the cent (you charge exactly what you priced; you never had to see a value).

Two priced surfaces, summed into one itemized USD quote:
  * LLM usage — context tokens + output tokens, at the model's per-1k rate (the NVIDIA/Nemotron substrate).
    Structured path: output ≈ the contract the model fills. Free-form path (the model writes the script
    itself): output ≈ the porter script + the vars. Tokens are an ESTIMATE (~chars/4); the tokenizer is
    swappable — the *structure* (priced before run, itemized, plan-bound) is the product, not chars/4.
  * Skill/tool fees — each tool's pay route (per-call / MCP / paid-API passthrough), set by the governance
    provider in pricing.json (a skill MAY also declare a `price` in its perk metadata.json).

No float ever touches a price (the infra/settle float-ban): token counts are ints, rates are Decimal strings,
every amount is Money (exact decimal, HALF_EVEN). pricing.json amounts are STRINGS for the same reason — a
JSON float would be refused at Money construction.
"""
from __future__ import annotations

import argparse
import json
import os
from decimal import Decimal

from infra import registry
from infra.settle.money import Money

HERE = os.path.dirname(os.path.abspath(__file__))
PRICING_PATH = os.path.join(HERE, "pricing.json")

_PER_1K = Decimal("0.001")                                     # tokens -> per-1k multiplier (Decimal, not a float)
_SKILL_CONTEXT = ("SKILL.md", "blueprint.json")               # what primes the model at the SKILL level
_PERK_CONTEXT = ("metadata.json", "manifesto.json", os.path.join("src", "contracts.json"))


def load_pricing(path: str = PRICING_PATH) -> dict:
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def est_tokens(text: str) -> int:
    """A deterministic, dependency-free token estimate (~chars/4). Swap a real tokenizer later; the pricing
    structure (priced-before-run, itemized, plan-bound) does not depend on the estimator's precision."""
    return max(0, len(text) // 4)


def _read(path: str) -> str:
    try:
        with open(path, encoding="utf-8") as f:
            return f.read()
    except OSError:
        return ""


def _perk_dir(skill: str, perk: str) -> str:
    return os.path.join(registry.skill_dir(skill), "perks", perk)


def context_tokens(skill: str, perk: str) -> int:
    """The value-free context the model reads to pick + configure this perk (skill docs + perk contract)."""
    sd = registry.skill_dir(skill)
    text = "".join(_read(os.path.join(sd, f)) for f in _SKILL_CONTEXT)
    pd = _perk_dir(skill, perk)
    text += "".join(_read(os.path.join(pd, f)) for f in _PERK_CONTEXT)
    return est_tokens(text)


def output_tokens(skill: str, perk: str, mode: str = "structured") -> int:
    """The tokens the model EMITS. structured: it fills the perk's contract (the value-free claim). free-form:
    it writes the porter script itself (so the script body + vars are the output)."""
    if mode == "freeform":
        srcdir = os.path.join(_perk_dir(skill, perk), "src")
        body = ""
        try:
            for fn in sorted(os.listdir(srcdir)):
                if fn.endswith((".sh", ".py")):
                    body += _read(os.path.join(srcdir, fn))
        except OSError:
            body = ""
        return est_tokens(body)
    return est_tokens(_read(os.path.join(_perk_dir(skill, perk), "src", "contracts.json")))


def llm_cost(in_tokens: int, out_tokens: int, rate: dict) -> Money:
    """in/out tokens at the model's per-1k rate. All Decimal/Money — no float (float-ban)."""
    c_in = Money(rate["in_per_1k"]).scale(Decimal(int(in_tokens))).scale(_PER_1K)
    c_out = Money(rate["out_per_1k"]).scale(Decimal(int(out_tokens))).scale(_PER_1K)
    return c_in + c_out


def tool_fee(skill: str, perk: str, pricing: dict) -> Money:
    """The tool's pay route: gov-provider fee (pricing.json, by 'skill/perk' then 'skill'), else the skill's
    own declared price (perk metadata.json `price.amount`), else the default. Each key is tried with the
    CANONICAL id first and then its BARE leaf, so a legacy pre-namespace `pricing.json` keyed `fs`/`fs/perk`
    still prices the canonical claim `general:fs` — the same back-compat leaf-fallback the per-actor ACL uses
    (else the cutover would silently fee-MISS a mixed-vintage fee table and under-charge)."""
    fees = pricing.get("tool_fees", {})
    leaf = skill.split(":", 1)[1] if ":" in skill else skill        # bare back-compat for a legacy fee table
    val = next((fees[k] for k in (f"{skill}/{perk}", f"{leaf}/{perk}", skill, leaf) if k in fees), None)
    if val is None:
        try:
            md = json.loads(_read(os.path.join(_perk_dir(skill, perk), "metadata.json")) or "{}")
            val = (md.get("price") or {}).get("amount")
        except (ValueError, AttributeError):
            val = None
    if val is None:
        val = fees.get("_default", "0")
    return Money(val, pricing.get("currency", "USD"))


def price_plan(skill: str, perk: str, model: str = None, mode: str = "structured", pricing: dict = None) -> dict:
    """The itemized USD quote for one perk-run, priced from the plan shape — no execution, no generation.
    `total` is what a Stripe charge bills; it reconciles to the cent because it IS the priced amount."""
    pricing = pricing or load_pricing()
    rates = pricing["model_rates"]
    model = model or pricing.get("default_model", "default")
    rate = rates.get(model) or rates["default"]
    cur = pricing.get("currency", "USD")

    ctx, out = context_tokens(skill, perk), output_tokens(skill, perk, mode)
    llm = llm_cost(ctx, out, rate)
    fee = tool_fee(skill, perk, pricing)
    subtotal = llm + fee
    mkt = subtotal.scale(Decimal(pricing.get("marketplace_fee_pct", "0")))
    total = subtotal + mkt
    return {
        "skill": skill, "perk": perk, "model": model, "mode": mode, "currency": cur,
        "llm": {"context_tokens": ctx, "output_tokens": out,
                "in_per_1k": rate["in_per_1k"], "out_per_1k": rate["out_per_1k"], "cost": str(llm.amount)},
        "tool_fee": str(fee.amount),
        "subtotal": str(subtotal.amount),
        "marketplace_fee": str(mkt.amount),
        "total": str(total.amount),
        "note": "estimate priced from the plan shape (tokens ~chars/4); charge `total` — it reconciles to the cent",
    }


def price_selftest() -> dict:
    """Value-free, no-network checks — total is exact, itemized, and the float-ban holds over this module."""
    pr = load_pricing()
    q = price_plan("fs", "find_large", pricing=pr)
    sub = Money(q["subtotal"]) == Money(q["llm"]["cost"]) + Money(q["tool_fee"])
    tot = Money(q["total"]) == Money(q["subtotal"]) + Money(q["marketplace_fee"])
    fee_pr = load_pricing()
    fee_pr["tool_fees"] = {"_default": "0", "fs/find_large": "0.5000"}
    qf = price_plan("fs", "find_large", pricing=fee_pr)
    from infra.settle.money import float_ban_scan
    no_float = float_ban_scan([__file__]) == []
    return {
        "itemized_subtotal_exact": sub,
        "total_exact": tot,
        "nonzero_llm_cost": Money(q["llm"]["cost"]) > Money("0"),
        "tool_fee_applied": q["tool_fee"] != qf["tool_fee"] and Money(qf["tool_fee"]) == Money("0.5000"),
        "freeform_differs": price_plan("fs", "find_large", mode="freeform")["llm"]["output_tokens"]
                            != q["llm"]["output_tokens"],
        "float_ban_clean": no_float,
    }


def main():
    ap = argparse.ArgumentParser(description="price a governed perk-run from its plan, before it runs (value-free)")
    ap.add_argument("--skill")
    ap.add_argument("--perk")
    ap.add_argument("--model", default=None)
    ap.add_argument("--freeform", action="store_true", help="price the model-writes-the-script path")
    ap.add_argument("--selftest", action="store_true")
    a = ap.parse_args()
    if a.selftest:
        print(json.dumps(price_selftest(), indent=2))
        return
    if not a.skill or not a.perk:
        ap.error("--skill and --perk are required (or use --selftest)")
    print(json.dumps(price_plan(a.skill, a.perk, model=a.model,
                                mode="freeform" if a.freeform else "structured"), indent=2))


if __name__ == "__main__":
    main()
