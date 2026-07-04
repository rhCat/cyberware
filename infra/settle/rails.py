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

from decimal import Decimal

from infra.settle import reward_ledger
from infra.settle.money import Money, float_ban_scan

_TAX_PREFIX = "tax:"
_HUNDRED = Decimal("100")               # USD -> minor units (cents); Decimal, never a float (float-ban)


def usd_to_minor(amount, currency: str = "USD") -> int:
    """Exact-decimal amount -> integer minor units (cents) for the Stripe API. Truncates sub-cent — which is
    exactly why per-call micro-taxes can't be a one-shot charge (Stripe's ~$0.50 minimum); use meter mode for
    usage. Pure Decimal/int — no float touches it."""
    return int(Money(amount, currency).scale(_HUNDRED).amount)


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
    transparent line items as metadata. Inert until `config.key_file` is set — the operator wires the key,
    server-side (the agent never sees it). charge-mode = one-shot PaymentIntent (for amounts >= the Stripe
    minimum; for per-call usage micro-taxes, meter mode is the right primitive — a later config switch)."""
    name = "stripe"
    API = "https://api.stripe.com/v1/payment_intents"

    def __init__(self, config: dict = None):
        self.config = config or {}

    def collect(self, charge: dict, idem_key: str) -> dict:
        key_file = self.config.get("key_file")
        if not key_file:
            return {"rail": "stripe", "status": "unconfigured", "would_charge": charge["total"],
                    "currency": charge["currency"], "breakdown": charge["breakdown"], "idem": idem_key,
                    "note": "set rails.stripe.key_file (operator's key, server-side) to enable; the agent never sees it"}
        return self._charge(charge, idem_key, key_file)

    def _charge(self, charge: dict, idem_key: str, key_file: str) -> dict:
        # charge-mode: a one-shot PaymentIntent for the quoted total, idempotent on plan_sha. The operator's
        # key is read at call time (cat) and never logged; the breakdown rides as metadata (transparent).
        import json as _json
        import os
        import urllib.error
        import urllib.parse
        import urllib.request
        cur = charge["currency"]
        cents = usd_to_minor(charge["total"], cur)
        if cents <= 0:                                             # sub-cent: a one-shot charge is impossible
            return {"rail": "stripe", "status": "below_minimum", "would_charge": charge["total"],
                    "currency": cur, "idem": idem_key, "note": "sub-cent total — use meter mode for usage taxes"}
        key = open(os.path.expanduser(key_file), encoding="utf-8").read().strip()
        fields = {"amount": cents, "currency": cur.lower(), "confirm": "true",
                  "payment_method": self.config.get("payment_method", "pm_card_visa"),
                  "payment_method_types[]": "card",          # card-only -> no redirect, no return_url needed
                  "description": f"cyberware tax {idem_key[:16]}"}
        for b in charge["breakdown"]:                              # transparent line items as Stripe metadata
            fields[f"metadata[{b['account']}]"] = b["amount"]
        req = urllib.request.Request(
            self.API, data=urllib.parse.urlencode(fields).encode(), method="POST",
            headers={"Authorization": "Bearer " + key, "Idempotency-Key": idem_key,
                     "Content-Type": "application/x-www-form-urlencoded"})
        try:
            with urllib.request.urlopen(req, timeout=20) as r:
                pi = _json.loads(r.read())
            return {"rail": "stripe", "status": "charged", "charge_id": pi.get("id"),
                    "pi_status": pi.get("status"), "amount": charge["total"], "currency": cur,
                    "breakdown": charge["breakdown"], "idem": idem_key}
        except urllib.error.HTTPError as e:                        # surface Stripe's error, never the key
            return {"rail": "stripe", "status": "error", "http": e.code,
                    "detail": e.read().decode()[:300], "idem": idem_key}


class CreditRail:
    """Collect the usage tax by DEBITING a prepaid credit balance (no per-call Stripe fee) — refused if the
    balance can't cover it (the tax is a structural gate). Top up the balance with credits.topup (one Stripe
    charge, fee amortized). This is the production per-call model; charge-mode is only for big one-off paids."""
    name = "credit"

    def __init__(self, entries: list, operator: str = "operator"):
        self.entries = entries
        self.operator = operator

    def collect(self, charge: dict, idem_key: str) -> dict:
        from infra.settle import credits
        return credits.debit_usage(self.entries, self.operator, charge, idem_key)


def make_rail(name: str = "ledger", entries: list = None, config: dict = None):
    config = config or {}
    if name == "stripe":
        return StripeRail(config)
    if name in ("credit", "ledger"):
        # a money-recording rail posts a double-entry into `entries` (mutated in place by reward_ledger.post),
        # so it MUST be handed the persistent reward chain to record into. Refusing None fails closed: silently
        # substituting a throwaway in-memory ledger would discard every posting AND break the documented
        # plan_sha idempotency (each fresh call can never see a prior collection). A caller that truly wants an
        # ephemeral ledger passes one explicitly (reward_ledger.open_ledger()).
        if entries is None:
            raise ValueError(f"the {name!r} rail records money into a ledger — pass `entries` (the reward "
                             "chain to post into); refusing a throwaway whose postings would be discarded")
        return CreditRail(entries, config.get("operator", "operator")) if name == "credit" else LedgerRail(entries)
    raise ValueError(f"unknown rail: {name}")


def collect_tax(charge: dict, rail, idem_key: str) -> dict:
    """Collect a transparent tax charge via the rail, idempotently. Refuses a charge whose split does not
    re-sum to the total (a skim) — the platform tax is the marketplace LINE in `charge`, never a hidden cut."""
    if not split_balances(charge):
        raise ValueError("charge breakdown does not re-sum to the total (a skim) — refused")
    return rail.collect(charge, idem_key)


def collect_run_tax(skill: str, perk: str, plan_sha: str, rail=None, pricing: dict = None,
                    model: str = None, mode: str = "structured", ledger_entries: list = None) -> dict:
    """The settle-time tax collection for ONE run: price the plan → the transparent charge → collect via the
    rail. This is what the engine/operator calls when a priced run SETTLES (never the agent — no extra LLM
    call). Idempotent on plan_sha. Returns {price, charge, receipt}. With no rail, builds the one named by
    pricing.json `rails.default`."""
    from infra.settle import price
    pricing = pricing or price.load_pricing()
    pq = price.price_plan(skill, perk, model=model, mode=mode, pricing=pricing)
    charge = charge_from_price(pq, plan_sha)
    if rail is None:
        rails_cfg = pricing.get("rails") or {}
        rail = make_rail(rails_cfg.get("default", "ledger"), entries=ledger_entries,
                         config=rails_cfg.get("stripe", {}))
    return {"price": pq, "charge": charge, "receipt": collect_tax(charge, rail, plan_sha)}


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
        "usd_to_minor_dollar": usd_to_minor("1.0000") == 100,          # $1.00 -> 100 cents
        "usd_to_minor_subcent_zero": usd_to_minor("0.0072") == 0,      # micro-tax -> below Stripe minimum
        "collect_run_tax_settles": collect_run_tax(
            "http", "get", "PSHA2", rail=LedgerRail(reward_ledger.open_ledger()))["receipt"]["status"] == "collected",
        "float_ban_clean": float_ban_scan([__file__]) == [],
    }
