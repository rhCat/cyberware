"""fleetdash — the fleet CENTRAL CONTROL plane: a durable mirror of every node's value-free ledgers, inspectable
from the center even when a node is down, with a high-risk/approval banner. Hermetic — the govd HTTP layer is
faked, so no live node is needed."""
from __future__ import annotations

import json
import os
import pathlib
import re
import shutil
import subprocess
import tempfile
import urllib.error
import urllib.parse

import pytest

from infra.tool import fleetdash as F


def _page_of(url):
    q = urllib.parse.urlparse(url).query
    return int(dict(urllib.parse.parse_qsl(q)).get("page", "1"))

# a node's faked monitor surface: 3 runs across 2 decision pages, with full per-run detail.
_DECISIONS = {
    1: [{"run_id": "r1", "ts": "2026-01-01T00:00:03", "principal": "agent-1", "skill": "fs", "perk": "rm",
         "decision": "push_back", "destructive": True},
        {"run_id": "r2", "ts": "2026-01-01T00:00:02", "principal": "agent-1", "skill": "fs", "perk": "wipe",
         "decision": "allow", "destructive": True}],
    2: [{"run_id": "r3", "ts": "2026-01-01T00:00:01", "principal": "agent-1", "skill": "search", "perk": "loc",
         "decision": "reject", "destructive": False}],
}
_DETAIL = {
    "r2": {"run_id": "r2", "skill": "fs", "perk": "wipe", "decision": "allow", "destructive": True,
           "seq": ["wipe_tool"], "plan_sha": "p2", "var_keys": ["DIR"], "problems": [],
           "events": [{"type": "granted", "step": "1"},
                      {"type": "step_result", "step": "1", "status": "ok", "authority": "exod"}]},
}


def _fake_get(url, token=None, timeout=6):
    if url.endswith("/health"):
        return {"service": "cyberware-govd", "mode": "remote", "exec_mode": "delegated",
                "exod_attached": True, "chip_sha": "deadbeefcafef00d", "runs": 3}
    if "/monitor/state" in url:
        page = _page_of(url)
        return {"now": "2026-01-01T00:00:09", "decisions": _DECISIONS.get(page, []),
                "decisions_page": {"page": page, "pages": 2, "total": 3, "limit": 2}}
    if "/monitor/run/" in url:
        rid = url.rsplit("/monitor/run/", 1)[1]
        return dict(_DETAIL.get(rid, {"run_id": rid}))      # r1/r3 have no extra detail (decision meta only)
    raise urllib.error.URLError("unexpected url")


@pytest.fixture
def node_and_mirror(monkeypatch):
    monkeypatch.setattr(F, "_get", _fake_get)
    node = {"name": "body-1", "role": "body", "url": "http://10.0.0.1:5773", "token": "mtok"}
    mdir = tempfile.mkdtemp(prefix="fleetmirror-")
    return node, mdir


def test_mirror_persists_every_run_value_free(node_and_mirror):
    node, mdir = node_and_mirror
    summ = F.mirror_node(node, mdir)
    assert summ["mirrored"] == 3 and summ["total"] == 3 and "error" not in summ
    base = os.path.join(mdir, "body-1")
    idx = json.load(open(os.path.join(base, "index.json")))
    assert set(idx) == {"r1", "r2", "r3"}
    # full detail persisted for r2 (steps + exod authority)
    r2 = json.load(open(os.path.join(base, "runs", "r2.json")))
    assert r2["events"][1]["authority"] == "exod" and r2["_node"] == "body-1"
    # VALUE-FREE: the monitor token never lands in any mirrored file
    blob = open(os.path.join(base, "index.json")).read() + open(os.path.join(base, "runs", "r2.json")).read()
    assert "mtok" not in blob and "token" not in json.dumps(r2)


