#!/usr/bin/env python3
"""infra/tool/fleetdash.py — the FLEET monitor: ONE dashboard wrapping every node's govd /monitor into a
single who-fired-what-WHERE view across the workforce, with drill-down.

Each govd node already records, value-free, WHO fired (principal), WHAT (skill/perk), WHEN (ts), the OUTCOME
(decision), and — from the step feed — WHO EXECUTED it (authority=exod on a confined body). fleetdash polls
every node's /monitor/state (monitor-token-gated, header X-Govd-Monitor), tags each record with the node
(the missing WHERE), and merges them into one time-sorted feed. Click a node → its own board; click a run →
its steps + exod authority + problems. Detail is PROXIED server-side, so the monitor tokens never leave
fleetdash (never land in a browser URL). Read-only; no govd change; stdlib only.

  python3 -m infra.tool.fleetdash --config fleet.json            # print the unified table once
  python3 -m infra.tool.fleetdash --config fleet.json --serve 8787   # serve the live, click-through dashboard

Tokens never sit in argv: each node's monitor token comes from `token_file` (a path) or env
GOVD_MONITOR_TOKEN_<NODENAME>. fleet.json:
  {"nodes": [
     {"name": "dgx-spark",        "role": "body",   "url": "http://100.125.82.27:5773", "token_file": "~/.cyberware/monitors/dgx-spark.token"},
     {"name": "cyberware-runner", "role": "anchor", "url": "http://100.87.213.98:5773",  "token_file": "~/.cyberware/monitors/runner.token"}
  ]}
"""
from __future__ import annotations
import argparse, concurrent.futures, html, json, os, urllib.error, urllib.request
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer


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


def poll(node):
    """Poll one node: /health (liveness + mode) then /monitor/state (the value-free decision + step feeds)."""
    name, url = node.get("name", "?"), node["url"].rstrip("/")
    out = {"name": name, "role": node.get("role", "-"), "url": url, "ok": False,
           "health": None, "decisions": [], "runs": [], "feed": [], "totals": {}}
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
    out.update(ok=True, decisions=snap.get("decisions", []), runs=snap.get("runs", []),
               feed=snap.get("feed", []), totals=snap.get("totals", {}))
    return out


def aggregate(nodes):
    """Poll every node concurrently → (per-node summaries, one merged who/what/where/when/outcome feed)."""
    with concurrent.futures.ThreadPoolExecutor(max_workers=min(8, max(1, len(nodes)))) as ex:
        results = list(ex.map(poll, nodes))
    merged = []
    for r in results:
        authority = {}                                       # run_id -> the limb that signed the step (exod)
        for e in r.get("feed", []):
            if e.get("type") == "step_result" and e.get("authority"):
                authority.setdefault(e.get("run_id"), e["authority"])
        for d in r.get("decisions", []):
            merged.append({"node": r["name"], "role": r["role"], "ts": d.get("ts"),
                           "principal": d.get("principal", "?"), "skill": d.get("skill"),
                           "perk": d.get("perk"), "decision": d.get("decision"),
                           "destructive": d.get("destructive", False),
                           "authority": authority.get(d.get("run_id"), ""),
                           "run_id": d.get("run_id")})
    merged.sort(key=lambda x: x.get("ts") or "", reverse=True)
    return results, merged


# ---- CLI render ---------------------------------------------------------------------------------
def render_text(results, feed, limit=40):
    lines = ["", "FLEET — nodes:"]
    for r in results:
        h = r.get("health") or {}
        st = (f"exec_mode={h.get('exec_mode','?')} exod={h.get('exod_attached','?')} runs={h.get('runs','?')}"
              if r["ok"] else f"\033[31m{r.get('error','down')}\033[0m")
        lines.append(f"  {r['name']:<18}{r['role']:<8}{r['url']:<30}{st}")
    lines.append("")
    lines.append(f"  {'WHEN (UTC)':<22}{'WHERE':<16}{'WHO':<12}{'WHAT':<26}{'EXEC':<8}OUTCOME")
    lines.append("  " + "-" * 96)
    for x in feed[:limit]:
        what = f"{x['skill']}/{x['perk']}" + ("  ⚠" if x["destructive"] else "")
        lines.append(f"  {str(x['ts'])[:22]:<22}{x['node']:<16}{str(x['principal']):<12}{what:<26}"
                     f"{(x['authority'] or '-'):<8}{x['decision']}")
    if not feed:
        lines.append("  (no runs recorded on any node yet)")
    return "\n".join(lines) + "\n"


