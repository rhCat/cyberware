"""Workflow model-checking for SV-5 (the P4 tranche): a workflow emits typed TLA+, the three independent
provers agree on a clean spec (EMPIRICAL · SYMBOLIC · AXIOMATIC), and a seeded invariant violation is
caught by the bounded checkers. The provers (TLC / Apalache / TLAPS) are heavy + environment-specific, so
this module SKIPS where they are absent (the plain CI image) and runs where the 3-prover stack is installed.
"""
from __future__ import annotations
import shutil

import pytest

from infra.cwp import workflow as W

_HAVE = bool(W.TLA2TOOLS_JAR) and bool(W.APALACHE_MC) and bool(shutil.which("tlapm"))
pytestmark = pytest.mark.skipif(not _HAVE, reason="needs the 3-prover stack (TLA2TOOLS_JAR + apalache-mc + tlapm)")


def test_emit_tla_is_typed_and_carries_invariants():
    tla = W.emit_tla(W.SAMPLE)
    assert "@type: Str" in tla and "@type: Bool" in tla        # Apalache type annotations
    assert "StartedBeforeDone" in tla and "TypeOK" in tla      # the invariants are emitted


def test_clean_workflow_earns_all_three_certs():
    r = W.run_all(W.SAMPLE)
    assert r["clean"] and r["certs"] == ["AXIOMATIC", "EMPIRICAL", "SYMBOLIC"]
    by = {x["prover"]: x["verdict"] for x in r["results"]}
    assert by["tlc"] == "no_error" and by["apalache"] == "no_error" and by["tlaps"] == "proved"


def test_seeded_violation_is_caught_by_the_bounded_checkers():
    bad = W.seed_violation(W.SAMPLE, "started")                # the "good" started:=True becomes :=False
    r = W.run_all(bad)
    by = {x["prover"]: x["verdict"] for x in r["results"]}
    assert by["tlc"] == "violation" and by["apalache"] == "violation"   # both independently catch it
    assert not r["clean"]
