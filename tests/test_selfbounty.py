"""P6-T20 — self-bounty: cyberware's security program through its own ledger (infra/settle/selfbounty.py).

Pins the program: a VALIDATED disclosure pays the external researcher through the reward ledger (balanced,
conserved); exactly one of several validated disclosures is paid (losers untouched); a class nobody
validates refunds the sponsor; the whole program conserves value."""
from __future__ import annotations

from infra.settle import reward_ledger as RL
from infra.settle import selfbounty as SB
from infra.settle.money import Money


def test_validated_disclosure_pays_researcher_through_the_ledger():
    entries = RL.open_ledger("sb", "sb")
    awards = SB.run_security_program(entries, "secops", [
        {"vuln_class": "toctou", "prize": Money("500.00", "USD"), "select": "best",
         "disclosures": [{"name": "ext:a", "validated": True, "score": 9},
                         {"name": "ext:b", "validated": True, "score": 5},
                         {"name": "ext:c", "validated": False}]}])
    assert awards[0]["winner"] == "ext:a" and awards[0]["paid"] == "500.0000"
    assert awards[0]["validated_count"] == 2                       # two reproduced, but...
    bal = RL.balances(entries)
    assert bal[("payee:ext:a", "USD")].amount == Money("500.00", "USD").amount   # ...exactly one paid
    assert ("payee:ext:b", "USD") not in bal                       # the validated loser is never touched
    assert RL.global_zero(entries)                                 # the program conserves value


def test_unclaimed_class_refunds_the_sponsor():
    entries = RL.open_ledger("sb", "sb")
    awards = SB.run_security_program(entries, "secops", [
        {"vuln_class": "replay", "prize": Money("300.00", "USD"),
         "disclosures": [{"name": "ext:d", "validated": False}]}])   # nobody reproduced it
    assert awards[0]["winner"] is None and awards[0]["paid"] == "0"
    assert RL.balances(entries).get(("secops", "USD"), Money.zero("USD")).amount == 0   # sponsor net zero (refunded)
    assert RL.global_zero(entries)


def test_first_select_pays_the_first_validated():
    entries = RL.open_ledger("sb", "sb")
    awards = SB.run_security_program(entries, "secops", [
        {"vuln_class": "x", "prize": Money("100.00", "USD"), "select": "first",
         "disclosures": [{"name": "ext:late", "validated": True, "score": 1},
                         {"name": "ext:first", "validated": True, "score": 99}]}])
    assert awards[0]["winner"] == "ext:late"                        # 'first' = first validated, not highest score


def test_selftest_ok():
    assert SB.selfbounty_selftest()["ok"] is True
