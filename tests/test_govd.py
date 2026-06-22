"""Integration: govd.py — the governance control/audit plane.

These pin the model: govd governs a CLAIM (skill, perk, var KEYS) and records STATUS. No values, no
file contents, no secrets, no command output ever cross to govd. It blesses a value-free PLAN and pins
its sha256; destructiveness is gated by the declared perk; the WS is a private per-run session that
monitors the plan hash and records status.
"""
from __future__ import annotations
import json
import os
import socket
import threading
import time
import urllib.error
import urllib.request

import pytest

from infra import registry
from infra.govern import compiler
from infra.govern import govd
from infra.govern import govd_client


@pytest.fixture
def server(tmp_path):
    cfg = govd.load_config()
    cfg["mode"] = "local"
    cfg["local"] = {"host": "127.0.0.1", "ports": [0]}
    cfg["record_root"] = str(tmp_path / "govd_ledger")
    govd.ensure_monitor_token(cfg)                        # local default => "admin"
    store = govd.Store(cfg["record_root"])
    httpd, _ = govd.bind_server("127.0.0.1", [0])
    httpd.daemon_threads = True
    httpd.cfg, httpd.store = cfg, store
    httpd.rate_buckets = {}
    # poll the shutdown flag every 20ms (not the 0.5s default) so the per-test teardown returns promptly —
    # otherwise httpd.shutdown() below waits up to half a second × every test in this file.
    threading.Thread(target=httpd.serve_forever, kwargs={"poll_interval": 0.02}, daemon=True).start()
    base = f"http://127.0.0.1:{httpd.server_address[1]}"
    for _ in range(100):
        try:
            urllib.request.urlopen(base + "/health", timeout=1); break
        except OSError:
            time.sleep(0.02)
    yield base, store, cfg
    httpd.shutdown(); httpd.server_close()


def claim(base, skill, perk, var_keys=(), approve=()):
    body = {"skill": skill, "perk": perk, "var_keys": list(var_keys)}
    if approve:
        body["approve"] = list(approve)
    return govd_client._post_json(base + "/govern", body)


# ── no data crosses the boundary ──

def test_health(server):
    base, _, _ = server
    h = json.loads(urllib.request.urlopen(base + "/health").read())
    assert h["status"] == "ok" and h["service"] == "cyberware-govd"
    assert h["chip_sha"] == json.load(open(registry.manifest_path()))["chip_sha"]   # attests WHICH cartridge


def test_catalog_endpoint_is_ungated_and_matches_the_builder(server):
    base, _, _ = server
    from infra.tool import skill_index
    c = json.loads(urllib.request.urlopen(base + "/catalog").read())   # no token — discovery is ungated
    assert c == skill_index.catalog()                                  # server serves the shared builder verbatim
    fs = next(s for s in c["skills"] if s["skill"] == "fs")
    assert fs["verified"] and {"archive", "find_large"} <= {p["id"] for p in fs["perks"]}


def test_flow_endpoint_serves_the_blueprint_svg(server):
    base, _, _ = server
    r = urllib.request.urlopen(base + "/flow/fs")                  # ungated, value-free registry diagram
    assert r.headers.get("Content-Type") == "image/svg+xml"
    body = r.read().decode()
    assert body.lstrip().startswith("<svg") and "</svg>" in body
    try:
        urllib.request.urlopen(base + "/flow/not_a_skill")         # only exact known skills are served
        assert False, "expected 404 for an unknown skill"
    except urllib.error.HTTPError as e:
        assert e.code == 404


def test_flow_run_serves_value_free_task_blueprint(server):
    base, _, cfg = server
    _, v = claim(base, "fs", "find_large", var_keys=["SEARCH_DIR"])
    rid, tok = v["run_id"], cfg["monitor_token"]
    r = urllib.request.urlopen(base + "/flow/run/" + rid + "?token=" + tok)
    assert r.headers.get("Content-Type") == "image/svg+xml"
    body = r.read().decode()
    assert body.lstrip().startswith("<svg")
    assert "fs_find_large" in body                                 # the perk's ACTUAL tool sequence (task-specific)
    assert "${SEARCH_DIR}" in body                                 # var KEY as a placeholder — value-free
    assert "</svg>" in body
    try:
        urllib.request.urlopen(base + "/flow/run/" + rid)          # monitor-gated like /monitor/run
        assert False, "expected 403 without the monitor token"
    except urllib.error.HTTPError as e:
        assert e.code == 403


