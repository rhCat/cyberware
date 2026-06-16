"""Truth-in-labeling doc lint (P0-T16): every enforcement claim in the specs cites a criterion-id; a claim
without one is caught, and casual prose is not mistaken for a claim."""
from __future__ import annotations

from infra.cwp import labeling


def test_real_specs_pass_truth_in_labeling():
    r = labeling.lint_specs(labeling.DEFAULT_SPECS)
    assert r["ok"], r["violations"]
    assert r["claims"] > 0 and r["docs_with_claims"] >= 3        # the convention is genuinely exercised


def test_enforcement_claim_without_a_criterion_id_is_caught():
    bad = "## X\n\nThis control is *Enforced by:* the runtime, trust us.\n"
    r = labeling.lint_text(bad)
    assert r["claims"] == 1 and len(r["violations"]) == 1


def test_enforcement_claim_with_a_criterion_id_passes():
    good = "## X\n\n*Enforced by: P0-V12 (the KeyStore seam) and F5 (the transport tourniquet).*\n"
    r = labeling.lint_text(good)
    assert r["claims"] == 1 and r["violations"] == []


def test_casual_lowercase_enforced_is_not_a_claim():
    prose = "## X\n\nThe abstraction is checked; the enforced data plane is the executor's job.\n"
    r = labeling.lint_text(prose)
    assert r["claims"] == 0 and r["violations"] == []            # not a labeling claim, so not flagged


def test_uppercase_ENFORCED_tag_needs_a_criterion():
    assert labeling.lint_text("[ENFORCED] the gate runs.")["violations"]          # tag, no id -> caught
    assert labeling.lint_text("[ENFORCED: P2-V14] the gate runs.")["violations"] == []   # tag + id -> ok