# ---- HTML dashboard (overview + drill-down; tokens stay server-side) ----------------------------
_STYLE = """
 body{font:13px ui-monospace,Menlo,monospace;background:#0b0e14;color:#c9d1d9;margin:0;padding:18px}
 a{color:#58a6ff;text-decoration:none} a:hover{text-decoration:underline}
 h1{font-size:15px;color:#58a6ff;margin:0 0 12px} h2{font-size:13px;color:#8b949e;margin:18px 0 8px}
 .muted{color:#6e7681;text-align:center;padding:18px} .back{font-size:12px;color:#6e7681}
 .chips{display:flex;flex-wrap:wrap;gap:10px;margin:8px 0 16px}
 .chip{display:block;background:#161b22;border:1px solid #30363d;border-radius:8px;padding:8px 12px;min-width:170px;color:#c9d1d9}
 .chip.up{border-left:3px solid #2ea043} .chip.down{border-left:3px solid #f85149}
 .chip .role{color:#6e7681;margin-left:6px} .chip .sub{color:#8b949e;margin-top:3px;font-size:11px}
 table{width:100%;border-collapse:collapse} th,td{text-align:left;padding:5px 8px;border-bottom:1px solid #21262d}
 th{color:#6e7681;font-weight:600;text-transform:uppercase;font-size:11px} td.t{color:#8b949e}
 tr.run{cursor:pointer} tr.run:hover td{background:#161b22}
 .ok{color:#3fb950} .no{color:#f85149} .warn{color:#d29922} .role{color:#6e7681}
 .kv{color:#8b949e} .kv b{color:#c9d1d9;font-weight:600} code{color:#79c0ff}
"""


def _esc(s):
    return html.escape(str(s))


def _page(title, content, refresh=None):
    meta = f'<meta http-equiv="refresh" content="{refresh}">' if refresh else ""
    return ('<!doctype html><html><head><meta charset="utf-8">' + meta + "<title>" + _esc(title)
            + "</title><style>" + _STYLE + "</style></head><body>" + content + "</body></html>")


def render_html(results, feed, refresh=5):
    chips = []
    for r in results:
        h, up = r.get("health") or {}, r["ok"]
        sub = (f"{h.get('exec_mode','?')} · exod {h.get('exod_attached','?')} · runs {h.get('runs','?')}"
               if up else _esc(r.get("error", "down")))
        chips.append(f'<a class="chip {"up" if up else "down"}" href="/node/{_esc(r["name"])}"><b>{_esc(r["name"])}</b>'
                     f'<span class="role">{_esc(r["role"])}</span><div class="sub">{sub}</div></a>')
    rows = []
    for x in feed[:200]:
        cls = {"allow": "ok", "reject": "no", "push_back": "warn"}.get(x["decision"], "")
        what = _esc(f"{x['skill']}/{x['perk']}") + (' <span class="warn">⚠</span>' if x["destructive"] else "")
        rid = _esc(x.get("run_id") or "")
        rows.append(f'<tr class="run" onclick="location=\'/run/{_esc(x["node"])}/{rid}\'">'
                    f'<td class="t">{_esc(str(x["ts"])[:19])}</td><td><b>{_esc(x["node"])}</b> '
                    f'<span class="role">{_esc(x["role"])}</span></td><td>{_esc(x["principal"])}</td><td>{what}</td>'
                    f'<td>{_esc(x["authority"] or "—")}</td><td class="{cls}">{_esc(x["decision"])}</td></tr>')
    body = "".join(rows) or '<tr><td colspan="6" class="muted">no runs recorded on any node yet</td></tr>'
    up = sum(1 for r in results if r["ok"])
    content = (f'<h1>cyberware · fleet monitor — who fired what, where</h1><div class="chips">{"".join(chips)}</div>'
               f'<table><thead><tr><th>when (utc)</th><th>where (node)</th><th>who (principal)</th>'
               f'<th>what (skill/perk)</th><th>exec</th><th>outcome</th></tr></thead><tbody>{body}</tbody></table>'
               f'<p class="muted">click a node or a run row for detail · auto-refresh {refresh}s · '
               f'{len(feed)} records across {up}/{len(results)} nodes</p>')
    return _page("cyberware — fleet monitor", content, refresh)


def render_node(node, snap, health, refresh=5):
    """Per-node board: that node's own runs/decisions/health, rendered by fleetdash from /monitor/state."""
    name = _esc(node.get("name"))
    h = health or {}
    authority = {}
    for e in snap.get("feed", []):
        if e.get("type") == "step_result" and e.get("authority"):
            authority.setdefault(e.get("run_id"), e["authority"])
    rows = []
    for d in snap.get("decisions", []):
        cls = {"allow": "ok", "reject": "no", "push_back": "warn"}.get(d.get("decision"), "")
        rid = _esc(d.get("run_id") or "")
        rows.append(f'<tr class="run" onclick="location=\'/run/{name}/{rid}\'">'
                    f'<td class="t">{_esc(str(d.get("ts"))[:19])}</td><td>{_esc(d.get("principal","?"))}</td>'
                    f'<td>{_esc(d.get("skill"))}/{_esc(d.get("perk"))}</td>'
                    f'<td>{_esc(authority.get(d.get("run_id"), "—"))}</td>'
                    f'<td class="{cls}">{_esc(d.get("decision"))}</td></tr>')
    tbody = "".join(rows) or '<tr><td colspan="5" class="muted">no runs on this node yet</td></tr>'
    tools = snap.get("tools", {})
    trows = "".join(f'<tr><td>{_esc(t)}</td><td class="ok">{v.get("ok",0)}</td>'
                    f'<td class="no">{v.get("error",0)}</td><td class="role">{v.get("granted",0)}</td></tr>'
                    for t, v in sorted(tools.items()))
    content = (f'<a class="back" href="/">← fleet</a><h1>{name} <span class="role">{_esc(node.get("role","-"))}</span></h1>'
               f'<p class="kv">mode <b>{_esc(h.get("mode","?"))}</b> · exec_mode <b>{_esc(h.get("exec_mode","?"))}</b> · '
               f'exod_attached <b>{_esc(h.get("exod_attached","?"))}</b> · runs <b>{_esc(h.get("runs","?"))}</b> · '
               f'chip <code>{_esc((h.get("chip_sha") or "?")[:16])}</code></p>'
               f'<h2>runs ({len(snap.get("decisions",[]))})</h2><table><thead><tr><th>when</th><th>who</th>'
               f'<th>what</th><th>exec</th><th>outcome</th></tr></thead><tbody>{tbody}</tbody></table>'
               + (f'<h2>tool usage</h2><table><thead><tr><th>tool</th><th>ok</th><th>error</th><th>granted</th>'
                  f'</tr></thead><tbody>{trows}</tbody></table>' if tools else ""))
    return _page(f"{node.get('name')} — node board", content, refresh)


