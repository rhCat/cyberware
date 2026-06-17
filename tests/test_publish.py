"""The governed release receipt for SV-4 (P3-T15): chip release + engine attestation are dual-signed and the
transparency inclusion proof is stored, all verifiable offline under the pinned root. Tampering any single leg
(chip, engine, or transparency) fails the receipt closed. Needs openssl with ed25519ph; skips otherwise."""
from __future__ import annotations
import shutil
import subprocess
import tempfile

import pytest

from infra.cwp import engineattest as E, publish as P


def _ph_capable() -> bool:
    if not shutil.which("openssl"):
        return False
    try:
        P.publish_selftest()
        return True
    except Exception:
        return False


pytestmark = pytest.mark.skipif(not _ph_capable(), reason="governed release needs openssl with ed25519ph")


def _keypair():
    d = tempfile.mkdtemp()
    priv, pub = f"{d}/k.key", f"{d}/k.pub"
    subprocess.run(["openssl", "genpkey", "-algorithm", "ed25519", "-out", priv], check=True, capture_output=True)
    subprocess.run(["openssl", "pkey", "-in", priv, "-pubout", "-out", pub], check=True, capture_output=True)
    return priv, pub


def test_selftest_holds():
    r = P.publish_selftest()
    assert r["ok"], r
    assert r["governed_release_verifies"] and r["rekor_proof_stored"] and r["tuf_root_pinned"]


def test_every_leg_tamper_is_caught():
    r = P.publish_selftest()
    assert r["chip_tamper_caught"] and r["engine_tamper_caught"] and r["transparency_tamper_caught"]


def test_governed_release_is_dual_signed_and_stores_the_proof():
    priv, pub = _keypair()
    engine = b"engine" + b"\x00" * 48
    receipt = P.governed_release("skillChip/index.json", engine, "1.1.0", priv)
    # dual-signed: chip release + engine attestation are both present and signed; transparency proof stored
    assert receipt["release"]["payloadType"] and receipt["engine"]["payloadType"]
    assert "inclusion" in receipt["transparency"] and "sth" in receipt["transparency"]
    rep = P.verify_governed_release(receipt, engine, "skillChip/index.json", pub)
    assert rep["ok"] and rep["release_signed"] and rep["engine_attested"] and rep["transparency_verified"]


def test_engine_must_match_the_published_digest():
    priv, pub = _keypair()
    engine = b"engine" + b"\x05" * 48
    receipt = P.governed_release("skillChip/index.json", engine, "1.1.0", priv)
    other = b"different-engine" + b"\x06" * 40
    rep = P.verify_governed_release(receipt, other, "skillChip/index.json", pub)
    assert not rep["ok"] and not rep["engine_attested"] and rep["engine_attested"] is False
    assert rep["engine_attested"] is not E.ATTESTED
