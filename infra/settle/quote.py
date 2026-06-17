#!/usr/bin/env python3
"""infra/settle/quote.py — the signed, funded quote (P6-T04, SV-6 / M6).

Before a priced perk runs, govd computes a **quote** from the perk's pricing block, the current FMV, and a
signed **split policy**, then signs it (Ed25519ph DSSE). The quote is bound to the **plan_sha** (so it cannot
be replayed against a different plan) and its **breakdown sums to the amount exactly** (via `money.split`).
A grant for a priced perk is honored only if it carries a `quote_sha` that is BOTH verified and **funded** —
the quote's amount is held in escrow in the reward ledger. An unfunded, tampered, unsigned, or plan-mismatched
quote does not authorize a priced run.
"""
from __future__ import annotations
import base64
import hashlib
import json

from infra.cwp import canonical, cosign
from infra.settle import reward_ledger
from infra.settle.money import Money, split

QUOTE_TYPE = "application/vnd.cyberware.quote+json"


def compute_quote(plan_sha: str, amount: Money, split_policy: dict, fmv: str) -> dict:
    """Build a value-bound quote: the amount split across the policy's accounts by exact weights, bound to
    the plan_sha + FMV. `split_policy` = {"accounts": [name...], "weights": [w...]} (non-float weights)."""
    accounts, weights = split_policy["accounts"], split_policy["weights"]
    parts = split(amount, weights)
    breakdown = [{"account": a, "amount": str(p.amount)} for a, p in zip(accounts, parts)]
    return {"plan_sha": plan_sha, "amount": str(amount.amount), "currency": amount.currency,
            "fmv": fmv, "split_policy": split_policy, "breakdown": breakdown}


def breakdown_balances(quote: dict) -> bool:
    """True iff the breakdown re-sums to the quoted amount EXACTLY (no money created or lost in the split)."""
    cur = quote["currency"]
    total = Money.zero(cur)
    for b in quote["breakdown"]:
        total = total + Money(b["amount"], cur)
    return total == Money(quote["amount"], cur)


def sign_quote(quote: dict, priv_pem_path: str) -> dict:
    """govd signs the quote (Ed25519ph DSSE) — the authorization token for a priced run."""
    return cosign.sign_ph(canonical.canonical_bytes(quote), priv_pem_path, payload_type=QUOTE_TYPE,
                          keyid="govd-quote")


def quote_sha(quote: dict) -> str:
    """The quote's content id — what a grant references and what escrow funds."""
    return hashlib.sha256(canonical.canonical_bytes(quote)).hexdigest()


def verify_quote(envelope: dict, pinned_pub_pem: str):
    """Returns (ok, quote). The envelope must be a quote type, signed, verify under govd's key, AND its
    breakdown must balance. A tampered/unsigned/wrong-type quote fails here."""
    if not isinstance(envelope, dict) or envelope.get("payloadType") != QUOTE_TYPE:
        return False, None
    if not envelope.get("signatures") or not cosign.verify_ph(envelope, pinned_pub_pem):
        return False, None
    try:
        q = json.loads(base64.b64decode(envelope["payload"]))
    except Exception:
        return False, None
    return (breakdown_balances(q), q)


def fund_quote(entries: list, funder: str, envelope: dict) -> dict:
    """Fund a quote: hold its amount in the quote's OWN escrow sub-account (`escrow_for(quote_sha)`), so the
    funding is bound to this specific quote — never a fungible pool another quote could ride on."""
    import base64 as _b64
    q = json.loads(_b64.b64decode(envelope["payload"]))
    sha = quote_sha(q)
    return reward_ledger.fund_escrow(entries, funder, Money(q["amount"], q["currency"]),
                                     escrow_acct=reward_ledger.escrow_for(sha), memo=f"fund-quote:{sha[:16]}")


def is_funded(entries: list, envelope: dict) -> bool:
    """True iff THIS quote's own escrow sub-account holds at least its amount — funding is per-quote, so an
    unrelated quote's escrow cannot make this one appear funded."""
    import base64 as _b64
    q = json.loads(_b64.b64decode(envelope["payload"]))
    cur = q["currency"]
    acct = reward_ledger.escrow_for(quote_sha(q))
    escrow = reward_ledger.balances(entries).get((acct, cur), Money.zero(cur))
    return not (escrow < Money(q["amount"], cur))


