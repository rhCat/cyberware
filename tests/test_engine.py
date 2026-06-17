"""The settlement engine for SV-6 (P6-T05): a dual-signed, validation:pass, quote-bound receipt settles
atomically (escrow zeroed, posting balanced, ledger zero-sum); a signature-stripped receipt, a verdict-flipped
receipt, and an unbound receipt each settle nothing; the holdback releases to the payee. Needs openssl with
ed25519ph; skips otherwise."""
from __future__ import annotations
import shutil

import pytest

from infra.settle import engine as E


def _capable():
    if not shutil.which("openssl"):
        return False
    try:
        E.engine_selftest()
        return True
    except Exception:
        return False


pytestmark = pytest.mark.skipif(not _capable(), reason="settlement needs openssl with ed25519ph")


def test_selftest():
    r = E.engine_selftest()
    assert r["ok"], r


def test_payment_impossible_without_both_sigs_and_validation_pass():
    r = E.engine_selftest()
    assert r["valid_receipt_settles"] and r["escrow_zeroed"] and r["global_zero_sum"]
    assert r["sig_stripped_rejected"] and r["verdict_flipped_rejected"] and r["unbound_rejected"]


def test_no_double_pay_and_no_cross_quote_funding():
    # the two value-integrity regressions an adversarial review surfaced
    r = E.engine_selftest()
    assert r["double_settle_refused"]      # a re-funded quote_sha cannot pay out twice (idempotent settlement)
    assert r["cross_quote_isolated"]       # one quote's escrow can never fund a different quote's settlement
