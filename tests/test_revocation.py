"""The signed revocation feed for SV-4 (P3-T03): a monotonic, publisher-signed `{seq, expires, revoked[]}`
feed. A revoked artifact is refused, a stale feed is `feed_stale` and fails closed, a replayed older feed is
`rollback`, and a forged feed is `bad_signature`. Needs openssl with ed25519ph; skips otherwise."""
from __future__ import annotations
import shutil
import subprocess
import tempfile

import pytest

from infra.cwp import revocation as R


def _ph_capable() -> bool:
    if not shutil.which("openssl"):
        return False
    try:
        R.revocation_selftest()
        return True
    except Exception:
        return False


pytestmark = pytest.mark.skipif(not _ph_capable(), reason="revocation feed needs openssl with ed25519ph")


def _keypair():
    d = tempfile.mkdtemp()
    priv, pub = f"{d}/k.key", f"{d}/k.pub"
    subprocess.run(["openssl", "genpkey", "-algorithm", "ed25519", "-out", priv], check=True, capture_output=True)
    subprocess.run(["openssl", "pkey", "-in", priv, "-pubout", "-out", pub], check=True, capture_output=True)
    return priv, pub


def test_selftest_holds():
    r = R.revocation_selftest()
    assert r["ok"], r


def test_rollback_and_stale_and_forgery_are_named():
    r = R.revocation_selftest()
    assert r["rollback_refused"] and r["stale_refused"] and r["forged_refused"]


def test_a_revoked_artifact_is_refused_and_others_run():
    priv, pub = _keypair()
    t0 = 1_700_000_000
    bad, good = "sha256:" + "a" * 64, "sha256:" + "c" * 64
    feed = R.sign_feed(5, [bad], t0, 3600, priv)
    assert R.revocation_decision(feed, bad, t0 + 10, last_seq=4, pinned_pub_pem=pub)["allow"] is False
    assert R.revocation_decision(feed, good, t0 + 10, last_seq=4, pinned_pub_pem=pub)["allow"] is True


def test_stale_feed_fails_closed_even_for_unlisted_artifacts():
    priv, pub = _keypair()
    t0 = 1_700_000_000
    feed = R.sign_feed(2, [], t0, 60, priv)                      # expires at t0+60
    d = R.revocation_decision(feed, "sha256:" + "d" * 64, t0 + 9999, last_seq=1, pinned_pub_pem=pub)
    assert d["allow"] is False and d["reason"] == "feed_stale"


def test_monotonic_seq_blocks_replay():
    priv, pub = _keypair()
    t0 = 1_700_000_000
    old = R.sign_feed(3, ["sha256:" + "a" * 64], t0, 3600, priv)
    # a consumer that has already accepted seq=4 must reject a replayed seq=3
    assert R.verify_feed(old, t0 + 10, last_seq=4, pinned_pub_pem=pub)[1] == "rollback"
