#!/usr/bin/env python3
"""infra/settle/disputes.py — the dispute lifecycle (P6-T12, SV-6 / M6 / M9).

A settled run can be disputed within a window. The lifecycle, all ledgered on the reward ledger:

  * **bond** — the disputer posts a bond into a dispute-bond account (skin in the game).
  * **m-of-n resolution** — `m` of `n` arbiters approve a **resolution document** by REUSING the P3 WebAuthn
    approval artifact (challenge = `sha256(JCS(doc))`), so the resolution carries the same hardware-backed,
    doc-bound, offline-verifiable approvals as any destructive grant. Fewer than `m` distinct valid approvals
    → unresolved.
  * **clawback + reputation** — if the dispute is **upheld**, the settlement's holdback is clawed back to the
    disputer and the bond is returned, and the payee's reputation takes a negative delta; if **rejected**,
    the bond is forfeited to the payee and the disputer's reputation takes the delta.

Every money movement is a balanced posting set; reputation deltas are recorded too.
"""
from __future__ import annotations

from infra.cwp import webauthn
from infra.settle import reward_ledger
from infra.settle.money import Money

ORIGIN, RP_ID = "https://arbitrate.cyberware", "cyberware"
BOND_ACCT = "dispute-bond"


def open_dispute(entries: list, disputer: str, quote_sha: str, bond: Money) -> dict:
    """Open a dispute: the disputer posts a bond into the dispute-bond account (balanced)."""
    return reward_ledger.post(entries, [reward_ledger._posting(disputer, -bond),
                                        reward_ledger._posting(f"{BOND_ACCT}:{quote_sha[:16]}", bond)],
                              memo=f"dispute-open:{quote_sha[:16]}")


def count_approvals(resolution_doc: dict, approvals: list) -> int:
    """The number of DISTINCT arbiters whose WebAuthn approval over the resolution doc verifies offline."""
    seen = set()
    for arb_id, assertion in approvals:
        if arb_id in seen:
            continue
        if webauthn.verify_assertion(resolution_doc, assertion, ORIGIN, RP_ID)[0]:
            seen.add(arb_id)
    return len(seen)


def resolve(entries: list, resolution_doc: dict, approvals: list, m: int, payee: str, disputer: str,
            quote_sha: str, reputation: dict) -> dict:
    """Resolve a dispute if ≥ m distinct arbiters approved the resolution doc. `resolution_doc.outcome` is
    "upheld" or "rejected". Moves the bond + holdback accordingly (balanced) and applies a reputation delta.
    Returns {resolved, outcome?, reason}."""
    if m < 2:                                                 # quorum must be a real m-of-n, never a single arbiter
        return {"resolved": False, "reason": "quorum_too_small"}
    approvals_n = count_approvals(resolution_doc, approvals)
    if approvals_n < m:
        return {"resolved": False, "reason": "insufficient_approvals", "approvals": approvals_n}

    cur = resolution_doc.get("currency", "USD")
    bond_acct = f"{BOND_ACCT}:{quote_sha[:16]}"
    hold_acct = f"hold:{quote_sha[:16]}"
    bal = reward_ledger.balances(entries)
    bond = bal.get((bond_acct, cur), Money.zero(cur))
    held = bal.get((hold_acct, cur), Money.zero(cur))
    outcome = resolution_doc["outcome"]

    if outcome == "upheld":                                   # disputer was right: claw back holdback + return bond
        postings = [reward_ledger._posting(hold_acct, -held), reward_ledger._posting(disputer, held),
                    reward_ledger._posting(bond_acct, -bond), reward_ledger._posting(disputer, bond)]
        reputation[payee] = reputation.get(payee, 0) - 1
    else:                                                     # rejected: bond forfeited to the payee
        postings = [reward_ledger._posting(bond_acct, -bond), reward_ledger._posting(payee, bond)]
        reputation[disputer] = reputation.get(disputer, 0) - 1
    reward_ledger.post(entries, postings, memo=f"dispute-resolve:{outcome}:{quote_sha[:16]}")
    return {"resolved": True, "outcome": outcome, "reason": "ok", "approvals": approvals_n}