def test_mirror_drops_a_nodes_smuggled_secret_fields(node_and_mirror, monkeypatch):
    """DEFENSE IN DEPTH: a compromised / MITM'd node returns a secret in extra fields of /monitor/run (top-level
    AND inside an event). The center must ALLOWLIST — none of it may land in the durable mirror."""
    node, mdir = node_and_mirror

    def malicious(url, token=None, timeout=6):
        if "/monitor/run/" in url:
            return {"run_id": url.rsplit("/", 1)[1], "skill": "fs", "perk": "rm", "decision": "allow",
                    "token": "SMUGGLED_SECRET", "vault_key": "ALSO_SECRET", "output": "raw stdout bytes",
                    "events": [{"type": "step_result", "step": "1", "status": "ok", "authority": "exod",
                                "token": "EVENT_SECRET", "value": "leaked"}]}
        return _fake_get(url, token, timeout)

    monkeypatch.setattr(F, "_get", malicious)
    F.mirror_node(node, mdir)
    blob = ""
    runs = os.path.join(mdir, "body-1", "runs")
    for fn in os.listdir(runs):
        blob += open(os.path.join(runs, fn)).read()
    blob += open(os.path.join(mdir, "body-1", "index.json")).read()
    for secret in ("SMUGGLED_SECRET", "ALSO_SECRET", "EVENT_SECRET", "raw stdout bytes", "leaked",
                   '"token"', '"output"', '"vault_key"', '"value"'):
        assert secret not in blob, f"{secret!r} leaked into the central mirror"
    # but the legitimate value-free fields survived (incl. the event's authority)
    r = json.load(open(os.path.join(runs, "r1.json")))
    assert r["events"][0]["authority"] == "exod" and r["decision"] == "allow"


def test_node_name_path_traversal_is_contained(node_and_mirror):
    """A node named with a traversal (operator typo / tampered fleet.json) can never write outside the mirror."""
    node, mdir = node_and_mirror
    evil = dict(node, name="../../../tmp/evil")
    F.mirror_node(evil, mdir)
    # everything the sweep wrote stays under mdir (no escape)
    for root, _dirs, files in os.walk(mdir):
        for f in files:
            assert os.path.realpath(os.path.join(root, f)).startswith(os.path.realpath(mdir) + os.sep)
    assert not os.path.exists("/tmp/evil/runs")              # the traversal did not escape


def test_mirror_is_idempotent_and_never_deletes(node_and_mirror):
    node, mdir = node_and_mirror
    F.mirror_node(node, mdir)
    F.mirror_node(node, mdir)                                 # re-poll
    idx = json.load(open(os.path.join(mdir, "body-1", "index.json")))
    assert set(idx) == {"r1", "r2", "r3"}                    # upsert, not duplicate

    # now the node "loses" r3 (evicted / wiped) — the center must RETAIN it
    monkeypatch_decisions = {1: _DECISIONS[1], 2: []}
    orig = F._get

    def fewer(url, token=None, timeout=6):
        if "/monitor/state" in url:
            return {"now": "t", "decisions": monkeypatch_decisions.get(_page_of(url), []),
                    "decisions_page": {"page": _page_of(url), "pages": 2, "total": 2, "limit": 2}}
        return orig(url, token, timeout)

    import pytest as _p
    with _p.MonkeyPatch.context() as m:
        m.setattr(F, "_get", fewer)
        F.mirror_node(node, mdir)
    idx2 = json.load(open(os.path.join(mdir, "body-1", "index.json")))
    assert "r3" in idx2                                       # the center kept the run the node dropped


def test_inspect_from_center_when_node_is_down(node_and_mirror):
    node, mdir = node_and_mirror
    F.mirror_node(node, mdir)                                 # mirror while up

    def down(url, token=None, timeout=6):
        raise urllib.error.URLError("node offline")

    import pytest as _p
    with _p.MonkeyPatch.context() as m:
        m.setattr(F, "_get", down)
        results, feed = F.fleet_from_mirror([node], mdir)     # node unreachable now
        assert results[0]["reachable"] is False
        assert {x["run_id"] for x in feed} == {"r1", "r2", "r3"}   # still fully inspectable from the mirror
        detail = F.load_run(mdir, "body-1", "r2")
        assert detail["events"][1]["authority"] == "exod"     # per-run detail survives the node being down


def test_risk_classification_and_summary():
    assert F.classify_risk({"decision": "push_back", "destructive": True}) == "approval"
    assert F.classify_risk({"decision": "allow", "destructive": True}) == "high"
    assert F.classify_risk({"decision": "reject", "destructive": False}) == "reject"
    assert F.classify_risk({"decision": "allow", "destructive": False}) is None
    feed = [{"decision": "push_back", "destructive": True}, {"decision": "allow", "destructive": True},
            {"decision": "reject"}, {"decision": "allow"}]
    s = F.risk_summary(feed)
    assert len(s["approval"]) == 1 and len(s["high"]) == 1 and len(s["reject"]) == 1


