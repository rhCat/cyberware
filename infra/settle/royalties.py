#!/usr/bin/env python3
"""infra/settle/royalties.py — repatriating the ancestor as priced perks (P6-T19, SV-6 / M11).

alchemy's verbs (extract / conserve / classify / concord) are the ancestor every verified-tier publish is
graded against (the Citrinitas gate). P6-T19 closes the loop: a **verified-tier publish pays a royalty to the
alchemy lineage** through the reward ledger. The publish only happens if alchemy's gate ADMITS the subject
(verified tier); on admission the publish revenue is split — a royalty share to the `alchemy:lineage` account,
the rest to the publisher — as a balanced posting set, and a **lineage receipt** records the payment. A
subject alchemy BLOCKS (a conservation defect, an unnamed shape, a CFG mismatch) is not published and pays no
royalty.
"""
from __future__ import annotations

from infra.settle import reward_ledger
from infra.settle.money import Money, split

ALCHEMY_LINEAGE = "alchemy:lineage"


def publish_with_royalty(entries: list, publisher: str, subject_source: str, revenue: Money,
                         royalty_weight=15, keep_weight=85) -> dict:
    """Attempt a verified-tier publish of `subject_source`: alchemy must ADMIT it; on admission the revenue is
    split (royalty share → alchemy lineage, the rest → publisher) as a balanced posting set, and a lineage
    receipt is returned. If alchemy blocks, nothing is published and no royalty is paid."""
    from infra.cwp import alchemy
    gate = alchemy.publish_gate(subject_source)
    if not gate["admit"]:
        return {"published": False, "reason": gate["reason"], "lineage_paid": "0"}
    royalty, kept = split(revenue, [royalty_weight, keep_weight])
    # the publisher funds the publish revenue; it is split to the alchemy lineage + the publisher's own balance
    reward_ledger.post(entries, [reward_ledger._posting("publish-revenue", -revenue),
                                 reward_ledger._posting(ALCHEMY_LINEAGE, royalty),
                                 reward_ledger._posting(publisher, kept)],
                       memo=f"lineage-royalty:{publisher}")
    return {"published": True, "tier": "verified", "reason": "citrinitas_clean",
            "lineage_paid": str(royalty.amount), "publisher_kept": str(kept.amount)}


def lineage_total(entries: list, currency: str = "USD") -> Money:
    """How much the alchemy lineage has earned so far."""
    return reward_ledger.balances(entries).get((ALCHEMY_LINEAGE, currency), Money.zero(currency))


def royalty_selftest() -> dict:
    """P6-T19: a verified-tier publish pays a real royalty to the alchemy lineage through the reward ledger
    (lineage credited > 0, posting balanced, ledger zero-sum); a subject alchemy BLOCKS pays no royalty.
    Needs the pinned alchemy/putrefactio engine."""
    from infra.cwp import alchemy
    led = reward_ledger.open_ledger()
    # a clean, verified-tier subject (open/close — balanced, all named) → publishes + pays lineage
    clean = "def manage(path):\n    fh = open(path)\n    fh.close()\n"
    r = publish_with_royalty(led, "pub-1", clean, Money("100.0000"))
    paid = lineage_total(led)
    verified_pays = (r["published"] and Money(r["lineage_paid"]) == paid and paid > Money.zero()
                     and reward_ledger.global_zero(led))

    # a subject with a conservation defect (leak) is BLOCKED → no publish, no royalty
    led2 = reward_ledger.open_ledger()
    leak = "def manage(path):\n    fh = open(path)\n    return fh\n"
    r2 = publish_with_royalty(led2, "pub-2", leak, Money("100.0000"))
    blocked_no_pay = (r2["published"] is False and lineage_total(led2).is_zero()
                      and r2["reason"] == "conservation_defect")

    return {"verified_publish_pays_lineage": verified_pays, "lineage_paid": str(paid.amount),
            "blocked_subject_pays_nothing": blocked_no_pay,
            "engine_available": alchemy.tools_present(),
            "ok": verified_pays and blocked_no_pay}
