#!/usr/bin/env python3
"""infra/tool/fleetdash.py — the FLEET monitor + CENTRAL CONTROL plane: one dashboard over every node's govd,
with a durable central copy of every node's ledgers and a high-risk / needs-approval banner.

Each govd node records, value-free, WHO fired (principal), WHAT (skill/perk), WHEN (ts), the OUTCOME (decision),
and — from the step feed — WHO EXECUTED it (authority=exod on a confined body). fleetdash:

  * MIRRORS each node centrally — it pages every node's /monitor decisions + pulls each run's full detail and
    PERSISTS it under `<mirror-dir>/<node>/` (value-free; the monitor is value-free, the mirror copies metadata
    only). So the center keeps the whole fleet's history even after a node is wiped/redeployed (a fresh node
    volume shows 0 runs, but the center still holds them). The mirror only ever upserts — it never deletes.
  * INSPECTS from the center as if on the local monitor — the board, per-node board, and per-run detail all
    render from the durable mirror, so a run stays inspectable even when its node is down/unreachable. Live
    /health is overlaid for liveness.
  * BANNERS high-risk work — a prominent top banner counts + links runs that NEED APPROVAL (push_back) and
    destructive runs that ran (audit), across the whole fleet, with a /risk drill-down.

Monitor tokens stay server-side (proxied; header X-Govd-Monitor) — never in a browser URL. Read-only; no govd
change; stdlib only.

  python3 -m infra.tool.fleetdash --config fleet.json                 # print the unified table once (also mirrors)
  python3 -m infra.tool.fleetdash --config fleet.json --serve 8787    # live, click-through dashboard + bg mirror

Tokens never sit in argv: each node's monitor token comes from `token_file` (a path) or env
GOVD_MONITOR_TOKEN_<NODENAME>. fleet.json (tailnet/overlay IPs — never public; fill from YOUR fleet):
  {"nodes": [
     {"name": "body-1",   "role": "body",   "url": "http://100.64.0.20:5773", "token_file": "~/.cyberware/monitors/body-1.token"},
     {"name": "anchor-1", "role": "anchor", "url": "http://100.64.0.10:5773", "token_file": "~/.cyberware/monitors/anchor-1.token"}
  ]}
"""
from __future__ import annotations
import argparse, concurrent.futures, html, json, os, threading, time, urllib.error, urllib.parse, urllib.request
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

DEFAULT_MIRROR = "~/.cyberware/fleet-ledgers"      # the central durable copy of every node's value-free ledgers


def _expand(p):
    return os.path.expanduser(os.path.expandvars(p)) if p else p


def _token(node):
    """Monitor token for a node — from token_file (a path) or GOVD_MONITOR_TOKEN_<NAME>. Read, never echoed."""
    if node.get("token"):                                    # inline (discouraged — prefer a file)
        return node["token"]
    f = _expand(node.get("token_file"))
    if f and os.path.isfile(f):
        return open(f).read().strip()
    return os.environ.get("GOVD_MONITOR_TOKEN_" + str(node.get("name", "")).replace("-", "_").upper(), "")


def _get(url, token=None, timeout=6):
    req = urllib.request.Request(url, headers={"X-Govd-Monitor": token} if token else {})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.loads(r.read())


def _node_monitor(node, path):
    """GET a monitor endpoint for one node with its token (server-side — the token never leaves fleetdash)."""
    return _get(node["url"].rstrip("/") + path, token=_token(node))


# ============================ central mirror (durable copy of every node's ledgers) ============================
# DEFENSE IN DEPTH: govd's own monitor is value-free, but the CENTER must not TRUST a (possibly compromised /
# MITM'd) node to be — it persists ONLY these known value-free fields, dropping anything else a node might
# smuggle into a /monitor/run response (a secret, an oversized blob). Mirrors govd's value-free projections.
_RUN_KEYS = ("run_id", "ts", "principal", "skill", "perk", "decision", "destructive",
             "seq", "plan_sha", "var_keys", "problems", "tlc", "restored", "failed", "progress")
