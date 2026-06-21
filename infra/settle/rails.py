#!/usr/bin/env python3
"""infra/settle/rails.py — collect the platform tax at SETTLE, via a pluggable RAIL.

The tax is NOT an agent action and NOT a hidden portal:

  * not an agent action — making the agent call a "stripe skill" to pay is itself a tax (an extra LLM
    round-trip the agent can fumble or skip). Instead the tax is collected AUTOMATICALLY when a priced run
    settles. The agent does one thing — its work; the engine, which already priced the run's shape, collects.
  * not a hidden portal — the tax IS the transparent itemized price the pricer computed: substrate (the
    LLM/NVIDIA usage), skill-author (the skill's pay route), and the marketplace fee (the platform's cut).
    A rail charges EXACTLY the quoted total and records the named split, so the operator sees where every
    cent goes — there is no separate account that skims.

Rails:
  * LedgerRail (default) — post the split to the reward-ledger by double entry (the free / self-hosted tier):
    the operator is debited the total; substrate / skill_author / marketplace are credited their lines.
  * StripeRail — the seam: charge the OPERATOR's account for the quoted total, Idempotency-Key = the run's
    plan_sha, with the line items as metadata. Inert until the operator wires a key (`config.key_file`,
    server-side); the agent never sees it and never makes the call.

Idempotent: a tax is collected at most once per idem_key (the plan_sha). No float touches a rail — every
amount is exact-decimal Money, and the line amounts come straight from the pricer.
"""
from __future__ import annotations

from infra.settle import reward_ledger
from infra.settle.money import Money, float_ban_scan

_TAX_PREFIX = "tax:"


def charge_from_price(price_quote: dict, plan_sha: str) -> dict:
    """Turn the pricer's itemized quote into a TRANSPARENT charge: the total + the named split the operator
    sees. The breakdown re-sums to the total exactly (the pricer guarantees subtotal = llm + tool, total =
    subtotal + marketplace)."""
    cur = price_quote.get("currency", "USD")
    breakdown = [
        {"account": "substrate", "amount": price_quote["llm"]["cost"]},        # LLM / NVIDIA-Nemotron usage
        {"account": "skill_author", "amount": price_quote["tool_fee"]},        # the skill's declared pay route
        {"account": "marketplace", "amount": price_quote["marketplace_fee"]},  # the platform tax — a VISIBLE line
    ]
    return {"plan_sha": plan_sha, "currency": cur, "total": price_quote["total"], "breakdown": breakdown}


def split_balances(charge: dict) -> bool:
    """The split re-sums to the total exactly — no skim, no money created or lost."""
    cur = charge["currency"]
    total = Money.zero(cur)
    for b in charge["breakdown"]:
        total = total + Money(b["amount"], cur)
    return total == Money(charge["total"], cur)


def _already_collected(entries: list, idem_key: str) -> bool:
    tag = _TAX_PREFIX + idem_key
    return any(e.get("type") == "posting_set" and e.get("memo") == tag for e in entries)


class LedgerRail:
    """Collect the tax by double-entry into the reward-ledger: operator debited the total, the split credited
    to its named accounts. Transparent + deterministic; the free / self-hosted tier."""
    name = "ledger"

    def __init__(self, entries: list):
        self.entries = entries

    def collect(self, charge: dict, idem_key: str) -> dict:
        if _already_collected(self.entries, idem_key):
            return {"rail": "ledger", "status": "duplicate", "idem": idem_key}
        cur = charge["currency"]
        postings = [reward_ledger._posting("operator", -Money(charge["total"], cur))]
        for b in charge["breakdown"]:
            postings.append(reward_ledger._posting(b["account"], Money(b["amount"], cur)))
        reward_ledger.post(self.entries, postings, memo=_TAX_PREFIX + idem_key)
        return {"rail": "ledger", "status": "collected", "total": charge["total"], "currency": cur,
                "breakdown": charge["breakdown"], "idem": idem_key}


class StripeRail:
    """Charge the OPERATOR's account for the quoted total (Idempotency-Key = the run's plan_sha), with the
    line items as metadata. Inert until `config.key_file` is set — the operator wires the key, server-side;
    the agent never sees it. The actual charge call is the one seam the operator completes."""
    name = "stripe"

    def __init__(self, config: dict = None):
        self.config = config or {}

    def collect(self, charge: dict, idem_key: str) -> dict:
        if not self.config.get("key_file"):
            return {"rail": "stripe", "status": "unconfigured", "would_charge": charge["total"],
                    "currency": charge["currency"], "breakdown": charge["breakdown"], "idem": idem_key,
                    "note": "set rails.stripe.key_file (operator's key, server-side) to enable; the agent never sees it"}
        # SEAM (operator wires this): POST https://api.stripe.com/v1/payment_intents
        #   amount = charge["total"] (minor units), currency, Idempotency-Key = idem_key,
        #   metadata = the breakdown (the transparent line items), key = cat(self.config["key_file"]).
        raise NotImplementedError("wire the Stripe charge here using config['key_file'] (cat at runtime)")


def make_rail(name: str = "ledger", entries: list = None, config: dict = None):
    if name == "stripe":
        return StripeRail(config)
    if name == "ledger":
        return LedgerRail(entries if entries is not None else reward_ledger.open_ledger())
    raise ValueError(f"unknown rail: {name}")


def collect_tax(charge: dict, rail, idem_key: str) -> dict:
    """Collect a transparent tax charge via the rail, idempotently. Refuses a charge whose split does not
    re-sum to the total (a skim) — the platform tax is the marketplace LINE in `charge`, never a hidden cut."""
    if not split_balances(charge):
        raise ValueError("charge breakdown does not re-sum to the total (a skim) — refused")
    return rail.collect(charge, idem_key)


def rails_selftest() -> dict:
    """Value-free, no-network: the split is transparent + balanced, collection is idempotent and zero-sum,
    a skim is refused, and Stripe is inert until configured."""
    from infra.settle import price
    pq = price.price_plan("http", "get")                       # has a tool fee -> all three lines non-trivial
    charge = charge_from_price(pq, "PLANSHA")
    cur = charge["currency"]
    led = reward_ledger.open_ledger()
    rail = LedgerRail(led)
    r1 = collect_tax(charge, rail, "PLANSHA")
    r2 = collect_tax(charge, rail, "PLANSHA")                  # same plan_sha -> collected at most once
    bal = reward_ledger.balances(led)
    bad = dict(charge, total=str((Money(charge["total"], cur) + Money("1", cur)).amount))  # tampered: more than the split
    skim_refused = False
    try:
        collect_tax(bad, LedgerRail(reward_ledger.open_ledger()), "Y")
    except ValueError:
        skim_refused = True
    return {
        "split_balances": split_balances(charge),
        "marketplace_is_a_visible_line": any(b["account"] == "marketplace" for b in charge["breakdown"]),
        "collected": r1["status"] == "collected",
        "idempotent": r2["status"] == "duplicate",
        "operator_debited_total": bal.get(("operator", cur), Money.zero(cur)) == -Money(charge["total"], cur),
        "zero_sum": reward_ledger.global_zero(led),
        "stripe_inert_until_keyed": StripeRail().collect(charge, "Z")["status"] == "unconfigured",
        "skim_refused": skim_refused,
        "float_ban_clean": float_ban_scan([__file__]) == [],
    }