def test_discover_tags_verified_unverified_and_drift(server, tmp_path):
    base, _, _ = server
    import shutil
    from infra.tool import skill_index
    # 1) same registry as the server → every local skill is verified, nothing missing
    d = govd_client.discover(base)
    assert set(d["summary"]) == {"verified"} and not d["missing_local"]
    # 2) a divergent local registry: copy the skills, add a NEW one, tamper an existing one
    reg = tmp_path / "reg"
    shutil.copytree(registry.SKILLCHIP, reg)                          # the agent's registry IS a skillChip (source-grouped feed-stock)
    src = reg / "znew" / "perks" / "noop" / "src"
    src.mkdir(parents=True)
    (reg / "znew" / "perks.json").write_text(json.dumps(
        {"skill": "znew", "perks": [{"id": "noop", "summary": "new", "destructive": False, "tools": ["znew_noop"]}]}))
    (src / "contracts.json").write_text(json.dumps({"tool": "znew_noop", "inputs": {"FOO": {"required": True}}}))
    skill_index.write_index("znew", str(reg))
    # the agent PERMITS its own new skill in its local cartridge (re-seed the roster from disk) — govd's
    # manifest still won't have znew, so discover tags it unverified
    skill_index.write_manifest(str(reg), roster=skill_index.scan_skills(str(reg)))
    with open(os.path.join(registry.skill_dir("fs", str(reg)), "SKILL.md"), "a") as f:
        f.write("\n# tampered\n")                                      # files no longer match fs's own index
    d2 = govd_client.discover(base, registry=str(reg))
    by = {s["skill"]: s["status"] for s in d2["skills"]}
    assert by["znew"] == "unverified"     # govd's image has never seen it → not governable
    assert by["fs"] == "drift"            # local copy diverged from the blessed one
    assert d2["summary"].get("unverified") == 1 and d2["summary"].get("drift") == 1


def test_govern_returns_a_value_free_plan(server):
    base, store, _ = server
    code, v = claim(base, "fs", "find_large", var_keys=["SEARCH_DIR"])
    assert code == 200 and v["decision"] == "allow"
    plan = v["plan"]
    assert plan["sequence"] == ["fs_find_large"]
    assert "fs_find_large.sh" in plan["snippet_shas"] and "snippets" not in plan   # hashes only, no code shipped
    assert plan.get("skill_sha")                              # the authenticity anchor from index.json
    assert "${VAR}" not in plan["wrapper"]                    # wrapper is structural, not value-bearing
    assert v["plan_sha"] == compiler.plan_sha(plan)           # agent can recompute the pinned hash
    # the server record holds NO values — only keys + the plan hash
    rec = store.get(v["run_id"])
    assert rec["var_keys"] == ["SEARCH_DIR"] and "vars" not in rec


def test_govern_never_receives_values_even_if_sent(server):
    """Defense: even a client that posts var VALUES gets ledgered by name only — values are ignored."""
    base, store, _ = server
    body = {"skill": "fs", "perk": "find_large", "var_keys": ["SEARCH_DIR"],
            "vars": {"SEARCH_DIR": "/etc/secret-path"}}            # stray values
    _, v = govd_client._post_json(base + "/govern", body)
    rec = store.get(v["run_id"])
    assert "/etc/secret-path" not in json.dumps(rec)              # the value never lands in the ledger


# ── secrets are never plaintext ──

def test_plaintext_secret_key_is_refused(server):
    base, _, _ = server
    code, v = claim(base, "pg_ops", "select", var_keys=["PGHOST", "PGDATABASE", "PGUSER", "QUERY", "PGPASSWORD"])
    assert code == 403 and v["decision"] == "reject"
    assert any(p["id"] == "plaintext_secret_key" for p in v["problems"])
    # the *_FILE pointer form is accepted
    code2, v2 = claim(base, "pg_ops", "select",
                      var_keys=["PGHOST", "PGDATABASE", "PGUSER", "QUERY", "PGPASSWORD_FILE"])
    assert v2["decision"] == "allow"


# ── destructiveness gated by the declared perk, not by payload ──

def test_destructive_perk_pushes_back_until_approved(server):
    base, _, _ = server
    keys = ["PGHOST", "PGDATABASE", "PGUSER", "MIGRATION"]
    code, v = claim(base, "pg_ops", "migrate", var_keys=keys)
    assert code == 409 and v["decision"] == "push_back" and v["needs_approve"] == ["migrate"]
    assert "plan" not in v
    code2, v2 = claim(base, "pg_ops", "migrate", var_keys=keys, approve=["migrate"])
    assert code2 == 200 and v2["decision"] == "allow" and "plan" in v2


def test_govern_runs_the_compose_check_incl_tlc(server):
    base, _, _ = server
    _, v = claim(base, "fs", "find_large", var_keys=["SEARCH_DIR"])
    assert isinstance(v.get("tlc"), str)                       # compose/TLC verdict surfaced (real in container)