_EVENT_KEYS = ("type", "step", "status", "exit", "reason", "span", "authority", "keyid",
               "snippet_shas", "meter", "ts", "traceparent")


def _value_free(detail):
    """Allowlist a node's run detail down to the known value-free fields (top-level AND per-event), so a node
    can never leak a secret into the central mirror by stuffing an extra field into its response."""
    out = {k: detail[k] for k in _RUN_KEYS if k in detail}
    out["events"] = [{k: e[k] for k in _EVENT_KEYS if k in e}
                     for e in detail.get("events", []) if isinstance(e, dict)]
    return out


def _mbase(mirror_dir, name):
    # the node name is joined into the mirror path → _safe() it (an operator typo or a tampered fleet.json
    # naming a node `../../etc` can never escape the mirror dir).
    return os.path.join(_expand(mirror_dir), _safe(name))


def _atomic_write(path, obj):
    """Crash-safe write: a unique tmp + os.replace, so a reader never sees a half-written ledger."""
    tmp = path + f".tmp.{os.getpid()}.{threading.get_ident()}"
    with open(tmp, "w") as f:
        json.dump(obj, f)
    os.replace(tmp, path)


def mirror_node(node, mirror_dir):
    """Pull a node's FULL decision history (paging /monitor/state) + each run's detail (/monitor/run/<id>) and
    PERSIST it under <mirror-dir>/<node>/. Idempotent run_id-keyed upsert — a re-poll refreshes a run's progress
    and NEVER deletes one the node has since evicted/lost, so the center accumulates the whole history. Returns a
    summary {node, mirrored, seen, error?}. Value-free throughout (the monitor is value-free)."""
    name = node.get("name", "?")
    base = _mbase(mirror_dir, name)
    runs_dir = os.path.join(base, "runs")
    os.makedirs(runs_dir, exist_ok=True)
    try:
        health = _get(node["url"].rstrip("/") + "/health")
        _atomic_write(os.path.join(base, "health.json"), health)
    except Exception:
        pass                                                 # a down node keeps its last mirrored health + runs
    tok = _token(node)
    if not tok:
        return {"node": name, "mirrored": 0, "error": "no monitor token"}
    index = _read_json(os.path.join(base, "index.json"), {})
    seen, page, pages, mirrored = set(), 1, 1, 0
    while page <= pages and page <= 200:                     # hard page cap — never loop unbounded
        try:
            snap = _get(node["url"].rstrip("/") + f"/monitor/state?page={page}", token=tok)
        except Exception as e:
            return {"node": name, "mirrored": mirrored, "seen": len(seen),
                    "error": f"{type(e).__name__}{' (bad token?)' if isinstance(e, urllib.error.HTTPError) else ''}"}
        pages = (snap.get("decisions_page") or {}).get("pages", 1) or 1
        for d in snap.get("decisions", []):
            rid = d.get("run_id")
            if not rid or rid in seen:
                continue
            seen.add(rid)
            try:                                             # the full per-run detail (steps + exod authority)
                detail = _get(node["url"].rstrip("/") + "/monitor/run/" + urllib.parse.quote(rid), token=tok)
            except Exception:
                detail = {"run_id": rid}
            if not isinstance(detail, dict) or detail.get("error"):
                detail = {"run_id": rid}
            # carry the decision-feed metadata the run dir may not have (principal/ts/decision/destructive)
            for k in ("skill", "perk", "decision", "destructive", "ts", "principal"):
                detail.setdefault(k, d.get(k))
            detail = _value_free(detail)                      # ALLOWLIST — never trust the node to be value-free
            detail["run_id"], detail["_node"], detail["_mirrored_at"] = rid, name, snap.get("now")
            _atomic_write(os.path.join(runs_dir, _safe(rid) + ".json"), detail)
            index[rid] = {k: detail.get(k) for k in
                          ("run_id", "ts", "principal", "skill", "perk", "decision", "destructive")}
            index[rid]["authority"] = _run_authority(detail)
            mirrored += 1
        page += 1
    _atomic_write(os.path.join(base, "index.json"), index)
    out = {"node": name, "mirrored": mirrored, "seen": len(seen), "total": len(index)}
    if pages > 200:                                           # the page loop is capped — surface a silent truncation
        out["warning"] = f"decision history exceeds the 200-page mirror cap ({pages} pages) — older runs truncated"
    return out


