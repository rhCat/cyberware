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


# ── fleet_tier: the topology HIERARCHY, orthogonal to the trust tier ──
def test_fleet_rank_named_numeric_and_unknown():
    assert fleetd._fleet_rank("mothership") == 1
    assert fleetd._fleet_rank("EDGE") == 2                     # case-insensitive
    assert fleetd._fleet_rank("subagent") == 3
    assert fleetd._fleet_rank("4") == 4 and fleetd._fleet_rank(5) == 5   # 'and so on' — deeper ints verbatim
    assert fleetd._fleet_rank(None) is None
    assert fleetd._fleet_rank("garbage") is None
    assert fleetd._fleet_rank(0) is None and fleetd._fleet_rank(-1) is None
    assert fleetd._fleet_rank(True) is None                   # a bool is not a tier (int-subclass guard)


def test_fleet_tier_ok_is_exact_by_rank():
    assert fleetd._fleet_tier_ok("subagent", None) is True    # no filter -> no constraint
    assert fleetd._fleet_tier_ok("subagent", "garbage") is True
    assert fleetd._fleet_tier_ok("subagent", "subagent") is True
    assert fleetd._fleet_tier_ok("subagent", "3") is True     # numeric alias of the same rank matches
    assert fleetd._fleet_tier_ok("edge", "subagent") is False
    assert fleetd._fleet_tier_ok(None, "subagent") is False   # an unranked node never wins a constrained query


def test_self_descriptor_carries_fleet_tier():
    srv, base = _start({"mode": "local", "exec_mode": "cooperative", "principals": {},
                        "fleet": {"fleet_tier": "mothership", "tier": "core"}})
    try:
        _, d = _get(base, "/fleet/nodes")
        me = d["nodes"][0]
        assert me["fleet_tier"] == "mothership" and me["tier"] == "core"   # both orthogonal axes present
    finally:
        srv.shutdown(); srv.server_close()


def test_probe_carries_fleet_tier_even_when_peer_is_down(tmp_path, monkeypatch):
    roster = tmp_path / "fleet.json"
    roster.write_text(json.dumps({"nodes": [
        {"name": "ghost", "url": "http://127.0.0.1:1", "tier": "core", "fleet_tier": "subagent"}]}))
    monkeypatch.setenv("FLEETD_FLEET", str(roster))
    srv, base = _start({"mode": "local", "exec_mode": "cooperative", "principals": {}})
    try:
        _, d = _get(base, "/fleet/nodes")
        ghost = {n["url"]: n for n in d["nodes"]}["http://127.0.0.1:1"]
        assert ghost["fleet_tier"] == "subagent"              # topology is roster-declared; survives an unreachable probe
    finally:
        srv.shutdown(); srv.server_close()


def test_find_filters_by_fleet_tier(monkeypatch):
    srv, base = _start({"mode": "local", "exec_mode": "cooperative", "principals": {},
                        "fleet": {"fleet_tier": "mothership"}})
    try:
        _, nodes = _get(base, "/fleet/nodes")
        skill = nodes["nodes"][0]["skills"][0]                 # a skill self really offers
        hit = _get(base, f"/fleet/find?skill={skill}&fleet_tier=mothership")
        assert hit[0] == 200 and hit[1]["fleet_tier"] == "mothership"
        miss = _get(base, f"/fleet/find?skill={skill}&fleet_tier=subagent")   # self is mothership, not subagent
        assert miss[0] == 404
    finally:
        srv.shutdown(); srv.server_close()


# ── pure units ──
def test_tier_ceiling():
    assert fleetd._tier_ok("core", "verified") is True        # core is at least as trusted as verified
    assert fleetd._tier_ok("community", "verified") is False
    assert fleetd._tier_ok("verified", "verified") is True
    assert fleetd._tier_ok("core", None) is True              # no filter -> no constraint
    assert fleetd._tier_ok("core", "garbage") is True         # unrecognized filter -> no constraint
    # an untiered node is treated as the LEAST-trusted (community): matches a loose filter, never an elevated one
    assert fleetd._tier_ok(None, "community") is True
    assert fleetd._tier_ok(None, "verified") is False
    assert fleetd._tier_ok(None, "core") is False             # never wins a tier=core query (no unearned trust)


def test_load_roster_empty_not_throw(tmp_path, monkeypatch):
    monkeypatch.delenv("FLEETD_FLEET", raising=False)
    monkeypatch.delenv("FLEETD_FLEET_URL", raising=False)
    assert fleetd.load_roster({}) == []                       # absent -> [] (graceful, never raises)
    bad = tmp_path / "bad.json"; bad.write_text("{ not json")
    monkeypatch.setenv("FLEETD_FLEET", str(bad))
    assert fleetd.load_roster({}) == []                       # unreadable -> [] (never raises)


# ── hardening regressions (from the adversarial review) ──
def test_health_does_not_disclose_roster_size(gated_server):
    # M1: the ungated health path must NOT fetch the roster or leak fleet size — bare liveness only
    code, d = _get(gated_server, "/fleet/health")
    assert code == 200 and "peers_configured" not in d
    assert set(d) == {"status", "service", "self_url", "roster_source"}


def test_ssrf_only_http_schemes_are_dereferenced(monkeypatch):
    # L2: file:// / ftp:// roster sources are rejected before any dereference
    monkeypatch.setenv("FLEETD_FLEET_URL", "file:///etc/passwd")
    assert fleetd.load_roster({}) == []
    monkeypatch.delenv("FLEETD_FLEET_URL")
    assert fleetd._safe_url("http://x:5773") and fleetd._safe_url("https://x:5773")
    assert not fleetd._safe_url("file:///etc/passwd") and not fleetd._safe_url("ftp://x/")
    assert fleetd._nodes_of({"nodes": [{"url": "file:///x"}, {"url": "http://ok:5773"}]}) == [{"url": "http://ok:5773"}]


def test_named_local_principal_is_still_rate_limited():
    # L4: a registry principal literally named "local" must NOT bypass the throttle (gate on registry, not pid)
    reg = {"local": {"token_sha": P.token_sha("T"), "rate": 0.0, "burst": 1.0}}
    srv, base = _start({"mode": "remote", "exec_mode": "cooperative", "principals": reg})
    try:
        assert _get(base, "/fleet/nodes", token="T")[0] == 200    # first: the one burst token
        assert _get(base, "/fleet/nodes", token="T")[0] == 429    # second: throttled, despite pid == "local"
    finally:
        srv.shutdown(); srv.server_close()
