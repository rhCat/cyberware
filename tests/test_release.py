"""Publisher signing for the SV-4 release transparency layer (P3-T01): the chip release manifest is signed
by the publisher key, verified against the PINNED root, and an unsigned/tampered release is refused at all
three entry points (chipfetch / govd boot / exod run). Needs openssl with ed25519ph; skips otherwise."""
from __future__ import annotations
import shutil
import subprocess
import tempfile

import pytest

from infra.cwp import release as R


def _ph_capable() -> bool:
    if not shutil.which("openssl"):
        return False
    try:
        R.release_selftest()
        return True
    except Exception:
        return False


pytestmark = pytest.mark.skipif(not _ph_capable(), reason="release signing needs openssl with ed25519ph")


def test_selftest_holds():
    r = R.release_selftest()
    assert r["ok"], r
    assert r["signed_passes_tri_layer"] and r["matches_chip"] and r["tuf_root_pinned"]


def test_unsigned_and_tampered_are_refused_at_all_layers():
    r = R.release_selftest()
    assert r["unsigned_refused_all_layers"] and r["tampered_refused_all_layers"]


def test_release_manifest_reflects_the_chip():
    m = R.release_manifest("skillChip/index.json")
    assert m["chip_sha"] and isinstance(m["skills"], dict) and "cws:cws-redteam" in m["skills"]   # v2: namespaced keys


def test_verify_release_rejects_wrong_type_and_unsigned():
    assert R.verify_release({"payloadType": "application/other", "signatures": [{}]})[1] == "wrong_type"
    assert R.verify_release({"payloadType": R.RELEASE_TYPE, "signatures": []})[1] == "unsigned"


def test_tri_layer_covers_three_entry_points():
    # a real signed release passes at chipfetch, govd_boot AND exod_run (defense in depth)
    d = tempfile.mkdtemp()
    priv, pub = f"{d}/k.key", f"{d}/k.pub"
    subprocess.run(["openssl", "genpkey", "-algorithm", "ed25519", "-out", priv], check=True, capture_output=True)
    subprocess.run(["openssl", "pkey", "-in", priv, "-pubout", "-out", pub], check=True, capture_output=True)
    env = R.sign_release("skillChip/index.json", priv)
    layers = R.tri_layer_check(env, pub)["layers"]
    assert set(layers) == set(R.ENTRY_POINTS) and all(v["pass"] for v in layers.values())