def test_tlc_result_is_cached_per_blueprint():
    bp = json.loads(open(registry.skill_dir("fs") + "/blueprint.json").read())
    govd._TLC_CACHE.clear()
    first = govd.tlc_check(bp)
    assert govd.tlc_check(bp) == first and len(govd._TLC_CACHE) == 1   # runs once, then cached
    ok, msg, tla, out = first
    assert "MODULE task" in tla and isinstance(out, str)              # the spec + full log are returned


def test_run_record_persists_tlc_spec_and_log(server):
    """The TLA+ spec + TLC's full output are written into the run record (the mounted ledger), not /tmp."""
    base, store, _ = server
    _, v = claim(base, "fs", "find_large", var_keys=["SEARCH_DIR"])
    rec = store.get(v["run_id"])
    assert "MODULE task" in (rec.get("tlc_tla") or "")               # the spec is persisted per run
    assert "tlc_log" in rec                                          # full output ("" when TLC is skipped locally)


def test_missing_required_input_is_rejected_by_name(server):
    base, _, _ = server
    code, v = claim(base, "pg_ops", "select", var_keys=["PGHOST"])   # QUERY/PGDATABASE/PGUSER missing
    assert v["decision"] == "reject"
    missing = {p["detail"] for p in v["problems"] if p["id"] == "missing_input"}
    assert {"QUERY", "PGDATABASE", "PGUSER"} <= missing


def test_var_key_injection_is_rejected(server):
    base, _, _ = server
    code, v = claim(base, "fs", "find_large", var_keys=["SEARCH_DIR", "Z=1; rm -rf /; A"])
    assert code == 403 and any(p["id"] == "bad_var_key" for p in v["problems"])


# ── the per-step gate: plan hash + grant-bound provenance ──

def test_step_gate_monitors_plan_hash_and_order(server):
    _, store, _ = server
    store.create("r1", {"run_id": "r1", "decision": "allow", "plan_sha": "PSHA", "seq": ["a", "b"],
                        "events": [], "ts": "t", "skill": "x", "perk": "y", "var_keys": []})
    assert govd.authorize_step(store, "r1", "2", "PSHA")[0] is False        # upstream not run
    assert govd.authorize_step(store, "r1", "1", "PSHA")[0] is True
    bad, why = govd.authorize_step(store, "r1", "1", "OTHER")               # inconsistent plan hash
    assert not bad and "inconsistent" in why
    for missing in ("", None):
        assert govd.authorize_step(store, "r1", "1", missing)[0] is False


def test_unsolicited_step_result_is_rejected(server):
    _, store, _ = server
    store.create("r2", {"run_id": "r2", "decision": "allow", "plan_sha": "PSHA", "seq": ["a"],
                        "events": [], "ts": "t", "skill": "x", "perk": "y", "var_keys": []})
    ok, why = govd.result_acceptable(store, "r2", "1", "PSHA")              # no grant yet
    assert not ok and "never granted" in why
    store.append("r2", {"type": "granted", "ts": "t", "step": "1", "plan_sha": "PSHA"})
    assert govd.result_acceptable(store, "r2", "1", "PSHA")[0] is True


# ── bank-session privacy ──

def test_ws_and_ledger_require_the_run_token(server):
    base, _, _ = server
    _, v = claim(base, "fs", "find_large", var_keys=["SEARCH_DIR"])
    rid, tok = v["run_id"], v["session_token"]
    ws_host, ws_port = v["ws"].split("://", 1)[1].split("/", 1)[0].rsplit(":", 1)

    s = govd_client._ws_connect(ws_host, int(ws_port))
    govd_client._ws_send(s, json.dumps({"type": "hello", "run_id": rid, "token": "WRONG"}))
    assert json.loads(govd_client._ws_recv(s))["authorized"] is False
    s.close()

    try:
        urllib.request.urlopen(base + "/ledger/" + rid); assert False
    except urllib.error.HTTPError as e:
        assert e.code == 403
    body = json.loads(urllib.request.urlopen(base + "/ledger/" + rid + "?token=" + tok).read())
    assert body["run_id"] == rid and "token" not in body


def test_run_table_is_bounded():
    import tempfile
    st = govd.Store(tempfile.mkdtemp(), max_runs=3)
    for i in range(5):
        st.create(f"r{i}", {"run_id": f"r{i}", "events": [], "decision": "allow"})
    assert len(st.runs) == 3 and st.get("r0") is None and st.get("r4") is not None


# ── end-to-end: value-free plan, run locally, status-only provenance on the server ──