def mirror_all(nodes, mirror_dir):
    """Mirror every node concurrently. Returns the per-node summaries."""
    with concurrent.futures.ThreadPoolExecutor(max_workers=min(8, max(1, len(nodes)))) as ex:
        return list(ex.map(lambda n: _safe_mirror(n, mirror_dir), nodes))


def _safe_mirror(node, mirror_dir):
    try:
        return mirror_node(node, mirror_dir)
    except Exception as e:                                   # one bad node never stops the sweep
        return {"node": node.get("name", "?"), "mirrored": 0, "error": type(e).__name__}


def _safe(rid):
    """A run_id (a hex/url-safe token) → a SINGLE safe filename component: only [A-Za-z0-9_-], so no '/', '\\',
    or '..' can ever escape the per-node runs/ dir (the only thing joined into the central mirror's path)."""
    return "".join(c if (c.isalnum() or c in "-_") else "_" for c in str(rid))[:128] or "_"


def _read_json(path, default):
    try:
        return json.load(open(path))
    except Exception:
        return default


def _run_authority(detail):
    """The limb that signed the run's steps (authority=exod on a confined body), from its step_results."""
    for e in detail.get("events", []):
        if e.get("type") == "step_result" and e.get("authority"):
            return e["authority"]
    return ""


def load_node_mirror(mirror_dir, name):
    """Read a node's persisted copy: {health, index:{run_id:meta}, run(rid)->detail-loader}."""
    base = _mbase(mirror_dir, name)
    return {"health": _read_json(os.path.join(base, "health.json"), None),
            "index": _read_json(os.path.join(base, "index.json"), {})}


def load_run(mirror_dir, name, run_id):
    """A single run's full mirrored detail (durable — inspectable even when the node is down)."""
    return _read_json(os.path.join(_mbase(mirror_dir, name), "runs", _safe(run_id) + ".json"), None)


def fleet_from_mirror(nodes, mirror_dir, live_health=True):
    """Build the dashboard model from the DURABLE mirror (+ a quick live /health overlay for liveness). Returns
    (per-node summaries, one merged who/what/where/when/outcome feed across the whole fleet)."""
    def one(node):
        name = node.get("name", "?")
        m = load_node_mirror(mirror_dir, name)
        health, reachable = m["health"], None
        if live_health:
            try:
                health, reachable = _get(node["url"].rstrip("/") + "/health"), True
            except Exception:
                reachable = False
        return {"name": name, "role": node.get("role", "-"), "url": node["url"].rstrip("/"),
                "reachable": reachable, "health": health, "index": m["index"], "count": len(m["index"])}

    with concurrent.futures.ThreadPoolExecutor(max_workers=min(8, max(1, len(nodes)))) as ex:
        results = list(ex.map(one, nodes))
    merged = []
    for r in results:
        for rid, d in r["index"].items():
            merged.append({"node": r["name"], "role": r["role"], "run_id": rid, **d})
    merged.sort(key=lambda x: x.get("ts") or "", reverse=True)
    return results, merged


# ============================ risk classification (the banner) ============================
def classify_risk(d):
    """The risk class of a run, value-free from its decision + destructive flag:
      'approval' — decision=push_back: a destructive claim AWAITING approval (ACTIONABLE — the operator decides);
      'high'     — destructive AND allowed: an approved destructive op that ran (AUDIT highlight);
      'reject'   — decision=reject: a claim govd refused (flag).
    Everything else is routine (None)."""
    dec = d.get("decision")
    if dec == "push_back":
        return "approval"
    if dec == "reject":
        return "reject"
    if d.get("destructive") and dec == "allow":
        return "high"
    return None


def risk_summary(feed):
    """Counts + the actionable lists across the merged feed: approval (needs decision), high (ran), reject."""
    buckets = {"approval": [], "high": [], "reject": []}
    for x in feed:
        c = classify_risk(x)
        if c:
            buckets[c].append(x)
    return {k: v for k, v in buckets.items()}


