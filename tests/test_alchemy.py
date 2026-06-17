"""The alchemy concordance validator (P3-T08) + the Citrinitas publish gate (P3-T09), SV-4. alchemy wraps the
pinned putrefactio extractor (extract/conserve/classify) + alembic (declared blueprint / citrinitas) in
file-mode. Each verb runs the REAL engine and is shown to discriminate (clean→0, a seeded defect→>0). The
gate blocks publish on a seeded conservation defect, an unnamed shape, and a CFG mismatch — each with its
named reason — and chip-wide concord passes. Needs the pinned putrefactio checkout; SKIPS otherwise (CI)."""
from __future__ import annotations

import pytest

from infra.cwp import alchemy as A

pytestmark = pytest.mark.skipif(not A.tools_present(), reason="needs the pinned putrefactio extractor checkout")


def test_extract_emits_lpp_per_snippet_core():
    r = A.extract_selftest()
    assert r["ok"] and r["lpp_emitted"] and r["blueprint_count"] >= 1


def test_classify_names_every_resource_call_and_catches_unnamed():
    r = A.classify_selftest()
    assert r["ok"] and r["clean_unnamed"] == 0 and r["exotic_unnamed"] >= 1


def test_conserve_law_fires_on_a_real_leak():
    r = A.conserve_selftest()
    assert r["ok"] and r["clean_unexplained_defects"] == 0 and r["leak_unexplained_defects"] >= 1


def test_concord_containment_and_diff():
    r = A.concord_selftest()
    assert r["ok"] and r["contained"] and r["tamper_caught"]
    assert r["violating_edges"]                                 # the diff is stored, non-empty on tamper


def test_citrinitas_gate_triple_block():
    tb = A.triple_block()
    assert tb["ok"]
    assert tb["conservation_blocked"] and tb["unnamed_blocked"] and tb["cfg_mismatch_blocked"]
    assert tb["clean_admitted"]


def test_chip_wide_concord_passes_and_is_not_vacuous():
    cw = A.chip_wide_concord("skillChip")
    assert cw["ok"] and cw["rate"] == 1.0 and cw["modeled"] >= 1
    assert not cw["drifted"] and not cw["unpinned"]
    assert cw["discriminates"]                                  # a rogue edge IS caught vs the pinned declared


def test_chip_wide_concord_fails_on_drift():
    # the check is a real drift gate, not a tautology: a declared blueprint that no longer matches the live
    # porter must be flagged as drift (ok=False)
    import json
    import tempfile
    decl = json.load(open(A.DECLARED_PATH))
    k = sorted(decl)[0]
    bad = dict(decl)
    bad[k] = {"states": ["stmtZ"], "edges": []}                 # declared no longer permits the live CFG
    p = tempfile.mktemp(suffix=".json")
    json.dump(bad, open(p, "w"))
    cw = A.chip_wide_concord("skillChip", p)
    assert not cw["ok"] and k in cw["drifted"]