def test_run_governed_records_status_only(server, tmp_path):
    base, store, _ = server
    sd = tmp_path / "data"; sd.mkdir(); (sd / "f").write_bytes(b"0" * 4096)
    ledger = {"skill": "fs", "perk": "find_large", "record_store": str(tmp_path / "out"),
              "vars": {"SEARCH_DIR": str(sd), "MIN_SIZE": "1c"}}
    out = govd_client.run_governed(base, ledger)
    assert out["decision"] == "allow" and out["results"] and all(r["exit"] == 0 for r in out["results"])
    rec = store.get(out["run_id"])
    sr = [e for e in rec["events"] if e["type"] == "step_result"]
    assert sr and all(e["status"] == "ok" for e in sr)
    assert all("stdout_tail" not in e and "stdout_sha" not in e for e in sr)   # status only, no output
    assert "/data/" not in json.dumps(rec)                                      # no value/path leaked in


def test_run_governed_rejects_an_untracked_file_in_the_agent_registry(server, tmp_path):
    """A sha-matching plan must NOT execute if the agent's own skill dir carries an UNTRACKED extra file: a
    blessed porter could `source` such a planted sibling. The per-snippet hash gate passes (blessed files are
    untouched), so the whole-skill authenticity gate (skill_index.verify) is what must catch it."""
    import shutil
    base, _, _ = server
    reg = tmp_path / "reg"
    shutil.copytree(registry.SKILLCHIP, reg)
    src = os.path.join(registry.skill_dir("fs", str(reg)), "perks", "find_large", "src")
    open(os.path.join(src, "evil.sh"), "w").write("# planted untracked sibling\n")   # not in fs's index.json
    sd = tmp_path / "data"; sd.mkdir(); (sd / "f").write_bytes(b"0" * 4096)
    out = govd_client.run_governed(base, {"skill": "fs", "perk": "find_large",
        "record_store": str(tmp_path / "out"),
        "vars": {"SEARCH_DIR": str(sd), "MIN_SIZE": "1c"}}, registry=str(reg))
    assert "results" not in out and "authenticity failed" in (out.get("error") or "")


def test_dashboard_served_and_monitor_token_gated(server):
    base, _, cfg = server
    html = urllib.request.urlopen(base + "/").read().decode()
    assert "govd" in html and "monitor" in html.lower()
    # the boot-log URL carries ?token=… — the route must serve the dashboard with a query string too
    for path in ("/?token=" + cfg["monitor_token"], "/dashboard", "/dashboard?token=x"):
        r = urllib.request.urlopen(base + path)
        assert r.getcode() == 200 and "text/html" in r.headers.get("Content-Type", "")
    try:
        urllib.request.urlopen(base + "/monitor/state"); assert False, "monitor must require a token"
    except urllib.error.HTTPError as e:
        assert e.code == 403
    snap = json.loads(urllib.request.urlopen(base + "/monitor/state?token=" + cfg["monitor_token"]).read())
    assert {"totals", "runs", "tools", "feed", "decisions"} <= set(snap)


def test_monitor_token_defaults_admin_local_random_remote():
    c = govd.load_config(); c["mode"] = "local"; c["monitor_token"] = None
    assert govd.ensure_monitor_token(c) == "admin"                 # friendly local default
    c2 = govd.load_config(); c2["mode"] = "remote"; c2["monitor_token"] = None
    t = govd.ensure_monitor_token(c2)
    assert t != "admin" and len(t) >= 16                           # remote is never a guessable default


def test_monitor_logs_every_decision(server):
    base, store, _ = server
    claim(base, "fs", "find_large", var_keys=["SEARCH_DIR"])                              # allow
    claim(base, "fs", "find_large", var_keys=["SEARCH_DIR", "BAD KEY"])                   # reject (bad key)
    claim(base, "pg_ops", "migrate", var_keys=["PGHOST", "PGDATABASE", "PGUSER", "MIGRATION"])  # push_back
    decs = {d["decision"] for d in store.monitor_snapshot()["decisions"]}
    assert {"allow", "reject", "push_back"} <= decs


