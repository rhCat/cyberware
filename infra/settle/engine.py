#!/usr/bin/env python3
"""infra/settle/engine.py — the settlement engine (P6-T05, SV-6 / M6 — the rung that closes the ladder).

Settlement is a pure function of a **dual-signed receipt** (P3-T14), the **funded quote** (P6-T04), and the
signed split policy. It pays out only when ALL of the following hold, and refuses (writing nothing) otherwise:

  * the receipt is **dual-signed** (both the executor's and the approver's Ed25519-DSSE signatures verify),
  * the receipt's predicate carries **validation == "pass"** (a flipped verdict is rejected),
  * the receipt is **bound to the quote** (its `quote_sha` matches a quote that verifies under govd's key),
  * the quote is **funded** in escrow.

On success it writes **one atomic, balanced posting set**: escrow is drained to zero, the fee and payee are
credited per the quote breakdown, and a **dispute-window holdback** is parked in a hold account (released
after the window). A mutant receipt — signature stripped, or verdict flipped to "fail" — settles **nothing**:
payment is impossible without both signatures AND a passing validation.
"""
from __future__ import annotations
import base64
import json

from infra.cwp import receipts
from infra.settle import quote as quote_mod
from infra.settle import reward_ledger
from infra.settle.money import Money, split

RECEIPT_PREDICATE = receipts.RECEIPT_PREDICATE
_SETTLE_PREFIX = "settle:quote:"                               # settlement records are tagged by quote_sha


def _already_settled(entries: list, quote_sha: str) -> bool:
    """True iff this quote_sha has already paid out — the spent-quote guard that makes settlement idempotent
    (a re-funded quote cannot double-pay). Keyed on quote_sha, never the attacker-chosen run_id."""
    tag = f"{_SETTLE_PREFIX}{quote_sha}"
    return any(e.get("type") == "posting_set" and e.get("memo") == tag for e in entries)


def build_receipt(run_id: str, quote_sha: str, validation: str, amount: Money, priv_exec: str,
                  priv_appr: str) -> dict:
    """A finalized dual-signed receipt (executor + approver) over an in-toto statement whose predicate binds
    the quote_sha + the validation verdict. `validation` is "pass" for a real run."""
    predicate = {"run_id": run_id, "quote_sha": quote_sha, "validation": validation,
                 "amount": str(amount.amount), "currency": amount.currency}
    return receipts.finalize_receipt(run_id, quote_sha, predicate, priv_exec, "executor", priv_appr, "approver")


def _predicate(receipt: dict):
    try:
        return json.loads(base64.b64decode(receipt["payload"])).get("predicate", {})
    except Exception:
        return {}


def settle(entries: list, receipt: dict, quote_env: dict, exec_pub: str, approver_pub: str, govd_pub: str,
           hold_weight=10, keep_weight=90) -> dict:
    """Consume a receipt → at most one atomic posting set. Returns {settled, reason, holdback?}. Settles iff
    dual-signed AND validation==pass AND quote-bound (verified) AND funded; else refuses, writing nothing."""
    rep = receipts.verify_receipt(receipt, exec_pub, approver_pub)
    if not rep["dual_signed"]:
        return {"settled": False, "reason": "not_dual_signed"}
    pred = _predicate(receipt)
    if pred.get("validation") != "pass":
        return {"settled": False, "reason": "validation_not_pass"}
    qok, q = quote_mod.verify_quote(quote_env, govd_pub)
    if not qok:
        return {"settled": False, "reason": "quote_invalid"}
    sha = quote_mod.quote_sha(q)
    if pred.get("quote_sha") != sha:
        return {"settled": False, "reason": "quote_unbound"}
    if _already_settled(entries, sha):                          # idempotency: a quote pays out at most ONCE
        return {"settled": False, "reason": "quote_already_settled"}
    if not quote_mod.is_funded(entries, quote_env):
        return {"settled": False, "reason": "quote_unfunded"}

    cur = q["currency"]
    amount = Money(q["amount"], cur)
    by_acct = {b["account"]: Money(b["amount"], cur) for b in q["breakdown"]}
    fee_part = by_acct.get("fee", Money.zero(cur))
    payee_part = by_acct.get("payee", Money.zero(cur))
    held, kept = split(payee_part, [hold_weight, keep_weight])  # dispute-window holdback, exact split
    run = pred.get("run_id", "run")
    # drain THIS quote's escrow sub-account; tag the settlement with quote_sha (not the attacker-chosen run_id)
    postings = [reward_ledger._posting(reward_ledger.escrow_for(sha), -amount),
                reward_ledger._posting("fee", fee_part),
                reward_ledger._posting("payee", kept),
                reward_ledger._posting(f"hold:{sha[:16]}", held)]
    reward_ledger.post(entries, postings, memo=f"{_SETTLE_PREFIX}{sha}")
    return {"settled": True, "reason": "ok", "amount": str(amount.amount), "holdback": str(held.amount),
            "run_id": run, "quote_sha": sha}


def release_holdback(entries: list, quote_sha: str, currency: str = "USD") -> dict:
    """After the dispute window, release the held amount to the payee (a balanced posting set). Keyed on the
    quote_sha (the hold account `hold:{quote_sha[:16]}` settlement parked the holdback in)."""
    acct = f"hold:{quote_sha[:16]}"
    held = reward_ledger.balances(entries).get((acct, currency), Money.zero(currency))
    reward_ledger.post(entries, [reward_ledger._posting(acct, -held),
                                 reward_ledger._posting("payee", held)], memo=f"release-hold:{quote_sha[:16]}")
    return {"released": str(held.amount)}


