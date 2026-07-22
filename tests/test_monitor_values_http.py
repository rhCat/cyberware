"""End-to-end HTTP test of GET /monitor/values/<run_id> — the exact node endpoint the fleet monitor proxies to
for plaintext tool-use review (live-proxy model, decryption node-side). Proves: (1) the monitor-token gate
(403 without), (2) a recorded run's values decrypt and return over HTTP, (3) the value-free /monitor/run for
the same run carries only values_sha, never the values."""
import json
import threading
import urllib.error
import urllib.request

import pytest

from infra.govern import govd


@pytest.fixture
def server(tmp_path):
    cfg = govd.load_config()
    cfg["mode"] = "local"
    cfg["local"] = {"host": "127.0.0.1", "ports": [0]}
    cfg["record_root"] = str(tmp_path / "rr")
    govd.ensure_monitor_token(cfg)
    httpd, _ = govd.bind_server("127.0.0.1", [0])
    httpd.daemon_threads = True
    httpd.cfg, httpd.store, httpd.rate_buckets = cfg, govd.Store(cfg["record_root"], cfg=cfg), {}
    threading.Thread(target=httpd.serve_forever, kwargs={"poll_interval": 0.02}, daemon=True).start()
    base = f"http://127.0.0.1:{httpd.server_address[1]}"
    for _ in range(100):
        try:
            urllib.request.urlopen(base + "/health", timeout=1); break
        except OSError:
            import time; time.sleep(0.02)
    yield base, httpd, cfg["monitor_token"]
    httpd.shutdown(); httpd.server_close()


def _get(url, token=None):
    req = urllib.request.Request(url, headers={"X-Govd-Monitor": token} if token else {})
    with urllib.request.urlopen(req, timeout=3) as r:
        return r.status, json.load(r)


def test_monitor_values_gate_and_roundtrip(server):
    base, httpd, tok = server
    # a real run: the allow record exists (create), then a terminal step records values (the WS-handler order)
    httpd.store.create("runE2E", {"run_id": "runE2E", "skill": "x:y", "perk": "run", "decision": "allow",
                                  "seq": ["t1"], "events": [], "var_keys": ["SOURCE", "LIMIT", "INTEL_PROVIDER"],
                                  "plan_sha": "p" * 64, "ts": "2026-07-22T00:00:00Z"})
    vals = {"SOURCE": "/repos/curl", "LIMIT": "50", "INTEL_PROVIDER": "nvidia"}
    sha = httpd.store.record_values("runE2E", "1", "2026-07-22T00:00:00Z", vals)
    httpd.store.append("runE2E", {"type": "step_result", "step": "1", "status": "ok", "exit": 0,
                                  "authority": "exod", "values_sha": sha})
    httpd.store.mirror.flush()
    assert sha and len(sha) == 64

    # (1) unauthenticated -> 403, no plaintext
    try:
        _get(base + "/monitor/values/runE2E")
        assert False, "expected 403 without monitor token"
    except urllib.error.HTTPError as e:
        assert e.code == 403

    # (2) authenticated -> decrypted values over HTTP
    st, body = _get(base + "/monitor/values/runE2E", token=tok)
    assert st == 200
    steps = body["steps"]
    assert len(steps) == 1 and steps[0]["values"] == vals and steps[0]["values_sha"] == sha

    # (3) the value-free /monitor/run for the same run must NOT carry the plaintext, only the commitment
    _, detail = _get(base + "/monitor/run/runE2E", token=tok)
    blob = json.dumps(detail)
    assert "/repos/curl" not in blob and "nvidia" not in blob   # no plaintext value leaked into the value-free view