def test_non_allow_verdicts_are_navigable_with_ledger_and_problems(server):
    """push_back/reject land in the in-memory run store too (not only the decisions feed), so the monitor
    can select them and show their submitted ledger + blessed plan + problems."""
    base, store, _ = server
    _, rj = claim(base, "fs", "find_large", var_keys=["SEARCH_DIR", "BAD KEY"])           # reject
    _, pb = claim(base, "pg_ops", "migrate",
                  var_keys=["PGHOST", "PGDATABASE", "PGUSER", "MIGRATION"])               # push_back (destructive)
    assert rj["decision"] == "reject" and pb["decision"] == "push_back"
    rdet, pdet = store.run_detail(rj["run_id"]), store.run_detail(pb["run_id"])
    assert rdet and rdet["decision"] == "reject" and "BAD KEY" in rdet["var_keys"]        # the submitted ledger
    assert any(p.get("id") == "bad_var_key" for p in rdet["problems"])                    # why it was refused
    assert pdet and pdet["decision"] == "push_back" and pdet.get("wrapper")               # plan exists for the Script tab
    nav = {r["decision"] for r in store.monitor_snapshot()["runs"]}
    assert {"reject", "push_back"} <= nav            # in the navigable run list, not only the decisions feed


def test_porter_sources_surfaces_the_blessed_porter():
    """run_detail's Script tab reads the porter source from govd's OWN registry (public chip code)."""
    src = govd.porter_sources("fs", "find_large", ["fs_find_large"])
    assert "fs_find_large.sh" in src and src["fs_find_large.sh"].startswith("#!/usr/bin/env bash")
    assert govd.porter_sources("../evil", "x", ["y"]) == {}      # a bad skill name resolves to nothing, never escapes


def test_non_allow_verdicts_survive_a_restart_in_the_run_list(tmp_path):
    """reject/push_back get no per-run dir, only the durable decisions feed — but a RESTARTED store must
    still surface them in the navigable run list (their submitted ledger + problems), not only the feed."""
    root = str(tmp_path / "led")
    s1 = govd.Store(root)
    s1.create("ar", {"run_id": "ar", "ts": "2026-01-01T00:00:01Z", "skill": "fs", "perk": "find_large",
                     "decision": "allow", "seq": ["fs_find_large"], "events": [], "var_keys": ["SEARCH_DIR"]})
    s1.record_decision({"run_id": "rj", "ts": "2026-01-01T00:00:02Z", "skill": "fs", "perk": "find_large",
                        "decision": "reject", "var_keys": ["BAD KEY"], "problems": ["bad_var_key"]})
    s1.record_decision({"run_id": "pb", "ts": "2026-01-01T00:00:03Z", "skill": "pg_ops", "perk": "migrate",
                        "decision": "push_back", "var_keys": ["PGHOST"], "problems": [], "needs_approve": ["migrate"]})
    s2 = govd.Store(root)                                     # fresh store, same on-disk root (a restart)
    nav = {r["run_id"]: r for r in s2.monitor_snapshot()["runs"]}
    assert {"ar", "rj", "pb"} <= set(nav)                     # ALL three navigable, not just the allow run
    assert nav["rj"]["decision"] == "reject" and nav["pb"]["decision"] == "push_back"
    det = s2.run_detail("rj")                                 # the restored reject carries its ledger + problem
    assert det and "BAD KEY" in det["var_keys"] and any(p.get("id") == "bad_var_key" for p in det["problems"])


def test_run_view_failed_flag_tracks_the_error_state_exactly(tmp_path):
    """The monitor's `failed` flag = an allowed run whose step erred. Pins govd.py's run-view
    classification so the `state == 'error'` comparison can't silently flip (mutation ratchet)."""
    st = govd.Store(str(tmp_path))
    st.create("okrun", {"run_id": "okrun", "ts": "t1", "skill": "s", "perk": "p", "seq": ["a"], "decision": "allow",
                        "events": [{"type": "granted", "step": "1"},
                                   {"type": "step_result", "step": "1", "status": "ok", "exit": 0}]})
    st.create("badrun", {"run_id": "badrun", "ts": "t2", "skill": "s", "perk": "p", "seq": ["a"], "decision": "allow",
                         "events": [{"type": "granted", "step": "1"},
                                    {"type": "step_result", "step": "1", "status": "error", "exit": 1}]})
    views = {r["run_id"]: r for r in st.monitor_snapshot()["runs"]}
    assert views["okrun"]["failed"] is False          # all steps ok -> NOT failed (kills the == -> != mutant)
    assert views["badrun"]["failed"] is True           # an errored step -> failed


def test_monitor_snapshot_is_value_free(server, tmp_path):
    base, store, _ = server
    sd = tmp_path / "d"; sd.mkdir(); (sd / "f").write_bytes(b"0" * 4096)
    govd_client.run_governed(base, {"skill": "fs", "perk": "find_large",
                                    "record_store": str(tmp_path / "o"),
                                    "vars": {"SEARCH_DIR": str(sd), "MIN_SIZE": "1c"}})
    snap = store.monitor_snapshot()
    blob = json.dumps(snap)
    assert "token" not in blob and str(sd) not in blob          # no tokens, no values/paths
    assert "fs_find_large" in snap["tools"]                     # tool usage is tracked
    assert snap["tools"]["fs_find_large"]["ok"] >= 1


