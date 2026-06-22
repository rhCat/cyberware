"""P2-T12 — end-to-end govd→exod delegation through the live HTTP+WS+UDS path (the containment wiring).

A govd in delegated exec_mode hands each step to a real exod over a Unix socket; exod runs it (a stub runner
here — the real bwrap confinement is exec-image-only) and SIGNS the status; govd records the signed status
and the agent (run_delegated) runs NOTHING. Proves: the recorded authority is exod, the agent self-report is
rejected, and a delegated govd with no exod fails closed."""
from __future__ import annotations

import json
import os
import shutil
import subprocess
import tempfile
import threading
import time
import urllib.request

import pytest
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

from infra.exec.exod import Exod
from infra.govern import govd, govd_client


class _Stub:
    def __call__(self, profile, argv):
        return subprocess.CompletedProcess(argv, 0, "step-output-stays-server-side", "")


def _raw_pub(pk):
    from cryptography.hazmat.primitives import serialization
    return pk.public_bytes(serialization.Encoding.Raw, serialization.PublicFormat.Raw)


def _raw_priv(sk):
    from cryptography.hazmat.primitives import serialization
    return sk.private_bytes(serialization.Encoding.Raw, serialization.PrivateFormat.Raw,
                            serialization.NoEncryption())


@pytest.fixture
def delegated(tmp_path):
    """A govd bound in delegated exec_mode + a real exod listening on a UDS, sharing govd's grant key."""
    grant_key = Ed25519PrivateKey.generate()                 # govd's grant-issuer key
    exod_key = Ed25519PrivateKey.generate()                  # exod's distinct identity key
    sockdir = tempfile.mkdtemp(dir="/tmp")                   # short path — AF_UNIX caps at ~104 chars on macOS
    sock = os.path.join(sockdir, "e.sock")
    gk_path, pub_path = str(tmp_path / "grant.key"), str(tmp_path / "exod.pub")
    open(gk_path, "wb").write(_raw_priv(grant_key))
    open(pub_path, "wb").write(_raw_pub(exod_key.public_key()))

    exod = Exod(exod_key, grant_issuer_pub=grant_key.public_key(), runner=_Stub())
    t = threading.Thread(target=lambda: exod.serve(sock, max_requests=3), daemon=True)
    t.start()
    for _ in range(50):
        if os.path.exists(sock):
            break
        time.sleep(0.02)

    cfg = govd.load_config()
    cfg["mode"] = "local"
    cfg["local"] = {"host": "127.0.0.1", "ports": [0]}
    cfg["record_root"] = str(tmp_path / "rr")
    cfg["exec_mode"] = "delegated"
    cfg["exod"] = {"socket": sock, "grant_key": gk_path, "pub": pub_path}
    govd.ensure_monitor_token(cfg)
    httpd, _ = govd.bind_server("127.0.0.1", [0])
    httpd.daemon_threads = True
    httpd.cfg, httpd.store, httpd.rate_buckets = cfg, govd.Store(cfg["record_root"]), {}
    govd._load_exec_mode(cfg, httpd)
    threading.Thread(target=httpd.serve_forever, kwargs={"poll_interval": 0.02}, daemon=True).start()
    base = f"http://127.0.0.1:{httpd.server_address[1]}"
    for _ in range(100):
        try:
            urllib.request.urlopen(base + "/health", timeout=1); break
        except OSError:
            time.sleep(0.02)
    yield base, httpd
    httpd.shutdown(); httpd.server_close()
    shutil.rmtree(sockdir, ignore_errors=True)


def test_health_advertises_delegated_with_exod_attached(delegated):
    base, _ = delegated
    h = json.loads(urllib.request.urlopen(base + "/health").read())
    assert h["exec_mode"] == "delegated" and h["exod_attached"] is True


def test_delegated_run_status_is_exod_signed_agent_runs_nothing(delegated):
    base, httpd = delegated
    r = govd_client.run_delegated(base, {"skill": "fs", "perk": "find_large", "vars": {"SEARCH_DIR": "/tmp"}})
    assert r["mode"] == "delegated"
    assert r["results"] and r["results"][0]["status"] == "ok"
    assert r["results"][0]["authority"] == "exod"            # exod signed it; the agent reported nothing
    rec = httpd.store.get(r["run_id"])
    sr = [e for e in rec["events"] if e.get("type") == "step_result"]
    assert sr and sr[0]["authority"] == "exod" and sr[0]["exod_keyid"].startswith("ed25519:")
    assert "step-output-stays-server-side" not in json.dumps(rec)   # the step output never crossed to govd


def test_delegated_without_exod_fails_closed(tmp_path):
    cfg = govd.load_config()
    cfg.update({"mode": "local", "local": {"host": "127.0.0.1", "ports": [0]},
                "record_root": str(tmp_path / "rr"), "exec_mode": "delegated"})   # delegated but NO exod config
    govd.ensure_monitor_token(cfg)
    httpd, _ = govd.bind_server("127.0.0.1", [0])
    httpd.daemon_threads = True
    httpd.cfg, httpd.store, httpd.rate_buckets = cfg, govd.Store(cfg["record_root"]), {}
    govd._load_exec_mode(cfg, httpd)
    threading.Thread(target=httpd.serve_forever, kwargs={"poll_interval": 0.02}, daemon=True).start()
    base = f"http://127.0.0.1:{httpd.server_address[1]}"
    for _ in range(100):
        try:
            urllib.request.urlopen(base + "/health", timeout=1); break
        except OSError:
            time.sleep(0.02)
    try:
        r = govd_client.run_delegated(base, {"skill": "fs", "perk": "find_large", "vars": {"SEARCH_DIR": "/tmp"}})
        assert r["results"][0].get("refused")               # no exod -> every step refused, never run unconfined
    finally:
        httpd.shutdown(); httpd.server_close()
