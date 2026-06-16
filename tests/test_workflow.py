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


def test_corpus_dual_checker_agrees():
    r = W.run_corpus()                                          # TLC + Apalache over 6 specs
    assert r["ok"], r
    assert r["tlc_correct"] == r["total"] and r["apalache_correct"] >= r["total"] - 1
    assert r["disagreements"] == []                            # the two checkers never disagree


def test_three_certificates_earned():
    c = W.certs()
    assert c["have_all_three"], c                              # EMPIRICAL + SYMBOLIC + AXIOMATIC


def test_saga_model_and_execution():
    # model: the good saga holds, the skip-compensation variant is caught
    assert W.check_tlc(W.SAGA)["verdict"] == "no_error"
    assert W.check_tlc(W.buggy_saga())["verdict"] == "violation"
    # execution: a mid-branch failure runs the compensations
    assert W.run_saga(3, fail_at=1)["compensation_ran"] is True


def test_workflow_algebra_product_automaton_within_budget():
    b = W.algebra_budget()
    assert b["within_budget"] and b["finite"]
    par = W.compose(W.SAMPLE, W.SAGA, "par")
    assert W.check_tlc(par)["verdict"] == "no_error"           # the product automaton is deadlock-free


def test_plan_as_workflow_is_clean():
    assert W.check_tlc(W.plan_workflow())["verdict"] == "no_error"   # the plan verifies the plan (P4-T09)
