"""P4-T06 — the settlement lifecycle, model-checked (infra/cwp/workflow.prove_settlement).

The clean model passes EMPIRICAL (TLC) + SYMBOLIC (Apalache), and the three money mutants
(settle-before-validate / double-settle / strand-escrow) are each caught. Gated on the TLC + Apalache
provers (skips where absent — as test_workflow does for the full 3-prover stack)."""
from __future__ import annotations

import pytest

from infra.cwp import workflow as W

_HAVE = bool(W.TLA2TOOLS_JAR) and bool(W.APALACHE_MC)
pytestmark = pytest.mark.skipif(not _HAVE, reason="needs TLC (TLA2TOOLS_JAR) + Apalache (apalache-mc)")


def test_prove_settlement_clean_passes_and_money_mutants_caught():
    r = W.prove_settlement()
    assert r["ok"] is True, r
    assert r["empirical_plus_symbolic_pass"] is True     # clean model: no_error under TLC AND Apalache
    assert r["money_mutants_fail"] is True                # all 3 money mutants caught
    assert r["mutants_checked"] == 3