def engine_selftest() -> dict:
    """P6-T05: a valid dual-signed, validation:pass, quote-bound receipt settles atomically — escrow drains
    to zero, the posting set is balanced, and the global ledger stays zero-sum; a signature-stripped receipt
    and a verdict-flipped receipt each settle NOTHING; an unbound receipt is refused; and the holdback
    releases to the payee after the window. Needs openssl (ed25519ph)."""
    import os
    import subprocess
    import tempfile
    d = tempfile.mkdtemp(prefix="engine-")

    def kp(tag):
        p, pub = os.path.join(d, f"{tag}.key"), os.path.join(d, f"{tag}.pub")
        subprocess.run(["openssl", "genpkey", "-algorithm", "ed25519", "-out", p], check=True, capture_output=True)
        subprocess.run(["openssl", "pkey", "-in", p, "-pubout", "-out", pub], check=True, capture_output=True)
        return p, pub

    ex_priv, ex_pub = kp("exec")
    ap_priv, ap_pub = kp("appr")
    gv_priv, gv_pub = kp("govd")

    plan = "plan-" + "z" * 8
    policy = {"accounts": ["payee", "fee"], "weights": [90, 10]}
    q = quote_mod.compute_quote(plan, Money("100.0000"), policy, fmv="fmv")
    qenv = quote_mod.sign_quote(q, gv_priv)
    qsha = quote_mod.quote_sha(q)

    led = reward_ledger.open_ledger()
    quote_mod.fund_quote(led, "treasury", qenv)

    good = build_receipt("run-1", qsha, "pass", Money("100.0000"), ex_priv, ap_priv)
    res = settle(led, good, qenv, ex_pub, ap_pub, gv_pub)
    settled = res["settled"]
    # this quote's OWN escrow sub-account must drain to zero (not the generic pool)
    escrow_zero = reward_ledger.balances(led).get(
        (reward_ledger.escrow_for(qsha), "USD"), Money.zero()).is_zero()
    global_zero = reward_ledger.global_zero(led)

    # mutant A: strip a signature → not dual-signed → settles nothing
    stripped = {**good, "signatures": good["signatures"][:1]}
    led_a = reward_ledger.open_ledger(); quote_mod.fund_quote(led_a, "t", qenv)
    mut_a = settle(led_a, stripped, qenv, ex_pub, ap_pub, gv_pub)
    sig_rejected = mut_a["settled"] is False and not any(e.get("memo", "").startswith("settle:") for e in led_a)

    # mutant B: flip the verdict to fail → rejected
    flipped = build_receipt("run-1", qsha, "fail", Money("100.0000"), ex_priv, ap_priv)
    led_b = reward_ledger.open_ledger(); quote_mod.fund_quote(led_b, "t", qenv)
    mut_b = settle(led_b, flipped, qenv, ex_pub, ap_pub, gv_pub)
    verdict_rejected = mut_b["settled"] is False and mut_b["reason"] == "validation_not_pass"

    # mutant C: receipt bound to a different quote_sha → unbound
    unbound = build_receipt("run-1", "0" * 64, "pass", Money("100.0000"), ex_priv, ap_priv)
    led_c = reward_ledger.open_ledger(); quote_mod.fund_quote(led_c, "t", qenv)
    unbound_rejected = settle(led_c, unbound, qenv, ex_pub, ap_pub, gv_pub)["reason"] == "quote_unbound"

    # BLOCKER-2 regression — same-quote replay double-pay: re-fund the SAME quote and settle again. The
    # spent-quote guard must refuse, and no second settlement record may be written.
    quote_mod.fund_quote(led, "treasury", qenv)                 # top escrow back up (the replay vector)
    n_settle_before = sum(1 for e in led if str(e.get("memo", "")).startswith(_SETTLE_PREFIX))
    replay = settle(led, good, qenv, ex_pub, ap_pub, gv_pub)
    n_settle_after = sum(1 for e in led if str(e.get("memo", "")).startswith(_SETTLE_PREFIX))
    double_settle_refused = (replay["settled"] is False and replay["reason"] == "quote_already_settled"
                             and n_settle_after == n_settle_before == 1)

    # BLOCKER-1 regression — cross-quote escrow: a DISTINCT quote is not funded by another quote's escrow.
    q2 = quote_mod.compute_quote("plan-other", Money("50.0000"), policy, fmv="fmv")
    q2env = quote_mod.sign_quote(q2, gv_priv)
    led2 = reward_ledger.open_ledger()
    quote_mod.fund_quote(led2, "t", qenv)                       # fund quote 1 ($100) only
    r2 = build_receipt("run-2", quote_mod.quote_sha(q2), "pass", Money("50.0000"), ex_priv, ap_priv)
    cross_quote_isolated = settle(led2, r2, q2env, ex_pub, ap_pub, gv_pub)["reason"] == "quote_unfunded"

    # holdback releases to payee after the window (balanced) — keyed on quote_sha
    rel = release_holdback(led, qsha)
    hold_released = Money(rel["released"]) == Money(res["holdback"]) and reward_ledger.global_zero(led)

    return {"valid_receipt_settles": settled, "escrow_zeroed": escrow_zero, "global_zero_sum": global_zero,
            "sig_stripped_rejected": sig_rejected, "verdict_flipped_rejected": verdict_rejected,
            "unbound_rejected": unbound_rejected, "double_settle_refused": double_settle_refused,
            "cross_quote_isolated": cross_quote_isolated, "holdback_released_to_payee": hold_released,
            "ok": (settled and escrow_zero and global_zero and sig_rejected and verdict_rejected
                   and unbound_rejected and double_settle_refused and cross_quote_isolated and hold_released)}