# ============================ live one-shot poll (CLI text view; also used when no mirror) ============================
def poll(node):
    name, url = node.get("name", "?"), node["url"].rstrip("/")
    out = {"name": name, "role": node.get("role", "-"), "url": url, "ok": False, "health": None,
           "decisions": [], "feed": []}
    try:
        out["health"] = _get(url + "/health")
    except Exception as e:
        out["error"] = f"unreachable ({type(e).__name__})"
        return out
    tok = _token(node)
    if not tok:
        out["error"] = "no monitor token (set token_file)"
        return out
    try:
        snap = _get(url + "/monitor/state", token=tok)
    except urllib.error.HTTPError as e:
        out["error"] = f"monitor HTTP {e.code} (bad token?)"
        return out
    except Exception as e:
        out["error"] = f"monitor error ({type(e).__name__})"
        return out
    out.update(ok=True, decisions=snap.get("decisions", []), feed=snap.get("feed", []))
    return out


# ---- CLI render ---------------------------------------------------------------------------------
def render_text(results, feed, risk, limit=40):
    lines = ["", "FLEET — nodes:"]
    for r in results:
        h = r.get("health") or {}
        live = "" if r.get("reachable") is None else (" ·live" if r.get("reachable") else " ·OFFLINE")
        st = f"exec_mode={h.get('exec_mode','?')} exod={h.get('exod_attached','?')} runs={h.get('runs','?')}{live}" if h \
            else "\033[31mno data\033[0m"
        lines.append(f"  {r['name']:<18}{r['role']:<8}{r['url']:<30}{st}  [{r.get('count',0)} mirrored]")
    na, hi, rj = (len(risk.get(k, [])) for k in ("approval", "high", "reject"))
    if na or hi or rj:
        lines.append("")
        lines.append(f"  \033[1;31m⚠ {na} NEED APPROVAL\033[0m · \033[33m{hi} high-risk ran\033[0m · {rj} rejected")
    lines.append("")
    lines.append(f"  {'WHEN (UTC)':<22}{'WHERE':<16}{'WHO':<12}{'WHAT':<26}{'EXEC':<8}OUTCOME")
    lines.append("  " + "-" * 96)
    for x in feed[:limit]:
        what = f"{x.get('skill')}/{x.get('perk')}" + ("  ⚠" if x.get("destructive") else "")
        lines.append(f"  {str(x.get('ts'))[:22]:<22}{x['node']:<16}{str(x.get('principal')):<12}{what:<26}"
                     f"{(x.get('authority') or '-'):<8}{x.get('decision')}")
    if not feed:
        lines.append("  (no runs mirrored yet — they appear here as nodes run governed work)")
    return "\n".join(lines) + "\n"


# ---- HTML dashboard (mirror-backed; tokens stay server-side) ----------------------------
_STYLE = """
 body{font:13px ui-monospace,Menlo,monospace;background:#0b0e14;color:#c9d1d9;margin:0;padding:18px}
 a{color:#58a6ff;text-decoration:none} a:hover{text-decoration:underline}
 h1{font-size:15px;color:#58a6ff;margin:0 0 12px} h2{font-size:13px;color:#8b949e;margin:18px 0 8px}
 .muted{color:#6e7681;text-align:center;padding:18px} .back{font-size:12px;color:#6e7681}
 .chips{display:flex;flex-wrap:wrap;gap:10px;margin:8px 0 16px}
 .chip{display:block;background:#161b22;border:1px solid #30363d;border-radius:8px;padding:8px 12px;min-width:170px;color:#c9d1d9}
 .chip.up{border-left:3px solid #2ea043} .chip.down{border-left:3px solid #f85149} .chip.stale{border-left:3px solid #6e7681}
 .chip .role{color:#6e7681;margin-left:6px} .chip .sub{color:#8b949e;margin-top:3px;font-size:11px}
 table{width:100%;border-collapse:collapse} th,td{text-align:left;padding:5px 8px;border-bottom:1px solid #21262d}
 th{color:#6e7681;font-weight:600;text-transform:uppercase;font-size:11px} td.t{color:#8b949e}
 tr.run{cursor:pointer} tr.run:hover td{background:#161b22}
 .ok{color:#3fb950} .no{color:#f85149} .warn{color:#d29922} .role{color:#6e7681}
 .kv{color:#8b949e} .kv b{color:#c9d1d9;font-weight:600} code{color:#79c0ff}
 .banner{display:flex;gap:10px;margin:0 0 14px;flex-wrap:wrap}
 .bn{border-radius:8px;padding:9px 14px;font-weight:600;border:1px solid}
 .bn.approval{background:#3d1418;border-color:#f85149;color:#ffb4ac}
 .bn.high{background:#3a2c0a;border-color:#d29922;color:#e3b341}
 .bn.reject{background:#161b22;border-color:#30363d;color:#8b949e}
 .bn.clear{background:#0f2417;border-color:#2ea043;color:#56d364}
 .pill{display:inline-block;border-radius:6px;padding:1px 7px;font-size:11px;font-weight:600}
 .pill.approval{background:#3d1418;color:#ffb4ac} .pill.high{background:#3a2c0a;color:#e3b341} .pill.reject{background:#21262d;color:#8b949e}
 .off{color:#f85149;font-size:11px} .stalez{color:#6e7681;font-size:11px}
"""


