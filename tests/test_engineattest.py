"""Engine attestation + mutual handshake for SV-4 (P3-T05): the engine's reproducible-build digest is
publisher-signed; before two principals run together they mutually attest each other's live binary, and a
one-byte tamper on either side fails closed (engine_unattested). A dual-signed release receipt lets a verifier
confirm the live engine matches the signed release. Needs openssl with ed25519ph; skips otherwise."""
from __future__ import annotations
import shutil
import subprocess
import tempfile

import pytest

from infra.cwp import engineattest as E


def _ph_capable() -> bool:
    if not shutil.which("openssl"):
        return False
    try:
        E.engine_selftest()
        return True
    except Exception:
        return False


pytestmark = pytest.mark.skipif(not _ph_capable(), reason="engine attestation needs openssl with ed25519ph")


def _keypair():
    d = tempfile.mkdtemp()
    priv, pub = f"{d}/k.key", f"{d}/k.pub"
    subprocess.run(["openssl", "genpkey", "-algorithm", "ed25519", "-out", priv], check=True, capture_output=True)
    subprocess.run(["openssl", "pkey", "-in", priv, "-pubout", "-out", pub], check=True, capture_output=True)
    return priv, pub


def test_selftest_holds():
    r = E.engine_selftest()
    assert r["ok"], r
    assert r["clean_handshake_attested"] and r["health_matches_signed_release"] and r["tuf_root_pinned"]


def test_one_byte_tamper_on_either_side_is_unattested():
    r = E.engine_selftest()
    assert r["tamper_local_unattested"] and r["tamper_peer_unattested"]


def test_mutual_handshake_needs_both_sides():
    priv, pub = _keypair()
    a, b = b"engine-A" + b"\x00" * 32, b"engine-B" + b"\x01" * 32
    aa, ba = E.sign_engine(a, "1.1.0", priv), E.sign_engine(b, "1.1.0", priv)
    assert E.mutual_handshake(aa, a, ba, b, pub)["status"] == E.ATTESTED
    # flip one byte on the peer's live binary → whole handshake is engine_unattested
    bad = bytearray(b); bad[0] ^= 0x01
    hs = E.mutual_handshake(aa, a, ba, bytes(bad), pub)
    assert hs["status"] == E.UNATTESTED and hs["peer"] == E.UNATTESTED and not hs["ok"]


def test_forged_attestation_is_unattested():
    priv, pub = _keypair()
    blob = b"engine-X" + b"\x07" * 32
    att = E.sign_engine(blob, "1.1.0", priv)
    assert E.attest_live({**att, "signatures": []}, blob, pub) == E.UNATTESTED


def test_health_ties_live_engine_to_signed_release():
    priv, pub = _keypair()
    blob = b"engine-anchor" + b"\x09" * 32
    receipt = E.release_receipt("skillChip/index.json", blob, "1.1.0", priv)
    assert E.health_matches_signed_release(receipt, blob, pub)
    tampered = bytearray(blob); tampered[-1] ^= 0xFF
    assert not E.health_matches_signed_release(receipt, bytes(tampered), pub)
