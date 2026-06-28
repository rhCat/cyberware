"""Integration + unit: fleetd.py — the :8773 FLEET discovery plane (default-on, beside govd's :5773).

Pins the invariants: /fleet/health is ungated; /fleet/nodes + /fleet/find are Bearer-gated (deny-by-default,
reusing govd's principals trust root); the roster degrades to self-only with no config (graceful standalone,
never raises); a dead peer is marked healthy:false (never silently dropped); find resolves to a node's :5773
URL or 404s, and never routes to an unhealthy node.
"""
from __future__ import annotations
import json
import threading
import time
import urllib.error
import urllib.request

import pytest

from infra.govern import fleetd
from infra.govern import principals as P


def _start(cfg):
    fleetd._CACHE.clear()                                  # the 5s TTL cache must not leak across servers
    srv = fleetd.start(cfg, "127.0.0.1", port=0, self_url="http://127.0.0.1:5773")
    threading.Thread(target=srv.serve_forever, kwargs={"poll_interval": 0.02}, daemon=True).start()
    base = f"http://127.0.0.1:{srv.server_address[1]}"
    for _ in range(100):
        try:
            urllib.request.urlopen(base + "/fleet/health", timeout=1); break
        except OSError:
            time.sleep(0.02)
    return srv, base


def _get(base, path, token=None):
    req = urllib.request.Request(base + path)
    if token:
        req.add_header("Authorization", "Bearer " + token)
    try:
        r = urllib.request.urlopen(req, timeout=3)
        return r.status, json.loads(r.read())
    except urllib.error.HTTPError as e:
        return e.code, json.loads(e.read() or b"{}")


@pytest.fixture
def open_server():
    """No registry -> auth disabled (local dev); self-only roster."""
    srv, base = _start({"mode": "local", "exec_mode": "cooperative", "principals": {}})
    yield base
    srv.shutdown(); srv.server_close()


@pytest.fixture
def gated_server():
    """A registry present -> Bearer mandatory; token 'S' is principal 'agent'."""
    reg = {"agent": {"token_sha": P.token_sha("S"), "rate": 100.0, "burst": 100.0}}
    srv, base = _start({"mode": "remote", "exec_mode": "cooperative", "principals": reg})
    yield base
    srv.shutdown(); srv.server_close()


# ── auth: the aggregate roster is gated; own-liveness is not ──
def test_fleet_health_is_ungated(gated_server):
    code, d = _get(gated_server, "/fleet/health")              # no token, even with a registry present
    assert code == 200 and d["service"] == "cyberware-fleetd" and d["roster_source"] == "self"


def test_nodes_denied_without_valid_bearer(gated_server):
    assert _get(gated_server, "/fleet/nodes")[0] == 401        # no token
    assert _get(gated_server, "/fleet/nodes", token="wrong")[0] == 401
    code, d = _get(gated_server, "/fleet/nodes", token="S")    # the real principal token
    assert code == 200 and isinstance(d["nodes"], list)


def test_find_also_gated(gated_server):
    assert _get(gated_server, "/fleet/find?skill=x")[0] == 401


def test_no_registry_disables_auth(open_server):
    code, d = _get(open_server, "/fleet/nodes")                # local dev: registry empty -> no token needed
    assert code == 200 and len(d["nodes"]) == 1


# ── graceful standalone: self-only, real capability, no error ──
def test_self_only_roster(open_server):
    code, d = _get(open_server, "/fleet/nodes")
    assert code == 200 and len(d["nodes"]) == 1
    me = d["nodes"][0]
    assert me["url"] == "http://127.0.0.1:5773" and me["healthy"] is True
    assert me["chip_sha"] and isinstance(me["skills"], list) and me["skills"]   # real chip + real skills


# ── find: where-not-what ──
def test_find_resolves_to_self_for_offered_skill(open_server):
    _, nodes = _get(open_server, "/fleet/nodes")
    skill = nodes["nodes"][0]["skills"][0]                     # a skill this node really offers
    code, d = _get(open_server, f"/fleet/find?skill={skill}")
    assert code == 200 and d["url"] == "http://127.0.0.1:5773" and d["skill"] == skill


def test_find_unknown_skill_404(open_server):
    code, d = _get(open_server, "/fleet/find?skill=__nope__")
    assert code == 404 and d["url"] is None


def test_find_requires_skill_param(open_server):
    assert _get(open_server, "/fleet/find")[0] == 400


# ── peer probing: a dead peer is marked, never dropped, never routed to ──
def test_down_peer_marked_unhealthy_not_dropped(tmp_path, monkeypatch):
    roster = tmp_path / "fleet.json"
    roster.write_text(json.dumps({"nodes": [{"name": "ghost", "url": "http://127.0.0.1:1", "tier": "core"}]}))
    monkeypatch.setenv("FLEETD_FLEET", str(roster))
    srv, base = _start({"mode": "local", "exec_mode": "cooperative", "principals": {}})
    try:
        code, d = _get(base, "/fleet/nodes")
        assert code == 200
        urls = {n["url"]: n for n in d["nodes"]}
        assert "http://127.0.0.1:1" in urls                   # the dead peer is PRESENT (not silently dropped)
        ghost = urls["http://127.0.0.1:1"]
        assert ghost["healthy"] is False and ghost["last_seen"] is None and ghost["skills"] == []
        self_skill = urls["http://127.0.0.1:5773"]["skills"][0]
        _, d2 = _get(base, f"/fleet/find?skill={self_skill}&all=1")   # find never routes to the dead peer
        assert all(n["healthy"] for n in d2["nodes"])
        assert "http://127.0.0.1:1" not in {n["url"] for n in d2["nodes"]}
    finally:
        srv.shutdown(); srv.server_close()


# ── pure units ──
def test_tier_ceiling():
    assert fleetd._tier_ok("core", "verified") is True        # core is at least as trusted as verified
    assert fleetd._tier_ok("community", "verified") is False
    assert fleetd._tier_ok("verified", "verified") is True
    assert fleetd._tier_ok(None, "core") is False             # unknown node tier cannot satisfy a filter
    assert fleetd._tier_ok("core", None) is True              # no filter -> no constraint
    assert fleetd._tier_ok("core", "garbage") is True         # unrecognized filter -> no constraint


def test_load_roster_empty_not_throw(tmp_path, monkeypatch):
    monkeypatch.delenv("FLEETD_FLEET", raising=False)
    monkeypatch.delenv("FLEETD_FLEET_URL", raising=False)
    assert fleetd.load_roster({}) == []                       # absent -> [] (graceful, never raises)
    bad = tmp_path / "bad.json"; bad.write_text("{ not json")
    monkeypatch.setenv("FLEETD_FLEET", str(bad))
    assert fleetd.load_roster({}) == []                       # unreadable -> [] (never raises)
