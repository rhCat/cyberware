"""Ledger-v2 durability (P1-T02 / SV-2): concurrent appends serialize into one valid chain; a crash-
truncated tail is recovered (mid-chain corruption is not); snapshots are atomic. Fast + deterministic —
the full 16x5000 + kill-9 acceptance scale lives in infra/cwp/torture.py (the cws-ledgercheck/torture perk).
"""
import json

import pytest

from infra.cwp import ledger as L
from infra.cwp.torture import TortureConfig, run_concurrent_torture


def test_concurrent_appends_serialize_into_one_valid_chain(tmp_path):
    """The acceptance, at unit scale: N concurrent writers, zero lost, every line parses, ONE valid
    prev-hash chain, contiguous seq — proving durable_append serializes under the lock."""
    report, _ = run_concurrent_torture(tmp_path / "ledger.jsonl", TortureConfig(workers=6, appends_per=50))
    assert report["lost"] == 0, report
    assert report["all_parse"] and report["verify_chain_ok"] and report["seqs_contiguous"], report
    assert report["entry_count"] == report["total_expected"]


def test_durable_append_self_links_and_persists(tmp_path):
    p = tmp_path / "c.jsonl"
    L.write_chain(p, [L.genesis("run-Z", "plan-Z")])
    for i in range(5):
        L.durable_append(p, {"task_id": f"t{i}", "verdict": "pass"})
    entries, schema = L.read_chain(p)
    assert len(entries) == 6 and L.verify_chain(entries, schema)[0] is True
    assert [e["seq"] for e in entries] == [0, 1, 2, 3, 4, 5]


def test_torn_tail_recovered_but_strict_by_default(tmp_path):
    p = tmp_path / "c.jsonl"
    chain = [L.genesis("r", "p")]
    L.append(chain, {"task_id": "t1"})
    L.append(chain, {"task_id": "t2"})
    L.write_chain(p, chain)
    with open(p, "a") as f:
        f.write('{"task_id":"t3","verdict":"pa')              # crash-truncated final line (partial JSON)
    entries, schema, trunc = L.read_chain(p, allow_torn_tail=True)
    assert len(entries) == 3 and entries[-1]["task_id"] == "t2"
    assert trunc and trunc["was_torn"] and trunc["last_valid_seq"] == 2
    assert L.verify_chain(entries, schema)[0] is True          # the recovered prefix verifies
    with pytest.raises(json.JSONDecodeError):                  # default is strict — only opt-in recovers
        L.read_chain(p)


def test_durable_append_heals_a_torn_tail(tmp_path):
    """A pre-existing crash-truncated tail is dropped before the next append: the committed record is kept,
    the fragment never becomes mid-chain corruption, the chain stays readable + valid (audit blockers #2-#4)."""
    p = tmp_path / "c.jsonl"
    chain = [L.genesis("r", "p")]
    L.append(chain, {"task_id": "t1"})
    L.write_chain(p, chain)
    with open(p, "a") as f:
        f.write('{"task_id":"torn","verdict":"pa')           # crash fragment (no trailing newline)
    rec = L.durable_append(p, {"task_id": "good", "verdict": "pass"})
    entries, schema = L.read_chain(p)                          # readable (not bricked) under the strict reader
    ids = [e.get("task_id") for e in entries]
    assert "good" in ids and "torn" not in ids                # committed record kept; torn fragment healed away
    assert rec["seq"] == 2 and L.verify_chain(entries, schema)[0] is True   # one valid chain, no seq fork


def test_nonfinal_corruption_is_an_error_not_a_torn_tail(tmp_path):
    p = tmp_path / "c.jsonl"
    L.write_chain(p, [L.genesis("r", "p")])
    with open(p, "a") as f:
        f.write("GARBAGE NOT JSON\n")                          # corruption in the MIDDLE
        f.write(json.dumps({"task_id": "t1", "seq": 1, "prev": "x"}) + "\n")
    with pytest.raises(json.JSONDecodeError):
        L.read_chain(p, allow_torn_tail=True)                  # mid-chain corruption is never dropped


def test_write_chain_is_atomic_and_leaves_no_tmp(tmp_path):
    p = tmp_path / "c.jsonl"
    chain = [L.genesis("r", "p")]
    L.append(chain, {"task_id": "t1"})
    L.write_chain(p, chain)
    assert not list(tmp_path.glob("*.tmp.*")), "atomic write left a tmp sibling"
    entries, schema = L.read_chain(p)
    assert len(entries) == 2 and L.verify_chain(entries, schema)[0] is True


def test_read_chain_two_tuple_backward_compat(tmp_path):
    """Existing callers unpack a 2-tuple; the torn-tail recovery is opt-in only."""
    jl = tmp_path / "a.jsonl"
    L.write_chain(jl, [L.genesis("r", "p")])
    entries, schema = L.read_chain(jl)                          # 2-tuple on JSONL
    assert schema == 2 and len(entries) == 1
    obj = tmp_path / "b.json"
    obj.write_text(json.dumps({"chain": "x", "schema": 2, "entries": entries}))
    e2, s2 = L.read_chain(obj)                                  # 2-tuple on the {entries} object form
    assert s2 == 2 and len(e2) == 1