def test_store_hydrates_persisted_runs(tmp_path):
    """A restarted server (mounted record_root) reloads prior run ledgers for review."""
    root = str(tmp_path / "led")
    s1 = govd.Store(root)
    s1.create("rh", {"run_id": "rh", "ts": "2026-01-01T00:00:00Z", "skill": "fs", "perk": "find_large",
                     "decision": "allow", "plan_sha": "abc", "seq": ["fs_find_large"], "events": [],
                     "var_keys": ["SEARCH_DIR"]})
    s1.append("rh", {"type": "granted", "ts": "t", "step": "1", "plan_sha": "abc"})
    s2 = govd.Store(root)                                       # fresh store, same on-disk root
    rec = s2.get("rh")
    assert rec is not None and rec.get("restored") is True
    assert any(e["type"] == "granted" for e in rec["events"])
    assert any(d["run_id"] == "rh" for d in s2.decisions)       # decisions feed rebuilt too


def test_record_root_env_override(monkeypatch, tmp_path):
    monkeypatch.setenv("GOVD_RECORD_ROOT", str(tmp_path / "custom"))
    assert govd.load_config()["record_root"] == str(tmp_path / "custom")


def test_run_detail_endpoint(server):
    base, _, cfg = server
    _, v = claim(base, "fs", "find_large", var_keys=["SEARCH_DIR"])
    rid, mt = v["run_id"], cfg["monitor_token"]
    try:
        urllib.request.urlopen(base + "/monitor/run/" + rid); assert False, "must require monitor token"
    except urllib.error.HTTPError as e:
        assert e.code == 403
    d = json.loads(urllib.request.urlopen(base + "/monitor/run/" + rid + "?token=" + mt).read())
    assert d["run_id"] == rid and "token" not in d and d["seq"] == ["fs_find_large"]


def test_favicon_is_served(server):
    """The monitor's favicon is served as a PNG (ungated, like the dashboard HTML)."""
    base, _, _ = server
    r = urllib.request.urlopen(base + "/favicon.png")
    assert r.getcode() == 200 and r.headers.get("Content-Type") == "image/png" and len(r.read()) > 0


def test_price_endpoint_returns_a_value_free_quote(server):
    """GET /price gives an itemized usage quote for a claim BEFORE it runs — ungated, no values, total>0."""
    from decimal import Decimal
    base, _, _ = server
    d = json.loads(urllib.request.urlopen(base + "/price?skill=fs&perk=find_large").read())
    assert d["skill"] == "fs" and d["perk"] == "find_large"
    assert d["mode"] == "structured"                       # default mode (no ?mode= -> structured)
    assert "context_tokens" in d["llm"] and "output_tokens" in d["llm"]
    assert Decimal(d["total"]) > 0 and d["currency"] == "USD"
    f = json.loads(urllib.request.urlopen(base + "/price?skill=fs&perk=find_large&mode=freeform").read())
    assert f["mode"] == "freeform" and f["llm"]["output_tokens"] != d["llm"]["output_tokens"]
    try:
        urllib.request.urlopen(base + "/price?skill=nope&perk=x"); assert False, "unknown skill must 404"
    except urllib.error.HTTPError as e:
        assert e.code == 404


def test_codebaseqc_audit_runs_end_to_end_via_govd(server, sample_repo, tmp_path):
    """Regression: the audit's `.sh` porters exec sibling `.py` cores. The agent now runs from its own
    registry (which has both), verified against the blessed hashes — so it no longer dies with
    'can't open … cbqc_usage.py' (exit 2)."""
    base, store, _ = server
    out = govd_client.run_governed(base, {
        "skill": "codebaseqc", "perk": "audit", "record_store": str(tmp_path / "audit"),
        "vars": {"PROJECT_DIR": str(sample_repo), "SRC_DIR": "src", "TEST_DIR": "tests"}})
    assert out["decision"] == "allow"
    assert out["results"][0]["exit"] == 0 and len(out["results"]) >= 2   # core found; chain advanced past step 1
    oks = [e for e in store.get(out["run_id"])["events"] if e.get("status") == "ok"]
    assert len(oks) >= 1


