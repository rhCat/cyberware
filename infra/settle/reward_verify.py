#!/usr/bin/env python3
"""infra/settle/reward_verify.py — money↔work cross-check (P6-T06, SV-6 / M6).

The reward ledger conserves value INTERNALLY (P6-T02: chain integrity + per-record + global zero-sum).
P6-T06 adds the cross-PLANE invariant: the MONEY trail (settlement posting sets, each tagged
`settle:quote:<sha>`) and the WORK trail (the dual-signed, validation==pass, quote-bound receipts that
authorize a payout) cannot drift SILENTLY. `reward_verify` proves a bijection between them — a settlement
with no authorizing receipt (money moved without proven work) OR an authorized receipt with no settlement
(proven, quote-bound work never paid) is flagged, so the money trail and the work trail can never diverge
unnoticed.
"""
from __future__ import annotations

from infra.cwp import ledger, receipts
from infra.settle import engine
from infra.settle import quote as quote_mod
from infra.settle import reward_ledger


def settled_quote_shas(entries) -> list:
    """The MONEY trail: the quote_sha of every settlement posting set (one payout per quote)."""
    pre = engine._SETTLE_PREFIX
    return [str(e.get("memo"))[len(pre):] for e in entries
            if e.get("type") == "posting_set" and str(e.get("memo", "")).startswith(pre)]


def authorized_quote_shas(receipt_store, quote_envs, exec_pub, approver_pub, govd_pub) -> list:
    """The WORK trail: the quote_sha of every receipt that AUTHORIZES a payout — dual-signed AND
    validation==pass AND quote-bound (its quote envelope verifies under govd's key and the sha matches).
    `quote_envs` maps quote_sha -> the signed quote envelope."""
    out = []
    for r in receipt_store:
        if not receipts.verify_receipt(r, exec_pub, approver_pub).get("dual_signed"):
            continue
        pred = engine._predicate(r)
        if pred.get("validation") != "pass":
            continue
        sha = pred.get("quote_sha")
        qenv = (quote_envs or {}).get(sha)
        if not qenv:
            continue
        qok, q = quote_mod.verify_quote(qenv, govd_pub)
        if qok and quote_mod.quote_sha(q) == sha:
            out.append(sha)
    return out


def reward_verify(entries, receipt_store, quote_envs, exec_pub, approver_pub, govd_pub) -> dict:
    """Cross-check the money trail against the work trail. `ok` iff the ledger conserves value (chain
    integrity + per-record + global zero-sum) AND money↔work is a clean bijection: no orphan settlement
    (money_without_work), no orphan authorized receipt (work_without_money), no double-settled quote."""
    chain_ok = bool(ledger.verify_chain(entries, ledger.CURRENT_MAJOR))
    per_record_zero = all(reward_ledger.is_balanced(e["postings"])
                          for e in entries if e.get("type") == "posting_set")
    global_zero = reward_ledger.global_zero(entries)
    money = settled_quote_shas(entries)
    work = authorized_quote_shas(receipt_store, quote_envs, exec_pub, approver_pub, govd_pub)
    money_set, work_set = set(money), set(work)
    money_without_work = sorted(money_set - work_set)            # money moved with no authorizing receipt
    work_without_money = sorted(work_set - money_set)            # authorized, quote-bound work never paid
    double_settled = sorted({s for s in money_set if money.count(s) > 1})
    ok = (chain_ok and per_record_zero and global_zero
          and not money_without_work and not work_without_money and not double_settled)
    return {"chain_ok": chain_ok, "per_record_zero": per_record_zero, "global_zero": global_zero,
            "settlements": len(money), "authorized_receipts": len(work),
            "money_without_work": money_without_work, "work_without_money": work_without_money,
            "double_settled": double_settled, "ok": ok}


def reward_verify_selftest(n: int = 3) -> dict:
    """P6-T06: build N funded+settled quotes with their dual-signed receipts, prove reward_verify sees a
    clean money↔work bijection, then DISCRIMINATE both directions — dropping a receipt surfaces
    `money_without_work`, and an authorized-but-unsettled receipt surfaces `work_without_money`. Needs
    openssl (ed25519ph)."""
    import os
    import subprocess
    import tempfile

    from infra.settle.money import Money
    d = tempfile.mkdtemp(prefix="rverify-")

    def kp(tag):
        p, pub = os.path.join(d, f"{tag}.key"), os.path.join(d, f"{tag}.pub")
        subprocess.run(["openssl", "genpkey", "-algorithm", "ed25519", "-out", p], check=True, capture_output=True)
        subprocess.run(["openssl", "pkey", "-in", p, "-pubout", "-out", pub], check=True, capture_output=True)
        return p, pub

    ex_priv, ex_pub = kp("exec")
    ap_priv, ap_pub = kp("appr")
    gv_priv, gv_pub = kp("govd")
    policy = {"accounts": ["payee", "fee"], "weights": [90, 10]}

    led = reward_ledger.open_ledger()
    store, envs = [], {}
    for i in range(n):
        q = quote_mod.compute_quote(f"plan-{i}", Money("100.0000"), policy, fmv="fmv")
        qenv = quote_mod.sign_quote(q, gv_priv)
        sha = quote_mod.quote_sha(q)
        envs[sha] = qenv
        quote_mod.fund_quote(led, "treasury", qenv)
        rcpt = engine.build_receipt(f"run-{i}", sha, "pass", Money("100.0000"), ex_priv, ap_priv)
        engine.settle(led, rcpt, qenv, ex_pub, ap_pub, gv_pub)
        store.append(rcpt)
    clean = reward_verify(led, store, envs, ex_pub, ap_pub, gv_pub)

    # discriminate A: a settlement whose authorizing receipt is missing from the work trail
    drift_a = reward_verify(led, store[1:], envs, ex_pub, ap_pub, gv_pub)
    money_without_work_caught = (not drift_a["ok"]) and len(drift_a["money_without_work"]) == 1

    # discriminate B: an authorized, quote-bound receipt that was never settled
    q2 = quote_mod.compute_quote("plan-unpaid", Money("100.0000"), policy, fmv="fmv")
    q2env = quote_mod.sign_quote(q2, gv_priv)
    sha2 = quote_mod.quote_sha(q2)
    unpaid = engine.build_receipt("run-unpaid", sha2, "pass", Money("100.0000"), ex_priv, ap_priv)
    drift_b = reward_verify(led, store + [unpaid], {**envs, sha2: q2env}, ex_pub, ap_pub, gv_pub)
    work_without_money_caught = (not drift_b["ok"]) and drift_b["work_without_money"] == [sha2]

    return {"clean_bijection": clean["ok"], "settlements": clean["settlements"],
            "money_without_work_caught": money_without_work_caught,
            "work_without_money_caught": work_without_money_caught,
            "ok": clean["ok"] and money_without_work_caught and work_without_money_caught}


if __name__ == "__main__":
    import json
    import sys
    r = reward_verify_selftest()
    print(json.dumps(r, indent=2))
    sys.exit(0 if r.get("ok") else 1)