def test_banner_surfaces_needs_approval(node_and_mirror):
    node, mdir = node_and_mirror
    F.mirror_node(node, mdir)
    _, feed = F.fleet_from_mirror([node], mdir)
    html = F.render_html([{"name": "body-1", "role": "body", "url": "x", "reachable": True,
                           "health": {"runs": 3}, "index": {x["run_id"]: x for x in feed}, "count": 3}],
                         feed, F.risk_summary(feed))
    assert "NEED APPROVAL" in html and "/risk#approval" in html          # the actionable banner is shown
    assert "high-risk ran" in html


def test_rich_record_mirrored_and_still_value_free(node_and_mirror, monkeypatch):
    """The inspection record captures the FULL value-free record (plan, closure pins, approval, model-check,
    provenance, event chain) — but still ALLOWLISTS, so a node can't smuggle a secret in an extra field."""
    rich = {"run_id": "r1", "skill": "fs", "perk": "rm", "decision": "allow", "destructive": True,
            "approved": ["rm", "destructive"], "seq": ["rm_tool"], "plan_sha": "p" * 64,
            "snippet_shas": {"rm.py": "abc123"}, "credential_ids": ["api-key"], "wrapper": "#!/bin/sh\nrm",
            "var_keys": ["DIR"], "problems": [], "tlc": "ok", "tlc_tla": "MODULE X", "tlc_log": "no deadlock",
            "traceparent": "00-trace-span-01", "sources": ["s1"],
            "events": [{"type": "step_result", "step": "1", "status": "ok", "authority": "exod",
                        "exod_keyid": "ed25519:abc", "token": "EVENT_SECRET"}],
            "token": "TOPLEVEL_SECRET", "output": "stdout bytes", "vault": "x"}

    def get(url, token=None, timeout=6):
        if "/monitor/run/" in url:
            return dict(rich)
        return _fake_get(url, token, timeout)

    monkeypatch.setattr(F, "_get", get)
    F.mirror_node(node_and_mirror[0], node_and_mirror[1])
    r1 = json.load(open(os.path.join(node_and_mirror[1], "body-1", "runs", "r1.json")))
    # the rich value-free fields are captured for inspection
    for k in ("approved", "snippet_shas", "credential_ids", "wrapper", "tlc_tla", "tlc_log", "traceparent"):
        assert k in r1, f"{k} missing from the inspection record"
    assert r1["events"][0]["exod_keyid"] == "ed25519:abc"
    # but the smuggled secrets (top-level AND per-event) are dropped
    blob = json.dumps(r1)
    for secret in ("TOPLEVEL_SECRET", "EVENT_SECRET", "stdout bytes", '"token"', '"output"', '"vault"'):
        assert secret not in blob, f"{secret!r} leaked"


def test_flow_svg_is_mirrored_once(node_and_mirror, monkeypatch):
    node, mdir = node_and_mirror
    calls = {"n": 0}

    def fake_raw(url, token=None, timeout=8):
        calls["n"] += 1
        return "image/svg+xml", b'<svg xmlns="http://www.w3.org/2000/svg"></svg>'

    monkeypatch.setattr(F, "_get_raw", fake_raw)
    F.mirror_node(node, mdir)
    svg = F.load_run_svg(mdir, "body-1", "r1")
    assert svg and svg.startswith(b"<svg")
    n1 = calls["n"]
    F.mirror_node(node, mdir)                                 # second sweep must NOT re-fetch existing SVGs
    assert calls["n"] == n1


def test_render_run_has_inspection_sections():
    detail = {"run_id": "r1", "_node": "body-1", "skill": "fs", "perk": "rm", "decision": "allow",
              "destructive": True, "approved": ["rm"], "credential_ids": ["api-key"], "seq": ["rm_tool"],
              "plan_sha": "p" * 40, "snippet_shas": {"rm.py": "sha"}, "var_keys": ["DIR"], "problems": [],
              "tlc": "ok", "traceparent": "00-t-s-01", "wrapper": "#!/bin/sh",
              "events": [{"type": "granted", "step": "1"},
                         {"type": "step_result", "step": "1", "status": "ok", "authority": "exod"}]}
    html = F.render_run("body-1", "r1", detail, has_svg=True)
    for needle in ("ledger — event chain", "plan &amp; closure", "verification", "claim &amp; approval",
                   "/raw/body-1/r1", "/flow/body-1/r1", "/proxy/body-1/trace/r1", "closure file", "exod"):
        assert needle in html, f"inspection section missing: {needle}"


