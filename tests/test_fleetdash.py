"""fleetdash — the fleet CENTRAL CONTROL plane: a durable mirror of every node's value-free ledgers, inspectable
from the center even when a node is down, with a high-risk/approval banner. Hermetic — the govd HTTP layer is
faked, so no live node is needed."""
from __future__ import annotations

import json
import os
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


def test_safe_runid_blocks_path_traversal():
    for evil in ("../../etc/passwd", "..", "a/b\\c", "..\\..\\x", "/abs/path"):
        s = F._safe(evil)
        assert "/" not in s and "\\" not in s and ".." not in s and os.sep not in s
        # the joined mirror path can never escape the runs/ dir
        joined = os.path.realpath(os.path.join("/m/node/runs", s + ".json"))
        assert joined.startswith(os.path.realpath("/m/node/runs") + os.sep)
    assert F._safe("a/b\\c") == "a_b_c"