def _esc(s):
    return html.escape(str(s))


def _page(title, content, refresh=None):
    meta = f'<meta http-equiv="refresh" content="{refresh}">' if refresh else ""
    return ('<!doctype html><html><head><meta charset="utf-8">' + meta + "<title>" + _esc(title)
            + "</title><style>" + _STYLE + "</style></head><body>" + content + "</body></html>")


def _banner(risk):
    """The high-risk / needs-approval banner — the first thing the operator sees, fleet-wide."""
    na, hi, rj = (len(risk.get(k, [])) for k in ("approval", "high", "reject"))
    items = []
    if na:
        items.append(f'<a class="bn approval" href="/risk#approval">⚠ {na} NEED APPROVAL</a>')
    if hi:
        items.append(f'<a class="bn high" href="/risk#high">{hi} high-risk ran</a>')
    if rj:
        items.append(f'<a class="bn reject" href="/risk#reject">{rj} rejected</a>')
    if not items:
        items.append('<span class="bn clear">✓ no high-risk or pending-approval work</span>')
    return '<div class="banner">' + "".join(items) + "</div>"


def _risk_pill(d):
    c = classify_risk(d)
    return f'<span class="pill {c}">{c}</span>' if c else ""


def render_html(results, feed, risk, refresh=5):
    chips = []
    for r in results:
        h = r.get("health") or {}
        reach = r.get("reachable")
        cls = "up" if reach else ("down" if reach is False else "stale")
        flag = "" if reach is None else ('' if reach else ' <span class="off">offline</span>')
        sub = (f"{h.get('exec_mode','?')} · exod {h.get('exod_attached','?')} · runs {h.get('runs','?')}"
               if h else '<span class="stalez">no data yet</span>') + flag
        chips.append(f'<a class="chip {cls}" href="/node/{_esc(r["name"])}"><b>{_esc(r["name"])}</b>'
                     f'<span class="role">{_esc(r["role"])}</span> <span class="role">[{r.get("count",0)}]</span>'
                     f'<div class="sub">{sub}</div></a>')
    rows = []
    for x in feed[:300]:
        cls = {"allow": "ok", "reject": "no", "push_back": "warn"}.get(x.get("decision"), "")
        what = _esc(f"{x.get('skill')}/{x.get('perk')}") + (' <span class="warn">⚠</span>' if x.get("destructive") else "")
        rid = _esc(x.get("run_id") or "")
        rows.append(f'<tr class="run" onclick="location=\'/run/{_esc(x["node"])}/{rid}\'">'
                    f'<td class="t">{_esc(str(x.get("ts"))[:19])}</td><td><b>{_esc(x["node"])}</b> '
                    f'<span class="role">{_esc(x["role"])}</span></td><td>{_esc(x.get("principal"))}</td><td>{what}</td>'
                    f'<td>{_esc(x.get("authority") or "—")}</td>'
                    f'<td class="{cls}">{_esc(x.get("decision"))} {_risk_pill(x)}</td></tr>')
    body = "".join(rows) or '<tr><td colspan="6" class="muted">no runs mirrored yet — they appear as nodes run governed work</td></tr>'
    up = sum(1 for r in results if r.get("reachable"))
    content = (f'<h1>cyberware · fleet control — who fired what, where</h1>{_banner(risk)}'
               f'<div class="chips">{"".join(chips)}</div>'
               f'<table><thead><tr><th>when (utc)</th><th>where (node)</th><th>who (principal)</th>'
               f'<th>what (skill/perk)</th><th>exec</th><th>outcome</th></tr></thead><tbody>{body}</tbody></table>'
               f'<p class="muted">click a node or a run for detail · central mirror of {len(feed)} runs · '
               f'{up}/{len(results)} nodes live · auto-refresh {refresh}s</p>')
    return _page("cyberware — fleet control", content, refresh)