def test_proxy_allowlist_rejects_arbitrary_paths():
    assert F._proxiable("trace/r1") and F._proxiable("intoto/r1") and F._proxiable("flow/run/r1")
    assert F._proxiable("catalog") and F._proxiable("oversight")
    # exact-match boundary: govern, the write/other endpoints, and catalog/oversight LOOKALIKES are NOT proxiable
    for bad in ("govern", "monitor/state", "catalogAdmin", "oversightWrite", "health", "../etc/passwd", "catalog/x"):
        assert not F._proxiable(bad), bad


def test_node_redirect_is_not_followed_so_the_token_cannot_be_exfiltrated():
    # a compromised node could 302 to an attacker host; urllib would otherwise keep the X-Govd-Monitor token.
    # the opener refuses ALL redirects → the token can never leave the configured node.
    assert F._NoRedirect().redirect_request("req", "fp", 302, "msg", {}, "http://attacker.example/steal") is None


def test_embed_serves_trusted_spa_with_a_prefix_and_polling_shim():
    """The iframe gets the TRUSTED repo dashboard (not the node's HTML) with a shim injected BEFORE it that
    prefixes fetches to /embed/<node>/ and emulates EventSource by polling — so no node HTML/JS reaches the
    dashboard origin and no SSE-streaming proxy is needed."""
    html = F._embed_html("body-2", "NONCE123").decode()
    assert "govd_monitor_token" in html                       # it IS the real local-monitor SPA
    assert '"/embed/body-2"' in html and "window.fetch=function" in html   # path-prefix shim
    assert "window.EventSource=function" in html and "/monitor/state" in html  # SSE→polling shim
    # the shim must appear BEFORE the SPA's own "use strict" script so its overrides are in place first
    assert html.index("window.EventSource=function") < html.index('"use strict"')
    # every inline script is nonce-stamped (so a CSP script-src 'nonce-…' runs THESE but blocks injected handlers)
    assert '<script nonce="NONCE123">' in html and "<script>" not in html
    # the shim keys change-detection off the snapshot MINUS the per-second clock (else every idle poll "changes")
    assert "delete o.now" in html
    # the embed carries the dark scrollbar styling
    assert "::-webkit-scrollbar" in html and "scrollbar-color:#30363d" in html


def test_embed_shim_suppresses_clock_only_polls_but_fires_on_real_change():
    """Behavioral: run the SHIPPED shim key() in node against govd-shaped snapshots. Two snapshots that differ
    only in the per-second `now` must collapse to the same key (idle poll → onmessage NOT fired); a genuine change
    (a step advancing) must produce a different key (→ fired). This is the test that would have caught the inert
    first attempt, which diffed the raw text incl. `now` and so re-fired — and re-jumped — every 2.5s."""
    node = shutil.which("node")
    if not node:
        pytest.skip("node not available — behavioral shim test skipped (structural 'delete o.now' still asserted)")
    html = F._embed_html("n", "X").decode()
    m = re.search(r"function key\(t\)\{.*?catch\(e\)\{return t;\}\}", html, re.S)
    assert m, "shim key() not found — the now-stripping change-detector is gone"
    base = {"now": "2026-06-25T00:00:01Z", "runs_live": 2,
            "runs": [{"run_id": "r1", "decision": "allow", "progress": "1/3"}], "totals": {"allow": 5}}
    later_clock = {**base, "now": "2026-06-25T00:00:09Z"}            # only the clock moved → must be suppressed
    real_change = {**later_clock, "runs": [{"run_id": "r1", "decision": "allow", "progress": "2/3"}]}  # → must fire
    script = m.group(0) + (
        ";const k0=key(JSON.stringify(%s)),k1=key(JSON.stringify(%s)),k2=key(JSON.stringify(%s));"
        "if(k0!==k1){console.error('FAIL: clock-only poll not suppressed');process.exit(1);}"
        "if(k1===k2){console.error('FAIL: real change not detected');process.exit(1);}"
        "process.exit(0);"
    ) % (json.dumps(base), json.dumps(later_clock), json.dumps(real_change))
    r = subprocess.run([node, "-e", script], capture_output=True, text=True, timeout=20)
    assert r.returncode == 0, (r.stdout + r.stderr)


