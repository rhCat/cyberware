#!/usr/bin/env python3
"""infra/settle/selfbounty.py — P6-T20 self-bounty: cyberware's security program through its OWN ledger.

The economy's first outside users are paid to break it (adversarial dogfooding). Each vulnerability class is
a BOUNTY task; a disclosure is the work; a VALIDATED disclosure (a reproduced vulnerability — the validated
deliverable) wins the prize, which is paid to that external researcher THROUGH the reward ledger (the same
escrow/posting machinery every settlement uses). A class nobody validates refunds the sponsor. The program's
front door is the repo SECURITY.md doorbell (P3-T16, M12) — willingness has an address.

Built on infra.settle.markets.award_bounty (one validated winner, losers never debited, refund-if-none) over
the reward ledger. Exact Money, balanced double-entry, conserved.
"""
from __future__ import annotations

from infra.settle import markets
from infra.settle import reward_ledger as RL


def run_security_program(entries, sponsor, vuln_bounties):
    """Run cyberware's own security bounty program over the reward ledger. Each entry of `vuln_bounties` is a
    vuln class: {vuln_class, prize (Money), disclosures: [{name, validated: bool, score?}], select?}. Among
    the researchers whose disclosure VALIDATED, one is paid the prize through the ledger; a class with no
    validated disclosure refunds the sponsor. Returns a per-class award list."""
    awards = []
    for b in vuln_bounties:
        r = markets.award_bounty(entries, sponsor, b["prize"], b["disclosures"],
                                 bounty_id=b["vuln_class"], select=b.get("select", "best"))
        awards.append({"vuln_class": b["vuln_class"], **r})
    return awards


def selfbounty_selftest():
    """A validated disclosure pays the external researcher THROUGH the reward ledger (so the researcher's
    balance actually rises); among several validated disclosures exactly one is paid (losers untouched); a
    class nobody validates refunds the sponsor; the program's front door is the SECURITY.md doorbell
    (P3-T16); and the whole program conserves value (global zero-sum). `ok` iff all hold."""
    from infra.govern import doorbell
    from infra.settle.money import Money
    entries = RL.open_ledger("self-bounty", "self-bounty")
    program = [
        {"vuln_class": "snippet-toctou", "prize": Money("500.00", "USD"), "select": "best",
         "disclosures": [{"name": "ext:alice", "validated": True, "score": 9},
                         {"name": "ext:bob", "validated": True, "score": 5},      # validated but lower severity
                         {"name": "ext:carol", "validated": False}]},             # unreproduced -> not paid
        {"vuln_class": "grant-replay", "prize": Money("300.00", "USD"),
         "disclosures": [{"name": "ext:dave", "validated": False}]},              # nobody validated -> refund
    ]
    awards = run_security_program(entries, "cyberware:secops", program)

    best_validated_paid = awards[0]["winner"] == "ext:alice" and awards[0]["paid"] == "500.0000"
    exactly_one_paid = awards[0]["validated_count"] == 2 and awards[0]["winner"] == "ext:alice"
    no_winner_refunds = awards[1]["winner"] is None and awards[1]["paid"] == "0"

    bal = RL.balances(entries)
    alice = bal.get(("payee:ext:alice", "USD"))
    loser_untouched = ("payee:ext:bob", "USD") not in bal                          # a validated loser is NOT debited/credited
    researcher_paid = alice is not None and alice.amount > 0                        # payment flowed through the ledger
    sponsor_net = bal.get(("cyberware:secops", "USD"))
    refunded_class_neutral = sponsor_net is not None and sponsor_net.amount == Money("-500.00", "USD").amount

    front_door = doorbell.doorbell_selftest()["ok"]                                # the program's intake (M12)
    conserved = RL.global_zero(entries)

    ok = bool(best_validated_paid and exactly_one_paid and no_winner_refunds and loser_untouched
              and researcher_paid and refunded_class_neutral and front_door and conserved)
    return {"best_validated_paid": best_validated_paid, "exactly_one_paid": exactly_one_paid,
            "no_winner_refunds": no_winner_refunds, "loser_untouched": loser_untouched,
            "researcher_paid": researcher_paid, "refunded_class_neutral": refunded_class_neutral,
            "front_door_doorbell": front_door, "conserved": conserved, "ok": ok}


if __name__ == "__main__":
    import json
    import sys
    r = selfbounty_selftest()
    print(json.dumps(r, indent=2))
    sys.exit(0 if r["ok"] else 1)
