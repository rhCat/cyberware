"""P6-T16 — single-writer-per-currency group commit + checkpoint resume (infra/settle/throughput.py).

Pins the throughput path's invariants: a batch commits atomically (all-or-nothing — an unbalanced member
rejects the whole batch with no partial append), checkpoint→resume verifies the exact balance set (and
rejects a tampered checkpoint), and value stays conserved."""
from __future__ import annotations

import pytest

from infra.settle import reward_ledger as RL
from infra.settle import throughput as TP
from infra.settle.money import Money


def _pair(a, b, amt="1.00", cur="USD"):
    return [RL._posting(a, -Money(amt, cur)), RL._posting(b, Money(amt, cur))]


def test_group_commit_appends_the_whole_batch_atomically():
    entries = RL.open_ledger("t", "t")
    w = TP.GroupCommitWriter(entries, "USD")
    for i in range(20):
        w.stage(_pair(f"a{i}", f"b{i}"))
    assert w.commit() == 20                                  # commit returns the running committed count
    assert sum(1 for e in entries if e.get("type") == "posting_set") == 20
    cp = w.checkpoint()
    assert cp["root"] == RL.balance_root(entries)            # the running checkpoint == the folded ledger root
    assert TP.resume_verify(cp) and RL.global_zero(entries)


def test_unbalanced_member_rejects_the_whole_batch_no_partial():
    entries = RL.open_ledger("t", "t")
    w = TP.GroupCommitWriter(entries, "USD")
    w.stage(_pair("a", "b"))
    w.stage([RL._posting("bad", Money("5.00", "USD"))])     # unbalanced
    before = len(entries)
    with pytest.raises(ValueError):
        w.commit()
    assert len(entries) == before                            # NOT a partial append — the good set didn't land either
    assert w.committed == 0
    assert w._staged == []                                   # rejected batch dropped — the writer is not wedged
    w.stage(_pair("a", "b"))                                 # and it accepts new work after the failure
    assert w.commit() == 1


def test_foreign_currency_set_is_rejected():
    entries = RL.open_ledger("t", "t")
    w = TP.GroupCommitWriter(entries, "USD")                 # single-writer-PER-CURRENCY
    w.stage([RL._posting("e1", -Money("1.00", "EUR")), RL._posting("e2", Money("1.00", "EUR"))])
    before = len(entries)
    with pytest.raises(ValueError):
        w.commit()
    assert len(entries) == before and w.committed == 0


def test_writer_seeded_from_an_existing_chain():
    entries = RL.open_ledger("t", "t")
    RL.post(entries, _pair("seed_a", "seed_b"))              # a posting set already on the chain
    w = TP.GroupCommitWriter(entries, "USD")                 # attaches to a NON-empty chain
    cp = w.checkpoint()
    assert cp["root"] == RL.balance_root(entries)            # checkpoint reflects the whole chain, not just deltas
    w.stage(_pair("c", "d"))
    w.commit()
    assert w.checkpoint()["root"] == RL.balance_root(entries)


def test_resume_rejects_a_nonconserving_checkpoint():
    bad = {"root": TP._balances_root([("a", "USD", "5")]), "balances": {"a|USD": "5"}}  # root-consistent but not zero-sum
    assert TP.resume_verify(bad) is False


def test_checkpoint_resume_verifies_and_detects_tamper():
    entries = RL.open_ledger("t", "t")
    w = TP.GroupCommitWriter(entries, "USD")
    w.stage(_pair("a", "b"))
    w.commit()
    cp = w.checkpoint()
    assert TP.resume_verify(cp) is True                                      # the committed balance set resumes
    assert TP.resume_verify({"root": "0" * 64, "balances": cp["balances"]}) is False   # tampered root rejected
    assert TP.resume_verify({**cp, "balances": {**cp["balances"], "evil|USD": "9"}}) is False   # altered balances
    assert TP.resume_verify("not a checkpoint") is False                     # malformed checkpoint


def test_empty_commit_is_a_noop():
    entries = RL.open_ledger("t", "t")
    w = TP.GroupCommitWriter(entries, "USD")
    assert w.commit() == 0 and w.committed == 0             # nothing staged -> no append
    assert TP.resume_verify(w.checkpoint()) is True         # an empty checkpoint still verifies


def test_selftest_ok():
    assert TP.throughput_selftest()["ok"] is True