def render_run(name, run_id, detail):
    """Per-run detail: the steps, the exod authority, decision, problems, plan hash."""
    back = f'<a class="back" href="/node/{_esc(name)}">← {_esc(name)}</a>'
    if not detail or detail.get("error"):
        return _page("run", back + f'<h1>run {_esc(run_id)}</h1>'
                     f'<p class="muted">{_esc((detail or {}).get("error", "not found"))}</p>')
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
    steps = "".join(srows) or '<tr><td colspan="4" class="muted">no steps</td></tr>'
    dcls = {"allow": "ok", "reject": "no", "push_back": "warn"}.get(detail.get("decision"), "")
    probs = ", ".join((p.get("id", "?") if isinstance(p, dict) else str(p))
                      for p in detail.get("problems", [])) or "none"
    content = (back + f'<h1>{_esc(detail.get("skill"))}/{_esc(detail.get("perk"))} '
               f'<span class="{dcls}">{_esc(detail.get("decision"))}</span></h1>'
               f'<p class="kv">who <b>{_esc(detail.get("principal","?"))}</b> · when '
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


def serve(nodes, port, refresh):
    by_name = {n.get("name"): n for n in nodes}

    class H(BaseHTTPRequestHandler):
        def log_message(self, *a):  # quiet
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
                if not parts:                                       # overview
                    results, feed = aggregate(nodes)
                    return self._send(200, render_html(results, feed, refresh))
                if parts[0] == "node" and len(parts) == 2:          # per-node board
                    node = by_name.get(parts[1])
                    if not node:
                        return self._send(404, _page("404", '<a class="back" href="/">← fleet</a><p class="muted">unknown node</p>'))
                    try:
                        snap = _node_monitor(node, "/monitor/state")
                        health = _get(node["url"].rstrip("/") + "/health")
                    except Exception as e:
                        return self._send(200, _page("node", f'<a class="back" href="/">← fleet</a>'
                                          f'<p class="muted">{_esc(node["name"])}: {_esc(type(e).__name__)}</p>'))
                    return self._send(200, render_node(node, snap, health, refresh))
                if parts[0] == "run" and len(parts) == 3:           # per-run detail
                    node = by_name.get(parts[1])
                    if not node:
                        return self._send(404, _page("404", '<a class="back" href="/">← fleet</a><p class="muted">unknown node</p>'))
                    try:
                        detail = _node_monitor(node, "/monitor/run/" + urllib.parse.quote(parts[2]))
                    except Exception as e:
                        detail = {"error": type(e).__name__}
                    return self._send(200, render_run(node["name"], parts[2], detail))
                return self._send(404, _page("404", '<p class="muted">not found</p>'))
            except Exception as e:
                return self._send(500, _page("error", f'<p class="muted">{_esc(e)}</p>'))

    httpd = ThreadingHTTPServer(("127.0.0.1", port), H)
    print(f"fleet monitor → http://127.0.0.1:{port}  (click a node / run to drill down · polling {len(nodes)} nodes)")
    httpd.serve_forever()


def main():
    ap = argparse.ArgumentParser(description="cyberware fleet monitor — one dashboard over every node's govd")
    ap.add_argument("--config", required=True, help="fleet.json: {nodes:[{name,role,url,token_file}]}")
    ap.add_argument("--serve", type=int, metavar="PORT", help="serve the live, click-through HTML dashboard on 127.0.0.1:PORT")
    ap.add_argument("--refresh", type=int, default=5, help="dashboard auto-refresh seconds (default 5)")
    ap.add_argument("--limit", type=int, default=40, help="rows in the text view (default 40)")
    a = ap.parse_args()
    nodes = load_nodes(a.config)
    if a.serve:
        serve(nodes, a.serve, a.refresh)
    else:
        results, feed = aggregate(nodes)
        print(render_text(results, feed, a.limit))


if __name__ == "__main__":
    main()