def render_risk(feed, risk, refresh=5):
    """The /risk drill-down: every needs-approval / high-risk / rejected run across the fleet, grouped."""
    def section(key, title, hint):
        items = risk.get(key, [])
        rows = "".join(
            f'<tr class="run" onclick="location=\'/run/{_esc(x["node"])}/{_esc(x.get("run_id") or "")}\'">'
            f'<td class="t">{_esc(str(x.get("ts"))[:19])}</td><td><b>{_esc(x["node"])}</b></td>'
            f'<td>{_esc(x.get("principal"))}</td><td>{_esc(x.get("skill"))}/{_esc(x.get("perk"))}</td>'
            f'<td>{_risk_pill(x)}</td></tr>' for x in items)
        rows = rows or '<tr><td colspan="5" class="muted">none</td></tr>'
        return (f'<h2 id="{key}">{title} ({len(items)})</h2><p class="kv">{hint}</p>'
                f'<table><thead><tr><th>when</th><th>where</th><th>who</th><th>what</th><th>risk</th></tr></thead>'
                f'<tbody>{rows}</tbody></table>')
    content = ('<a class="back" href="/">← fleet</a><h1>high-risk &amp; approval queue</h1>'
               + section("approval", "needs approval", "destructive claims govd PUSHED BACK — re-submit the claim with the approval to proceed (govd never auto-approves).")
               + section("high", "high-risk (ran)", "destructive operations that were approved and executed — audit them.")
               + section("reject", "rejected", "claims govd refused (structural problems)."))
    return _page("fleet — risk queue", content, refresh)


def render_node(node, summary, refresh=5):
    """Per-node board, rendered from the node's MIRRORED runs (+ live health overlay)."""
    name = _esc(node.get("name"))
    h = summary.get("health") or {}
    reach = summary.get("reachable")
    runs = sorted(summary.get("index", {}).values(), key=lambda d: d.get("ts") or "", reverse=True)
    rows = []
    for d in runs:
        cls = {"allow": "ok", "reject": "no", "push_back": "warn"}.get(d.get("decision"), "")
        rid = _esc(d.get("run_id") or "")
        rows.append(f'<tr class="run" onclick="location=\'/run/{name}/{rid}\'">'
                    f'<td class="t">{_esc(str(d.get("ts"))[:19])}</td><td>{_esc(d.get("principal","?"))}</td>'
                    f'<td>{_esc(d.get("skill"))}/{_esc(d.get("perk"))}</td>'
                    f'<td>{_esc(d.get("authority") or "—")}</td>'
                    f'<td class="{cls}">{_esc(d.get("decision"))} {_risk_pill(d)}</td></tr>')
    tbody = "".join(rows) or '<tr><td colspan="5" class="muted">no runs mirrored for this node yet</td></tr>'
    livetag = "" if reach is None else ('<span class="ok">live</span>' if reach else '<span class="off">OFFLINE — showing the central mirror</span>')
    content = (f'<a class="back" href="/">← fleet</a><h1>{name} <span class="role">{_esc(node.get("role","-"))}</span> {livetag}</h1>'
               f'<p class="kv">mode <b>{_esc(h.get("mode","?"))}</b> · exec_mode <b>{_esc(h.get("exec_mode","?"))}</b> · '
               f'exod_attached <b>{_esc(h.get("exod_attached","?"))}</b> · runs <b>{_esc(h.get("runs","?"))}</b> · '
               f'chip <code>{_esc((h.get("chip_sha") or "?")[:16])}</code></p>'
               f'<h2>runs ({len(runs)} mirrored)</h2><table><thead><tr><th>when</th><th>who</th>'
               f'<th>what</th><th>exec</th><th>outcome</th></tr></thead><tbody>{tbody}</tbody></table>')
    return _page(f"{node.get('name')} — node board", content, refresh)


