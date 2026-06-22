"""P6-T03 escrow liveness (expiry + auto-refund) and P6-T07 code↔blueprint bisimulation."""
from __future__ import annotations

import os

from infra.cwp import workflow as W
from infra.settle import escrow_expiry


def test_escrow_expiry_auto_refunds_only_expired_unsettled():
    r = escrow_expiry.escrow_expiry_selftest()
    assert r["ok"] is True, r
    assert r["only_expired_unsettled_refunded"] is True
    assert r["live_escrow_untouched"] is True and r["global_zero"] is True
    assert r["no_stale_escrow_after_sweep"] is True and r["sweep_idempotent"] is True


def test_settlement_lifecycle_bisimilar_to_blueprint():
    bp = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                      "infra", "settle", "settlement.blueprint.json")
    r = W.prove_bisimulation(bp)
    assert r["ok"] is True, r
    assert r["bisimilar"] is True and not r["code_only"] and not r["blueprint_only"]
    assert r["seeded_extra_transition_fails"] is True
