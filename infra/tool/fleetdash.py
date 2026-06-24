#!/usr/bin/env python3
"""infra/tool/fleetdash.py — the FLEET monitor: ONE dashboard wrapping every node's govd /monitor into a
single who-fired-what-WHERE view across the workforce.

Each govd node already records, value-free, WHO fired (principal), WHAT (skill/perk), WHEN (ts), the OUTCOME
(decision), and — from the step feed — WHO EXECUTED it (authority=exod on a confined body). fleetdash polls
every node's /monitor/state (monitor-token-gated, header X-Govd-Monitor), tags each record with the node
(the missing WHERE), and merges them into one time-sorted feed. Read-only; no govd change; stdlib only.

  python3 -m infra.tool.fleetdash --config fleet.json            # print the unified table once
  python3 -m infra.tool.fleetdash --config fleet.json --serve 8787   # serve the live HTML dashboard

Tokens never sit in argv: each node's monitor token comes from `token_file` (a path) or the env var
GOVD_MONITOR_TOKEN_<NODENAME>. fleet.json:
  {"nodes": [
     {"name": "body-1",        "role": "body",   "url": "http://100.64.0.21:5773", "token_file": "~/.cyberware/monitors/body-1.token"},
     {"name": "runner-1", "role": "anchor", "url": "http://100.64.0.24:5773",  "token_file": "~/.cyberware/monitors/runner.token"}
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
        # WHO EXECUTED: map run_id -> the limb that signed the step (authority=exod on a confined body)
        authority = {}
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


# ---- HTML dashboard -----------------------------------------------------------------------------
def render_html(results, feed, refresh=5):
    def esc(s): return html.escape(str(s))
    chips = []
    for r in results:
        h = r.get("health") or {}
        up = r["ok"]
        sub = (f"{h.get('exec_mode','?')} · exod {h.get('exod_attached','?')} · runs {h.get('runs','?')}"
               if up else esc(r.get("error", "down")))
        chips.append(f'<div class="chip {"up" if up else "down"}"><b>{esc(r["name"])}</b>'
                     f'<span class="role">{esc(r["role"])}</span><div class="sub">{sub}</div></div>')
    rows = []
    for x in feed[:200]:
        cls = {"allow": "ok", "reject": "no", "push_back": "warn"}.get(x["decision"], "")
        what = esc(f"{x['skill']}/{x['perk']}") + (' <span class="warn">⚠</span>' if x["destructive"] else "")
        rows.append(
            f'<tr><td class="t">{esc(str(x["ts"])[:19])}</td><td><b>{esc(x["node"])}</b> '
            f'<span class="role">{esc(x["role"])}</span></td><td>{esc(x["principal"])}</td><td>{what}</td>'
            f'<td>{esc(x["authority"] or "—")}</td><td class="{cls}">{esc(x["decision"])}</td></tr>')
    body = "".join(rows) or '<tr><td colspan="6" class="muted">no runs recorded on any node yet</td></tr>'
    return f"""<!doctype html><html><head><meta charset="utf-8"><meta http-equiv="refresh" content="{refresh}">
<title>cyberware — fleet monitor</title><style>
 body{{font:13px ui-monospace,Menlo,monospace;background:#0b0e14;color:#c9d1d9;margin:0;padding:18px}}
 h1{{font-size:15px;color:#58a6ff;margin:0 0 12px}} .muted{{color:#6e7681;text-align:center;padding:18px}}
 .chips{{display:flex;flex-wrap:wrap;gap:10px;margin-bottom:16px}}
 .chip{{background:#161b22;border:1px solid #30363d;border-radius:8px;padding:8px 12px;min-width:170px}}
 .chip.up{{border-left:3px solid #2ea043}} .chip.down{{border-left:3px solid #f85149}}
 .chip .role{{color:#6e7681;margin-left:6px}} .chip .sub{{color:#8b949e;margin-top:3px;font-size:11px}}
 table{{width:100%;border-collapse:collapse}} th,td{{text-align:left;padding:5px 8px;border-bottom:1px solid #21262d}}
 th{{color:#6e7681;font-weight:600;text-transform:uppercase;font-size:11px}} td.t{{color:#8b949e}}
 .ok{{color:#3fb950}} .no{{color:#f85149}} .warn{{color:#d29922}} .role{{color:#6e7681}}
</style></head><body>
<h1>cyberware · fleet monitor — who fired what, where</h1>
<div class="chips">{''.join(chips)}</div>
<table><thead><tr><th>when (utc)</th><th>where (node)</th><th>who (principal)</th><th>what (skill/perk)</th>
<th>exec</th><th>outcome</th></tr></thead><tbody>{body}</tbody></table>
<p class="muted">auto-refresh {refresh}s · {len(feed)} records across {sum(1 for r in results if r['ok'])}/{len(results)} nodes</p>
</body></html>"""


def load_nodes(path):
    cfg = json.load(open(_expand(path)))
    return cfg["nodes"] if isinstance(cfg, dict) else cfg


def serve(nodes, port, refresh):
    class H(BaseHTTPRequestHandler):
        def log_message(self, *a):  # quiet
            pass

        def do_GET(self):
            if self.path.split("?")[0] not in ("/", "/index.html"):
                self.send_response(404); self.end_headers(); return
            results, feed = aggregate(nodes)
            page = render_html(results, feed, refresh).encode()
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(page)))
            self.end_headers()
            self.wfile.write(page)
    httpd = ThreadingHTTPServer(("127.0.0.1", port), H)
    print(f"fleet monitor → http://127.0.0.1:{port}  (polling {len(nodes)} nodes every {refresh}s)")
    httpd.serve_forever()


def main():
    ap = argparse.ArgumentParser(description="cyberware fleet monitor — one dashboard over every node's govd")
    ap.add_argument("--config", required=True, help="fleet.json: {nodes:[{name,role,url,token_file}]}")
    ap.add_argument("--serve", type=int, metavar="PORT", help="serve the live HTML dashboard on 127.0.0.1:PORT")
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