def test_dashboard_render_preserves_scroll_on_in_place_refresh():
    """The detail-view page-jump is fixed at its source: the SPA's render() captures the panes' scrollTop before the
    innerHTML rebuild and restores it when the navigation identity (run|tab|page) is unchanged — so an in-place
    refresh keeps scroll while a real navigation still starts the detail pane at the top."""
    spa = (pathlib.Path(F.__file__).resolve().parents[1] / "govern" / "govd_dashboard.html").read_text()
    assert "function viewNav()" in spa and "lastNav" in spa            # the in-place-vs-navigation discriminator
    assert "scrollTop" in spa and "_sameView" in spa                  # capture + conditional restore are present
    # restore is GATED on sameView (navigation must NOT restore the detail pane's old scroll)
    assert "if(_sameView) main.scrollTop" in spa


def test_sanitize_svg_strips_active_content():
    dirty = (b'<svg xmlns="http://www.w3.org/2000/svg" onload="root()"><script>steal()</script>'
             b'<rect onload="x()" onclick="y()" width="1" height="1"/>'
             b'<a xlink:href="javascript:evil()">t</a>'
             b'<image href="JavaScript:bad()"/>'
             b'<foreignObject><body onload="z()"></body></foreignObject></svg>')
    clean = F._sanitize_svg(dirty).lower()
    for bad in (b"<script", b"onload", b"onclick", b"javascript:", b"<foreignobject"):
        assert bad not in clean, bad
    assert b"<rect" in clean and b"<svg" in clean             # the harmless geometry survives


def test_embed_allowlist():
    assert F._embed_proxiable("monitor/state") and F._embed_proxiable("monitor/run/r1") and F._embed_proxiable("flow/run/r1")
    for bad in ("govern", "ledger/r1", "oversight", "catalog", "monitor/stream", "../x", "monitor/statex"):
        assert not F._embed_proxiable(bad), bad


def test_render_node_iframe_live_vs_offline():
    node = {"name": "body-2", "role": "body", "url": "http://x:5773"}
    live = F.render_node_iframe(node, reachable=True)
    assert '<iframe src="/embed/body-2/?token=proxied"' in live and "/mnode/body-2" in live
    off = F.render_node_iframe(node, reachable=False)
    assert "offline" in off and "<iframe" not in off and "/mnode/body-2" in off   # falls back to the mirror board


def test_safe_runid_blocks_path_traversal():
    for evil in ("../../etc/passwd", "..", "a/b\\c", "..\\..\\x", "/abs/path"):
        s = F._safe(evil)
        assert "/" not in s and "\\" not in s and ".." not in s and os.sep not in s
        # the joined mirror path can never escape the runs/ dir
        joined = os.path.realpath(os.path.join("/m/node/runs", s + ".json"))
        assert joined.startswith(os.path.realpath("/m/node/runs") + os.sep)
    assert F._safe("a/b\\c") == "a_b_c"


# ── the hierarchical, searchable side-nav (the home page node nav) ──
_NODES = [
    {"name": "mini", "role": "anchor", "fleet_tier": "mothership", "reachable": True, "health": {"runs": 5}, "count": 12},
    {"name": "edge-1", "role": "body", "fleet_tier": "edge", "reachable": False, "health": {}, "count": 3},
    {"name": "scribe", "role": "body", "fleet_tier": "subagent", "reachable": True, "health": {}, "count": 24},
    {"name": "legacy", "role": "node", "fleet_tier": None, "reachable": None, "health": {}, "count": 0},
]
_FEED = [{"node": "mini", "role": "anchor", "run_id": "r", "ts": "2026-06-29T10:00:00",
          "skill": "fs", "perk": "find", "principal": "mini", "decision": "allow", "authority": "blessed"}]


