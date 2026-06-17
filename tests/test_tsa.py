"""Trusted timestamp anchors for SV-4 (P3-T07): a high-value receipt is settlement-eligible only with a TSA
token that verifies offline against the receipt digest; absence, a tampered token, or a token bound to a
different receipt block settlement; a low-value receipt settles without one. Needs openssl with ed25519ph;
skips otherwise."""
from __future__ import annotations
import shutil
import subprocess
import tempfile

import pytest

from infra.cwp import tsa as T


def _capable() -> bool:
    if not shutil.which("openssl"):
        return False
    try:
        T.tsa_selftest()
        return True
    except Exception:
        return False


pytestmark = pytest.mark.skipif(not _capable(), reason="needs openssl with ed25519ph")


def test_selftest_holds():
    r = T.tsa_selftest()
    assert r["ok"], r


def test_absence_and_tamper_block_high_value_settlement():
    r = T.tsa_selftest()
    assert r["absence_blocks_settlement"] and r["tampered_token_blocked"] and r["wrong_receipt_token_blocked"]
    assert r["low_value_settles_without_token"] and r["token_verifies_offline"]


def test_token_is_bound_to_the_specific_receipt():
    d = tempfile.mkdtemp()
    priv, pub = f"{d}/tsa.key", f"{d}/tsa.pub"
    subprocess.run(["openssl", "genpkey", "-algorithm", "ed25519", "-out", priv], check=True, capture_output=True)
    subprocess.run(["openssl", "pkey", "-in", priv, "-pubout", "-out", pub], check=True, capture_output=True)
    receipt = {"run_id": "r1", "amount": 9000}
    tok = T.timestamp(receipt, 1_700_000_000, priv)
    assert T.verify_token(tok, receipt, pub)
    assert not T.verify_token(tok, {"run_id": "r2", "amount": 9000}, pub)   # different receipt → token invalid