def test_run_refused_when_local_registry_drifts(server, tmp_path, monkeypatch):
    """The agent refuses to run if its registry doesn't match govd's blessed hashes — no file shipping."""
    base, _, _ = server
    sd = tmp_path / "d"; sd.mkdir(); (sd / "f").write_text("x")
    fake_reg = tmp_path / "reg"                              # an empty 'registry' missing the snippet
    out = govd_client.run_governed(base, {"skill": "fs", "perk": "find_large",
                                          "record_store": str(tmp_path / "o"), "vars": {"SEARCH_DIR": str(sd)}},
                                   registry=str(fake_reg))
    assert "registry mismatch" in out.get("error", "")


def test_port_rotation_skips_occupied():
    busy = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    busy.bind(("127.0.0.1", 0)); busy.listen(1)
    taken = busy.getsockname()[1]
    httpd, port = govd.bind_server("127.0.0.1", [taken, 0])
    try:
        assert httpd is not None and port != taken
    finally:
        if httpd:
            httpd.server_close()
        busy.close()


# ── event-logic gates (added to kill the cws-mutate survivors in ran_ok/steps_seen/monitor_snapshot:
#    the first self-monitored improvement — the platform graded itself and these pin what it found unpinned) ──

def test_ran_ok_counts_only_ok_step_results(tmp_path):
    """ran_ok feeds the upstream gate (a step can't run until predecessors ran ok). Pin BOTH its
    filters — `type == step_result` AND `status == ok` — so neither comparison can be flipped silently."""
    st = govd.Store(str(tmp_path / "s"))
    st.create("r", {"run_id": "r", "events": []})
    st.append("r", {"type": "step_result", "step": "1", "status": "ok"})
    st.append("r", {"type": "step_result", "step": "2", "status": "error"})    # wrong status → excluded
    st.append("r", {"type": "granted", "step": "3"})                            # wrong type → excluded
    st.append("r", {"type": "step_result", "step": "4", "status": "ok"})
    assert st.ran_ok("r") == {"1", "4"}


def test_steps_seen_splits_granted_from_recorded(tmp_path):
    """steps_seen binds a step_result to a prior grant — pin that `granted` and `step_result` are
    classified by their exact event type."""
    st = govd.Store(str(tmp_path / "s"))
    st.create("r", {"run_id": "r", "events": []})
    st.append("r", {"type": "granted", "step": "1"})
    st.append("r", {"type": "granted", "step": "2"})
    st.append("r", {"type": "step_result", "step": "1", "status": "ok"})
    granted, done = st.steps_seen("r")
    assert granted == {"1", "2"} and done == {"1"}


def test_monitor_snapshot_classifies_each_step_state(tmp_path):
    """The dashboard's per-step ok/error/granted/pending classification — pin it so the state
    comparisons (and the granted-set membership) can't be flipped without a test noticing."""
    st = govd.Store(str(tmp_path / "s"))
    st.create("r", {"run_id": "r", "ts": "t", "skill": "sk", "perk": "pk", "seq": ["a", "b", "c", "d"], "events": []})
    st.append("r", {"type": "step_result", "step": "1", "status": "ok"})
    st.append("r", {"type": "step_result", "step": "2", "status": "error"})
    st.append("r", {"type": "granted", "step": "3"})
    snap = st.monitor_snapshot()
    run = next(rv for rv in snap["runs"] if rv["run_id"] == "r")
    assert {s["n"]: s["state"] for s in run["steps"]} == {1: "ok", 2: "error", 3: "granted", 4: "pending"}
    assert snap["tools"]["a"]["ok"] == 1
    assert snap["tools"]["b"]["error"] == 1
    assert snap["tools"]["c"]["granted"] == 1


# ── P1-T08: principal Bearer auth + token-bucket rate-limit at /govern ──
def _auth_server(tmp_path, reg):
    cfg = govd.load_config()
    cfg["mode"] = "local"
    cfg["local"] = {"host": "127.0.0.1", "ports": [0]}
    cfg["record_root"] = str(tmp_path / "govd_auth")
    govd.ensure_monitor_token(cfg)
    cfg["principals"] = reg
    store = govd.Store(cfg["record_root"])
    httpd, _ = govd.bind_server("127.0.0.1", [0])
    httpd.daemon_threads = True
    httpd.cfg, httpd.store = cfg, store
    httpd.rate_buckets = {}
    threading.Thread(target=httpd.serve_forever, kwargs={"poll_interval": 0.02}, daemon=True).start()
    base = f"http://127.0.0.1:{httpd.server_address[1]}"
    for _ in range(100):
        try:
            urllib.request.urlopen(base + "/health", timeout=1); break
        except OSError:
            time.sleep(0.02)
    return base, store, httpd


def _post(base, body, headers=None):
    req = urllib.request.Request(base + "/govern", data=json.dumps(body).encode(),
                                 headers=headers or {}, method="POST")
    try:
        r = urllib.request.urlopen(req, timeout=5)
        return r.status, json.loads(r.read())
    except urllib.error.HTTPError as e:
        return e.code, None