def render_run(name, run_id, detail):
    """Per-run detail from the mirror: steps, exod authority, decision, problems, plan hash — local-monitor parity."""
    back = f'<a class="back" href="/node/{_esc(name)}">← {_esc(name)}</a>'
    if not detail:
        return _page("run", back + f'<h1>run {_esc(run_id)}</h1>'
                     '<p class="muted">not in the central mirror (the node may not have run it, or the mirror has not polled it yet)</p>')
    by_step = {e.get("step"): e for e in detail.get("events", []) if e.get("type") == "step_result"}
    granted = {e.get("step") for e in detail.get("events", []) if e.get("type") == "granted"}
    srows = []
    for i, tool in enumerate(detail.get("seq", []), 1):
        e = by_step.get(str(i))
        state = ("ok" if e and e.get("status") == "ok" else "error" if e
                 else "granted" if str(i) in granted else "pending")
        cls = {"ok": "ok", "error": "no", "granted": "warn"}.get(state, "")
        srows.append(f'<tr><td>{i}</td><td>{_esc(tool)}</td><td>{_esc((e or {}).get("authority","—"))}</td>'
                     f'<td class="{cls}">{_esc(state)}</td></tr>')
    steps = "".join(srows) or '<tr><td colspan="4" class="muted">no steps recorded</td></tr>'
    dcls = {"allow": "ok", "reject": "no", "push_back": "warn"}.get(detail.get("decision"), "")
    probs = ", ".join((p.get("id", "?") if isinstance(p, dict) else str(p))
                      for p in detail.get("problems", [])) or "none"
    content = (back + f'<h1>{_esc(detail.get("skill"))}/{_esc(detail.get("perk"))} '
               f'<span class="{dcls}">{_esc(detail.get("decision"))}</span> {_risk_pill(detail)}</h1>'
               f'<p class="kv">where <b>{_esc(detail.get("_node", name))}</b> · who <b>{_esc(detail.get("principal","?"))}</b> · when '
               f'<b>{_esc(str(detail.get("ts"))[:19])}</b> · destructive <b>{_esc(detail.get("destructive",False))}</b> · '
               f'run <code>{_esc(run_id)}</code></p>'
               f'<p class="kv">plan_sha <code>{_esc((detail.get("plan_sha") or "")[:24])}</code> · '
               f'var_keys <b>{_esc(detail.get("var_keys",[]))}</b> · problems <b>{_esc(probs)}</b></p>'
               f'<h2>steps</h2><table><thead><tr><th>#</th><th>tool</th><th>exec (authority)</th>'
               f'<th>state</th></tr></thead><tbody>{steps}</tbody></table>')
    return _page(f"run {run_id}", content)


def load_nodes(path):
    cfg = json.load(open(_expand(path)))
    return cfg["nodes"] if isinstance(cfg, dict) else cfg