def test_node_groups_orders_hierarchy_then_untiered_last():
    order = [ft for ft, _ in F._node_groups(_NODES)]
    assert order == ["mothership", "edge", "subagent", None]      # rank 1<2<3, untiered (None) last


def test_sidebar_groups_nodes_by_fleet_tier():
    html = F.render_html(_NODES, _FEED, F.risk_summary(_FEED))
    assert '<aside class="sidebar">' in html and 'class="layout"' in html and 'class="chips"' not in html
    pos = [html.index(f'data-tier="{t}"') for t in ("mothership", "edge", "subagent", "untiered")]
    assert pos == sorted(pos)                                # tiers in hierarchy order, untiered last
    assert 'class="dot up"' in html and 'class="dot down"' in html and 'class="dot stale"' in html
    for n in ("mini", "edge-1", "scribe", "legacy"):
        assert f'/node/{n}"' in html
    assert 'class="main"' in html and "fs/find" in html      # the runs table is still in the main column


def test_sidebar_search_and_collapse_are_client_side_and_persisted():
    html = F.render_html(_NODES, _FEED, F.risk_summary(_FEED))
    assert 'class="navsearch"' in html                       # a filter box
    assert 'data-search="scribe body subagent"' in html      # each node carries a lowercased search haystack
    assert "cw-nav" in html and "localStorage" in html       # state persists like the tz selector (survives refresh)
    assert "navhdr" in html and "collapsed" in html          # per-tier collapse


def test_sidebar_handles_empty_roster():
    html = F.render_html([], [], F.risk_summary([]))
    assert "no nodes in the roster" in html and '<aside class="sidebar">' in html


# ── fleet credit accounting (the accountant pages: fleet + individual) ──
_ACCT_FEED = [
    {"node": "mini", "role": "anchor", "principal": "alice", "skill": "fs", "perk": "find",
     "decision": "allow", "cost": "1.0000", "ts": "2026-06-29T10:00:00", "run_id": "r1", "authority": "blessed"},
    {"node": "mini", "role": "anchor", "principal": "alice", "skill": "fs", "perk": "archive",
     "decision": "allow", "cost": "2.0000", "ts": "2026-06-29T10:01:00", "run_id": "r2", "authority": "blessed"},
    {"node": "edge", "role": "body", "principal": "bob", "skill": "http", "perk": "get",
     "decision": "allow", "cost": "1.0000", "ts": "2026-06-29T10:02:00", "run_id": "r3", "authority": "blessed"},
    {"node": "mini", "role": "anchor", "principal": "alice", "skill": "fs", "perk": "rm",
     "decision": "reject", "cost": None, "ts": "2026-06-29T10:03:00", "run_id": "r4", "authority": "—"},
]


def test_spend_rollup_sums_cost_by_actor_across_fleet():
    by = {r["actor"]: r for r in F._spend_rollup(_ACCT_FEED)}
    assert by["alice"]["spent"] == "3.0000" and by["alice"]["allows"] == 2 and by["alice"]["runs"] == 3
    assert by["bob"]["spent"] == "1.0000" and by["bob"]["nodes"] == 1
    assert F._spend_rollup(_ACCT_FEED)[0]["actor"] == "alice"        # sorted by spend desc


def test_render_accounting_fleet_total_and_per_actor_gauges():
    html = F.render_accounting(_ACCT_FEED)
    assert "fleet accounting" in html and "<b>4.0000</b>" in html    # fleet-wide total spend
    assert html.count('class="gfill"') == 2                          # one gauge bar per actor (a reject adds no actor)
    assert "/principal/alice" in html and "/principal/bob" in html
    assert ">3.0000<" in html                                        # alice's spend (the cost-None reject excluded)


def test_render_principal_individual_account():
    html = F.render_principal("alice", _ACCT_FEED)
    assert "alice — credit account" in html
    assert "spent across the fleet: <b>3.0000</b>" in html
    assert "fs/archive" in html and "fs/rm" in html                  # all of alice's runs (incl. the rejected one)


def test_home_links_to_accounting():
    html = F.render_html([{"name": "n", "role": "node", "reachable": True, "health": {}, "count": 0,
                           "fleet_tier": "edge"}], _ACCT_FEED, F.risk_summary(_ACCT_FEED))
    assert 'href="/accounting"' in html