def dispute_selftest() -> dict:
    """P6-T12 end-to-end: a bond is posted; an m-of-n (2-of-3) WebAuthn resolution upholds the dispute →
    holdback clawed back to the disputer + bond returned + payee reputation delta, all ledgered and the
    ledger stays zero-sum; a resolution with only m-1 distinct approvals does NOT resolve; the rejected path
    forfeits the bond to the payee. Needs nothing external (Ed25519 via cryptography)."""
    from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

    qsha = "q" * 32
    # seed a settled state: a holdback parked for this quote, funded by a treasury (balanced setup)
    led = reward_ledger.open_ledger()
    reward_ledger.post(led, [reward_ledger._posting("treasury", -Money("10.0000")),
                             reward_ledger._posting(f"hold:{qsha[:16]}", Money("10.0000"))], memo="seed-hold")
    open_dispute(led, "disputer", qsha, Money("5.0000"))

    arbiters = {f"arb{i}": Ed25519PrivateKey.generate() for i in range(3)}
    doc = {"quote_sha": qsha, "outcome": "upheld", "currency": "USD", "reason": "non-delivery"}
    approvals = [(aid, webauthn.make_assertion(doc, key, ORIGIN, RP_ID)) for aid, key in arbiters.items()]

    # m-1 approvals (only 1) must NOT resolve
    rep = {}
    too_few = resolve(reward_ledger.open_ledger(), doc, approvals[:1], 2, "payee", "disputer", qsha, rep)
    insufficient_blocked = too_few["resolved"] is False and too_few["reason"] == "insufficient_approvals"

    # 2-of-3 upheld → clawback + bond return + reputation delta, all ledgered & zero-sum
    res = resolve(led, doc, approvals[:2], 2, "payee", "disputer", qsha, rep)
    disputer_bal = reward_ledger.balances(led).get(("disputer", "USD"), Money.zero())
    upheld_ok = (res["resolved"] and res["outcome"] == "upheld"
                 and reward_ledger.global_zero(led) and rep.get("payee") == -1
                 # disputer got holdback (10) + bond back (5) - bond posted (5) = +10 net
                 and disputer_bal == Money("10.0000"))

    # a tampered approval (over a DIFFERENT doc) does not count toward m
    other_doc = {**doc, "outcome": "rejected"}
    mismatched = [(aid, webauthn.make_assertion(other_doc, key, ORIGIN, RP_ID)) for aid, key in arbiters.items()]
    tamper_ignored = count_approvals(doc, mismatched) == 0

    # rejected path forfeits the bond to the payee
    led2 = reward_ledger.open_ledger()
    open_dispute(led2, "disputer", qsha, Money("5.0000"))
    rej_doc = {"quote_sha": qsha, "outcome": "rejected", "currency": "USD"}
    rej_appr = [(aid, webauthn.make_assertion(rej_doc, key, ORIGIN, RP_ID)) for aid, key in arbiters.items()]
    rep2 = {}
    rej = resolve(led2, rej_doc, rej_appr[:2], 2, "payee", "disputer", qsha, rep2)
    rejected_ok = (rej["outcome"] == "rejected"
                   and reward_ledger.balances(led2).get(("payee", "USD"), Money.zero()) == Money("5.0000")
                   and rep2.get("disputer") == -1 and reward_ledger.global_zero(led2))

    return {"bond_posted_and_upheld_clawback": upheld_ok, "insufficient_approvals_blocked": insufficient_blocked,
            "tampered_approval_ignored": tamper_ignored, "rejected_forfeits_bond": rejected_ok,
            "ok": upheld_ok and insufficient_blocked and tamper_ignored and rejected_ok}