def serve(nodes, port, refresh, mirror_dir, mirror_interval):
    by_name = {n.get("name"): n for n in nodes}

    def _mirror_loop():                                      # the durable copy is kept fresh in the background
        while True:
            try:
                mirror_all(nodes, mirror_dir)
            except Exception:
                pass
            time.sleep(max(2, mirror_interval))
    if mirror_dir:
        mirror_all(nodes, mirror_dir)                        # seed once so the first page is populated
        threading.Thread(target=_mirror_loop, name="fleet-mirror", daemon=True).start()

    class H(BaseHTTPRequestHandler):
        def log_message(self, *a):
            pass

        def _send(self, code, page):
            b = page.encode()
            self.send_response(code)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(b)))
            self.end_headers()
            self.wfile.write(b)

        def do_GET(self):
            parts = [urllib.parse.unquote(s) for s in
                     urllib.parse.urlparse(self.path).path.strip("/").split("/") if s]
            try:
                if not parts:                                       # overview (mirror-backed)
                    results, feed = fleet_from_mirror(nodes, mirror_dir)
                    return self._send(200, render_html(results, feed, risk_summary(feed), refresh))
                if parts[0] == "risk":                              # fleet-wide risk / approval queue
                    results, feed = fleet_from_mirror(nodes, mirror_dir)
                    return self._send(200, render_risk(feed, risk_summary(feed), refresh))
                if parts[0] == "node" and len(parts) == 2:          # per-node board (from the mirror)
                    node = by_name.get(parts[1])
                    if not node:
                        return self._send(404, _page("404", '<a class="back" href="/">← fleet</a><p class="muted">unknown node</p>'))
                    results, _ = fleet_from_mirror([node], mirror_dir)
                    return self._send(200, render_node(node, results[0], refresh))
                if parts[0] == "run" and len(parts) == 3:           # per-run detail (durable mirror)
                    node = by_name.get(parts[1])
                    if not node:
                        return self._send(404, _page("404", '<a class="back" href="/">← fleet</a><p class="muted">unknown node</p>'))
                    return self._send(200, render_run(node["name"], parts[2], load_run(mirror_dir, node["name"], parts[2])))
                return self._send(404, _page("404", '<p class="muted">not found</p>'))
            except Exception as e:
                return self._send(500, _page("error", f'<p class="muted">{_esc(e)}</p>'))

    httpd = ThreadingHTTPServer(("127.0.0.1", port), H)
    print(f"fleet control → http://127.0.0.1:{port}  (central mirror → {_expand(mirror_dir) if mirror_dir else 'OFF'} · "
          f"every {mirror_interval}s · {len(nodes)} nodes)")
    httpd.serve_forever()


def main():
    ap = argparse.ArgumentParser(description="cyberware fleet control — central monitor + durable ledger mirror")
    ap.add_argument("--config", required=True, help="fleet.json: {nodes:[{name,role,url,token_file}]}")
    ap.add_argument("--serve", type=int, metavar="PORT", help="serve the live, click-through HTML dashboard on 127.0.0.1:PORT")
    ap.add_argument("--refresh", type=int, default=5, help="dashboard auto-refresh seconds (default 5)")
    ap.add_argument("--mirror-dir", default=DEFAULT_MIRROR, help=f"central durable ledger copy (default {DEFAULT_MIRROR})")
    ap.add_argument("--mirror-interval", type=int, default=10, help="background mirror sweep seconds (default 10)")
    ap.add_argument("--no-mirror", action="store_true", help="do not keep a central copy (live-proxy only)")
    ap.add_argument("--limit", type=int, default=40, help="rows in the text view (default 40)")
    a = ap.parse_args()
    nodes = load_nodes(a.config)
    mirror_dir = None if a.no_mirror else a.mirror_dir
    if a.serve:
        serve(nodes, a.serve, a.refresh, mirror_dir, a.mirror_interval)
    else:
        if mirror_dir:
            mirror_all(nodes, mirror_dir)                   # mirror once, then render the durable view
            results, feed = fleet_from_mirror(nodes, mirror_dir)
        else:
            live = [poll(n) for n in nodes]
            results = [{"name": r["name"], "role": r["role"], "url": r["url"], "reachable": r["ok"],
                        "health": r.get("health"), "index": {}, "count": 0} for r in live]
            feed = []
            for r in live:
                for d in r.get("decisions", []):
                    feed.append({"node": r["name"], "role": r["role"], **d})
            feed.sort(key=lambda x: x.get("ts") or "", reverse=True)
        print(render_text(results, feed, risk_summary(feed), a.limit))


if __name__ == "__main__":
    main()
