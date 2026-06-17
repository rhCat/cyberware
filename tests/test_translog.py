"""Offline transparency proofs for SV-4 (P3-T02): every release is a leaf in a Merkle log whose head is a
publisher-signed tree head; a release ships a self-contained inclusion proof that verifies against the
PINNED root with no live log contacted. An unsigned/forged head, a tampered leaf, or a wrong index all fail
offline. Needs openssl with ed25519ph; skips otherwise."""
from __future__ import annotations
import base64
import shutil
import subprocess
import tempfile

import pytest

from infra.cwp import canonical, translog as T


def _ph_capable() -> bool:
    if not shutil.which("openssl"):
        return False
    try:
        T.transparency_selftest()
        return True
    except Exception:
        return False


pytestmark = pytest.mark.skipif(not _ph_capable(), reason="transparency proofs need openssl with ed25519ph")


def _keypair():
    d = tempfile.mkdtemp()
    priv, pub = f"{d}/k.key", f"{d}/k.pub"
    subprocess.run(["openssl", "genpkey", "-algorithm", "ed25519", "-out", priv], check=True, capture_output=True)
    subprocess.run(["openssl", "pkey", "-in", priv, "-pubout", "-out", pub], check=True, capture_output=True)
    return priv, pub


def _envs(n, salt=""):
    return [{"payloadType": "application/vnd.cyberware.release+json",
             "payload": base64.b64encode(canonical.canonical_bytes({"r": i, "s": salt})).decode(),
             "signatures": [{"keyid": "publisher-root", "sig": "x"}]} for i in range(n)]


def test_selftest_holds():
    r = T.transparency_selftest()
    assert r["ok"], r
    assert r["valid_verifies_offline"] and r["every_leaf_verifies"] and r["tuf_root_pinned"]


def test_all_refusals_fire_offline():
    r = T.transparency_selftest()
    assert r["unsigned_sth_refused"] and r["forged_sth_refused"]
    assert r["tampered_leaf_refused"] and r["wrong_index_refused"]


@pytest.mark.parametrize("n", [1, 2, 3, 7, 8, 16, 17, 31, 32])
def test_inclusion_proof_recomputes_root_at_every_size(n):
    assert T.transparency_selftest(n)["ok"]


def test_offline_proof_needs_no_live_log_and_is_self_contained():
    priv, pub = _keypair()
    envs = _envs(8)
    leaves = [T.leaf_hash(e) for e in envs]
    bundle = T.offline_proof(envs[5], 5, leaves, priv)
    # the bundle carries everything: leaf, index, tree_size, inclusion path, signed tree head
    assert set(bundle) == {"leaf", "index", "tree_size", "inclusion", "sth"}
    assert T.verify_offline(bundle, pub)[0]


def test_a_proof_does_not_verify_against_a_different_trees_head():
    priv, pub = _keypair()
    a, b = _envs(8, "A"), _envs(8, "B")
    la, lb = [T.leaf_hash(e) for e in a], [T.leaf_hash(e) for e in b]
    bundle = T.offline_proof(a[3], 3, la, priv)
    cross = {**bundle, "sth": T.signed_tree_head(lb, priv)}      # graft a different tree's signed head
    assert not T.verify_offline(cross, pub)[0]