def test_govern_bearer_auth_principal_and_rate_limit(tmp_path):
    from infra.govern import principals
    reg = {"agent-a": {"token_sha": principals.token_sha("secret-A"), "rate": 1.0, "burst": 3}}
    base, store, httpd = _auth_server(tmp_path, reg)
    body = {"skill": "cws-conform", "perk": "schemas", "var_keys": []}
    try:
        assert _post(base, body)[0] == 401                                   # no token -> 401
        assert _post(base, body, {"Authorization": "Bearer nope"})[0] == 401  # wrong token -> 401
        assert _post(base, body, {"Authorization": "token=secret-A"})[0] == 401  # query-style -> 401 (Bearer only)
        code, v = _post(base, body, {"Authorization": "Bearer secret-A"})     # valid -> allow
        assert code == 200 and v["decision"] == "allow"
        # the persisted record carries the principal (every_record_carries_principal)
        led = json.loads(urllib.request.urlopen(
            base + "/ledger/" + v["run_id"] + "?token=" + v["session_token"]).read())
        assert led["principal"] == "agent-a"
        # burst then 429 (burst=3; one token already spent on the allowed call above)
        codes = [_post(base, body, {"Authorization": "Bearer secret-A"})[0] for _ in range(4)]
        assert 429 in codes
    finally:
        httpd.shutdown(); httpd.server_close()


# ── P5-T02: SSE push + paginated decisions feed ──────────────────────────────────────────────────────

def _fill_decisions(store, n):
    for i in range(n):
        store.decisions.append({"ts": f"2026-06-22T00:{i // 60:02d}:{i % 60:02d}Z", "run_id": f"r{i}",
                                "decision": "allow", "skill": "fs", "perk": "read", "destructive": False})


def test_monitor_state_paginates_decisions(server):
    base, store, _ = server
    _fill_decisions(store, 250)                                    # more than one page
    p1 = json.loads(urllib.request.urlopen(base + "/monitor/state?token=admin&dec_limit=50").read())
    assert len(p1["decisions"]) == 50                              # one page, not all 250
    assert p1["decisions_page"] == {"page": 1, "pages": 5, "total": 250, "limit": 50}
    assert p1["decisions"][0]["run_id"] == "r249"                  # newest first
    p2 = json.loads(urllib.request.urlopen(base + "/monitor/state?token=admin&dec_page=2&dec_limit=50").read())
    assert p2["decisions_page"]["page"] == 2
    assert p2["decisions"][0]["run_id"] == "r199"                  # the next-older window — no overlap with page 1
    # out-of-range / bad params clamp rather than error (feed.paginate)
    over = json.loads(urllib.request.urlopen(base + "/monitor/state?token=admin&dec_page=99&dec_limit=50").read())
    assert over["decisions_page"]["page"] == 5
    bad = json.loads(urllib.request.urlopen(base + "/monitor/state?token=admin&dec_page=x").read())
    assert bad["decisions_page"]["page"] == 1                      # non-int -> default, never a 500


def test_monitor_state_pagination_is_token_gated(server):
    base, _, _ = server
    with pytest.raises(urllib.error.HTTPError) as e:
        urllib.request.urlopen(base + "/monitor/state?dec_page=2")   # no token
    assert e.value.code == 403


def test_monitor_stream_pushes_sse_and_is_token_gated(server):
    base, store, _ = server
    _fill_decisions(store, 3)
    r = urllib.request.urlopen(base + "/monitor/stream?token=admin", timeout=5)
    assert r.headers.get("Content-Type") == "text/event-stream"
    r.fp.raw._sock.settimeout(4)                                   # bound the streaming read
    buf = b""
    while len(buf) < 65536:                                        # read until a COMPLETE data frame arrives
        chunk = r.read(256)
        if not chunk:
            break
        buf += chunk
        if b"data: " in buf and b"\n\n" in buf.split(b"data: ", 1)[1]:
            break
    r.close()
    txt = buf.decode(errors="replace")
    assert "retry: 2000" in txt                                   # client auto-reconnect backoff is advertised
    assert "data: " in txt                                        # a value-free snapshot was PUSHED
    payload = json.loads(txt.split("data: ", 1)[1].split("\n\n", 1)[0])
    assert "decisions" in payload and "token" not in json.dumps(payload)   # value-free, no session token


def test_monitor_stream_requires_token(server):
    base, _, _ = server
    with pytest.raises(urllib.error.HTTPError) as e:
        urllib.request.urlopen(base + "/monitor/stream")
    assert e.value.code == 403
