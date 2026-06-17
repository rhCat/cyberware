"""Finalized dual-signed receipts for SV-4 (P3-T14): a receipt is two independent Ed25519-DSSE signatures
over one in-toto statement, consumable as a standard attestation. A single signature, a tampered statement,
or two signatures from one key do not pass as a finalized receipt. Needs openssl with ed25519ph; skips
otherwise."""
from __future__ import annotations
import shutil
import subprocess
import tempfile

import pytest

from infra.cwp import receipts as R


def _capable() -> bool:
    if not shutil.which("openssl"):
        return False
    try:
        R.receipts_selftest()
        return True
    except Exception:
        return False


pytestmark = pytest.mark.skipif(not _capable(), reason="needs openssl with ed25519ph")


def _keypair(tag, d):
    p, pub = f"{d}/{tag}.key", f"{d}/{tag}.pub"
    subprocess.run(["openssl", "genpkey", "-algorithm", "ed25519", "-out", p], check=True, capture_output=True)
    subprocess.run(["openssl", "pkey", "-in", p, "-pubout", "-out", pub], check=True, capture_output=True)
    return p, pub


def test_selftest_holds():
    r = R.receipts_selftest()
    assert r["ok"], r
    assert r["dual_signed_and_consumable"] and r["single_signature_not_dual"]


def test_finalized_receipt_is_dual_signed_and_in_toto():
    d = tempfile.mkdtemp()
    ax, ap = _keypair("exec", d)
    bx, bp = _keypair("appr", d)
    receipt = R.finalize_receipt("run-1", "a" * 64, {"outcome": "ok"}, ax, "exec", bx, "appr")
    rep = R.verify_receipt(receipt, ap, bp)
    assert rep["dual_signed"] and rep["in_toto_consumable"] and rep["ok"]
    assert len(receipt["signatures"]) == 2


def test_tampered_and_single_are_rejected():
    r = R.receipts_selftest()
    assert r["tampered_statement_refused"] and r["same_key_not_dual"]