def grant_admits(envelope, entries, plan_sha: str, priced: bool, pinned_pub_pem: str) -> dict:
    """The grant gate for priced perks: a priced perk is admitted only with a verified quote whose plan_sha
    matches AND whose amount is funded in escrow. A free perk needs no quote. Returns {allow, reason}."""
    if not priced:
        return {"allow": True, "reason": "free_perk"}
    if not envelope:
        return {"allow": False, "reason": "quote_missing"}
    ok, q = verify_quote(envelope, pinned_pub_pem)
    if not ok:
        return {"allow": False, "reason": "quote_invalid"}
    if q["plan_sha"] != plan_sha:
        return {"allow": False, "reason": "plan_mismatch"}
    if not is_funded(entries, envelope):
        return {"allow": False, "reason": "quote_unfunded"}
    return {"allow": True, "reason": "funded_quote"}


def quote_selftest() -> dict:
    """P6-T04: a computed quote's breakdown balances to the amount; govd's signature verifies; a priced
    grant is REFUSED without a funded quote and ADMITTED with one; a tampered quote, an unfunded quote, and a
    plan-mismatched quote are each refused. Needs openssl (ed25519ph)."""
    import os
    import subprocess
    import tempfile
    d = tempfile.mkdtemp(prefix="quote-")
    priv, pub = os.path.join(d, "q.key"), os.path.join(d, "q.pub")
    subprocess.run(["openssl", "genpkey", "-algorithm", "ed25519", "-out", priv], check=True, capture_output=True)
    subprocess.run(["openssl", "pkey", "-in", priv, "-pubout", "-out", pub], check=True, capture_output=True)

    plan = "plan-" + "a" * 8
    policy = {"accounts": ["payee", "fee"], "weights": [90, 10]}
    q = compute_quote(plan, Money("100.0000"), policy, fmv="fmv-2026q2")
    env = sign_quote(q, priv)
    balances = breakdown_balances(q)
    verified = verify_quote(env, pub)[0]

    led = reward_ledger.open_ledger()
    refused_unfunded = grant_admits(env, led, plan, priced=True, pinned_pub_pem=pub)["allow"] is False
    fund_quote(led, "treasury", env)
    admitted_funded = grant_admits(env, led, plan, priced=True, pinned_pub_pem=pub)["allow"] is True
    free_ok = grant_admits(None, led, plan, priced=False, pinned_pub_pem=pub)["allow"] is True

    tampered = {**env, "signatures": []}
    tampered_refused = grant_admits(tampered, led, plan, priced=True, pinned_pub_pem=pub)["allow"] is False
    plan_mismatch = grant_admits(env, led, "plan-OTHER", priced=True, pinned_pub_pem=pub)
    plan_refused = plan_mismatch["allow"] is False and plan_mismatch["reason"] == "plan_mismatch"

    # cross-quote isolation: funding THIS quote must not make a DISTINCT quote of the same amount look funded
    q2 = compute_quote("plan-2", Money("100.0000"), policy, fmv="fmv-2026q2")
    env2 = sign_quote(q2, priv)
    cross = grant_admits(env2, led, "plan-2", priced=True, pinned_pub_pem=pub)
    cross_quote_isolated = cross["allow"] is False and cross["reason"] == "quote_unfunded"

    return {"breakdown_balances": balances, "quote_verifies": verified,
            "priced_refused_without_funded_quote": refused_unfunded,
            "priced_admitted_with_funded_quote": admitted_funded, "free_perk_needs_no_quote": free_ok,
            "tampered_quote_refused": tampered_refused, "plan_mismatch_refused": plan_refused,
            "cross_quote_isolated": cross_quote_isolated,
            "ok": (balances and verified and refused_unfunded and admitted_funded and free_ok
                   and tampered_refused and plan_refused and cross_quote_isolated)}
