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
import argparse, concurrent.futures, html, json, os, re, secrets, threading, time, urllib.error, urllib.parse, urllib.request
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

DEFAULT_MIRROR = "~/.cyberware/fleet-ledgers"      # the central durable copy of every node's value-free ledgers
_DASH_HTML = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "govern", "govd_dashboard.html")

# the node sub-paths the EMBED (the individual-monitor iframe) proxies — exactly what govd_dashboard.html fetches.
_EMBED_PREFIX = ("monitor/run/", "flow/run/")
_EMBED_EXACT = ("monitor/state",)

# strip the active content a (compromised) node's flow SVG could carry — the SPA innerHTMLs it, so harden it
# server-side: drop <script>/<foreignObject>, every on*-handler, and javascript: URIs.
_SVG_STRIP = re.compile(rb"(?is)<script.*?</script>|<foreignObject.*?</foreignObject>"
                        rb"|\son\w+\s*=\s*(\"[^\"]*\"|'[^']*'|[^\s>]+)|javascript:")


def _sanitize_svg(data: bytes) -> bytes:
    return _SVG_STRIP.sub(b"", data)


def _embed_html(node_name: str, nonce: str) -> bytes:
    """The TRUSTED local-monitor SPA (govd_dashboard.html from the repo — never the node's HTML, so a node can't
    inject script into the dashboard origin), with a shim injected BEFORE it that (a) prefixes every absolute
    fetch path to /embed/<node>/ and (b) emulates EventSource by polling /monitor/state (so we need no fragile
    SSE-streaming proxy). The token is added server-side by the proxy — the iframe carries only a dummy. Every
    inline <script> is stamped with `nonce` so the page's CSP (script-src 'nonce-…') can run THESE scripts while
    blocking any inline event-handler a node's (innerHTML'd, sanitized) flow SVG might still smuggle in."""
    src = open(_DASH_HTML, "r", encoding="utf-8").read()
    marker = '<div id="root"></div>\n<script>'
    if marker not in src:                                    # fail loud rather than serve a silently-broken SPA
        raise RuntimeError("embed: dashboard asset changed — the shim-injection marker is gone")
    pfx = "/embed/" + urllib.parse.quote(node_name)
    css = ("<style>::-webkit-scrollbar{width:11px;height:11px}::-webkit-scrollbar-track{background:#0d1117}"
           "::-webkit-scrollbar-thumb{background:#30363d;border-radius:6px;border:2px solid #0d1117}"
           "::-webkit-scrollbar-thumb:hover{background:#484f58}"
           "html{scrollbar-width:thin;scrollbar-color:#30363d #0d1117}</style>")
    # emulate EventSource by polling, but fire ONLY when the snapshot CHANGED — mirroring govd's own SSE, which
    # pushes on change and ignores the per-second clock (govd.py digests the snapshot MINUS `now`). We key `last`
    # off the same now-stripped form: otherwise `now` advancing every second makes every idle poll look "changed",
    # re-rendering the open detail view and resetting its scroll (the detail-view page-jump). Reset on error so a
    # recovered, byte-identical snapshot still re-fires once.
    shim = ("<script>(function(){var P=" + json.dumps(pfx) + ";var _f=window.fetch.bind(window);"
            "window.fetch=function(u,o){return _f((typeof u===\"string\"&&u.charAt(0)===\"/\")?P+u:u,o);};"
            "window.EventSource=function(u){var s=this;s.onmessage=null;s.onerror=null;var last=null;"
            "function key(t){try{var o=JSON.parse(t);delete o.now;return JSON.stringify(o);}catch(e){return t;}}"
            "function poll(){_f(P+\"/monitor/state\",{cache:\"no-store\"})"
            ".then(function(r){return r.ok?r.text():Promise.reject();})"
            ".then(function(t){var k=key(t);if(k===last)return;last=k;if(s.onmessage)s.onmessage({data:t});})"
            ".catch(function(){last=null;if(s.onerror)s.onerror();});}"
            "s._t=setInterval(poll,2500);s.close=function(){clearInterval(s._t);};};})();</script>")
    src = src.replace(marker, '<div id="root"></div>\n' + css + shim + "\n<script>", 1)
    return src.replace("<script>", f'<script nonce="{nonce}">').encode()   # nonce every inline script


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


_MAX_BODY = 8 * 1024 * 1024                                 # cap a node response we read into memory / mirror to disk


class _NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, *a, **k):
        return None                                         # NEVER follow a node redirect


# A node could return a 3xx to an attacker host; urllib follows redirects AND keeps the X-Govd-Monitor token
# header — exfiltrating it. This opener refuses to follow ANY redirect (a 3xx surfaces as an HTTPError, caught
# by callers), so the monitor token can never leak to a redirect target.
_OPENER = urllib.request.build_opener(_NoRedirect)


def _get(url, token=None, timeout=6):
    req = urllib.request.Request(url, headers={"X-Govd-Monitor": token} if token else {})
    with _OPENER.open(req, timeout=timeout) as r:
        return json.loads(r.read(_MAX_BODY + 1)[:_MAX_BODY])


def _node_monitor(node, path):
    """GET a monitor endpoint for one node with its token (server-side — the token never leaves fleetdash)."""
    return _get(node["url"].rstrip("/") + path, token=_token(node))


def _get_raw(url, token=None, timeout=8):
    """Fetch a non-JSON resource (the flow SVG, a proxied read endpoint) → (content_type, bytes), bounded to
    _MAX_BODY. The token is added server-side (header), never in the browser URL; redirects are NOT followed
    (an attacker node can't 302 the token away)."""
    req = urllib.request.Request(url, headers={"X-Govd-Monitor": token} if token else {})
    with _OPENER.open(req, timeout=timeout) as r:
        data = r.read(_MAX_BODY + 1)
        if len(data) > _MAX_BODY:
            raise ValueError("node response exceeds the size cap")
        return r.headers.get("Content-Type", "application/octet-stream"), data


# ============================ central mirror (durable copy of every node's ledgers) ============================
# DEFENSE IN DEPTH: govd's own monitor is value-free, but the CENTER must not TRUST a (possibly compromised /
# MITM'd) node to be — it persists ONLY these known value-free fields, dropping anything else a node might
# smuggle into a /monitor/run response (a secret, an oversized blob). Mirrors govd's value-free projections.
_RUN_KEYS = ("run_id", "ts", "principal", "skill", "perk", "decision", "destructive", "approved",
             "seq", "plan_sha", "snippet_shas", "credential_ids", "wrapper", "var_keys", "problems",
             "tlc", "tlc_tla", "tlc_log", "traceparent", "sources", "restored", "failed", "progress")
_EVENT_KEYS = ("type", "step", "status", "exit", "reason", "span", "authority", "keyid",
               "snippet_shas", "meter", "ts", "traceparent", "result_nonce", "exod_keyid", "plan_sha")


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
    _atomic_write_bytes(path, json.dumps(obj).encode())


def _atomic_write_bytes(path, data):
    tmp = path + f".tmp.{os.getpid()}.{threading.get_ident()}"
    with open(tmp, "wb") as f:
        f.write(data)
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
            svg_path = os.path.join(runs_dir, _safe(rid) + ".svg")
            if not os.path.exists(svg_path):                  # the blueprint/oversight FLOW svg — record-static, fetch once
                try:
                    ct, svg = _get_raw(node["url"].rstrip("/") + "/flow/run/" + urllib.parse.quote(rid), tok)
                    if svg[:5] in (b"<svg ", b"<?xml"):
                        _atomic_write_bytes(svg_path, svg)
                except Exception:
                    pass
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


def load_run_svg(mirror_dir, name, run_id):
    """The run's mirrored blueprint/oversight flow SVG bytes (offline), or None."""
    p = os.path.join(_mbase(mirror_dir, name), "runs", _safe(run_id) + ".svg")
    return open(p, "rb").read() if os.path.isfile(p) else None


# the ONLY node sub-paths fleetdash will proxy live (token-injected) — read-only inspection endpoints. The
# target host is always the configured node (no SSRF to arbitrary hosts); this bounds it to safe read paths.
_PROXY_PREFIX = ("trace/", "intoto/", "flow/run/", "ledger/", "monitor/run/")
_PROXY_EXACT = ("catalog", "oversight")


def _proxiable(sub):
    """Whether `sub` is a safe node read-endpoint to proxy. Prefixes require a trailing-slash boundary; catalog
    and oversight match EXACTLY — so `catalogX` / `oversightWrite` / `govern` are NOT proxiable."""
    return sub in _PROXY_EXACT or any(sub.startswith(p) for p in _PROXY_PREFIX)


def _embed_proxiable(sub):
    """The endpoints the individual-monitor iframe (the embedded SPA) is allowed to reach on a node."""
    return sub in _EMBED_EXACT or any(sub.startswith(p) for p in _EMBED_PREFIX)


def render_node_iframe(node, reachable):
    """The per-node view = the ACTUAL individual-monitor UI in an iframe (the trusted SPA, served from
    /embed/<node>/, talking to the token-injecting proxy). When the node is down there is no live UI, so point
    at the durable central mirror board instead."""
    name = _esc(node.get("name"))
    links = (f'<a class="back" href="/">← fleet</a> · <a class="back" href="/mnode/{name}">central mirror board ↗</a>'
             f' · <span class="role">{_esc(node.get("role","-"))}</span>')
    if not reachable:
        return _page(f"{node.get('name')}", links + f'<h1>{name} <span class="off">offline</span></h1>'
                     f'<p class="muted">node unreachable — the live monitor UI needs the node. '
                     f'<a href="/mnode/{name}">open the central mirror board ↗</a> (durable, inspectable offline).</p>')
    content = (links + f'<iframe src="/embed/{name}/?token=proxied" title="{name} monitor" '
               'style="width:100%;height:90vh;border:1px solid #30363d;border-radius:8px;background:#0d1117;margin-top:10px">'
               '</iframe>')
    return _page(f"{node.get('name')} — monitor", content)


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
        return {"name": name, "role": node.get("role", "-"), "fleet_tier": node.get("fleet_tier"),
                "url": node["url"].rstrip("/"),
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
    out = {"name": name, "role": node.get("role", "-"), "fleet_tier": node.get("fleet_tier"),
           "url": url, "ok": False, "health": None,
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
 .layout{display:flex;gap:18px;align-items:flex-start}
 .sidebar{flex:0 0 240px;position:sticky;top:0} .main{flex:1 1 auto;min-width:0}
 .navsearch{width:100%;box-sizing:border-box;background:#0d1117;border:1px solid #30363d;border-radius:6px;color:#c9d1d9;padding:6px 8px;margin:0 0 10px;font:12px ui-monospace,Menlo,monospace}
 .navsearch:focus{outline:none;border-color:#58a6ff}
 .navtier{margin-bottom:8px}
 .navhdr{cursor:pointer;color:#8b949e;text-transform:uppercase;font-size:11px;font-weight:600;padding:4px 2px;user-select:none}
 .navhdr .caret{display:inline-block;width:12px;color:#6e7681}
 .navtier.collapsed .navlist{display:none} .navtier.collapsed .caret{transform:rotate(-90deg)}
 .tcount,.navnode .cnt{color:#6e7681}
 .navlist{display:flex;flex-direction:column;gap:4px;margin-top:4px}
 .navnode{display:flex;align-items:center;gap:6px;background:#161b22;border:1px solid #30363d;border-radius:6px;padding:5px 8px;color:#c9d1d9}
 .navnode:hover{background:#1c2230;text-decoration:none}
 .navnode .role{margin-left:0} .navnode .cnt{margin-left:auto}
 .dot{display:inline-block;width:8px;height:8px;border-radius:50%;flex:0 0 8px}
 .dot.up{background:#2ea043} .dot.down{background:#f85149} .dot.stale{background:#6e7681}
 .navempty{color:#6e7681;font-size:11px;padding:6px 2px}
 @media(max-width:760px){.layout{flex-direction:column}.sidebar{flex:none;width:100%;position:static}}
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
 .hlink{font-size:12px;color:#58a6ff;margin-left:10px}
 .gauge{display:flex;align-items:center;gap:8px}
 .gbar{flex:1;min-width:80px;height:10px;background:#21262d;border-radius:5px;overflow:hidden}
 .gfill{height:100%;background:linear-gradient(90deg,#2ea043,#d29922 70%,#f85149)}
 .glab{min-width:70px;color:#8b949e;font-size:11px}
 pre{background:#161b22;border:1px solid #21262d;border-radius:6px;padding:10px;overflow:auto;max-height:340px;color:#8b949e;white-space:pre-wrap;word-break:break-word}
 details{margin:6px 0} summary{cursor:pointer;color:#58a6ff;padding:4px 0}
 img{display:block;margin:8px 0}
 html{scrollbar-width:thin;scrollbar-color:#30363d #0d1117}
 ::-webkit-scrollbar{width:11px;height:11px}
 ::-webkit-scrollbar-track{background:#0d1117}
 ::-webkit-scrollbar-thumb{background:#30363d;border-radius:6px;border:2px solid #0d1117}
 ::-webkit-scrollbar-thumb:hover{background:#484f58}
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


def _node_groups(results):
    """Group node summaries by fleet_tier, ordered mothership -> edge -> subagent -> deeper -> untiered (last)."""
    from infra.govern.fleetd import _fleet_rank        # single source of truth for the hierarchy rank
    groups = {}
    for r in results:
        groups.setdefault(r.get("fleet_tier"), []).append(r)

    def key(ft):
        rk = _fleet_rank(ft)
        return (rk is None, rk if rk is not None else 0, str(ft if ft is not None else "~"))
    return [(ft, groups[ft]) for ft in sorted(groups, key=key)]


def _sidebar(results):
    """The hierarchical, searchable node nav: a filter box + nodes grouped under collapsible fleet-tiers."""
    parts = ['<input class="navsearch" id="navsearch" placeholder="filter nodes…" autocomplete="off">']
    if not results:
        parts.append('<div class="navempty">no nodes in the roster</div>')
    for ft, nodes in _node_groups(results):
        label = _esc(ft if ft is not None else "untiered")
        items = []
        for r in nodes:
            reach = r.get("reachable")
            dot = "up" if reach else ("down" if reach is False else "stale")
            name, role = _esc(r.get("name", "?")), _esc(r.get("role") or "")
            search = _esc(" ".join(str(x) for x in (r.get("name"), r.get("role"), ft) if x).lower())
            items.append(f'<a class="navnode" data-search="{search}" href="/node/{name}">'
                         f'<span class="dot {dot}"></span><b>{name}</b>'
                         f'<span class="role">{role}</span><span class="cnt">{r.get("count", 0)}</span></a>')
        parts.append(f'<div class="navtier" data-tier="{label}">'
                     f'<div class="navhdr" data-tier="{label}"><span class="caret">▾</span>{label} '
                     f'<span class="tcount">{len(nodes)}</span></div>'
                     f'<div class="navlist">{"".join(items)}</div></div>')
    return '<aside class="sidebar">' + "".join(parts) + '</aside>'


# Client-side nav: search-filter + per-tier collapse, persisted in localStorage so they survive the 5s
# meta-refresh (the same pattern the display-timezone selector uses). No new server round-trips.
_NAVJS = """
(function(){
  var KEY='cw-nav', box=document.getElementById('navsearch'), s={};
  try{s=JSON.parse(localStorage.getItem(KEY))||{}}catch(e){}
  function save(){ try{localStorage.setItem(KEY,JSON.stringify(s))}catch(e){} }
  if(box && s.q) box.value=s.q;
  document.querySelectorAll('.navtier').forEach(function(t){
    if(s.collapsed && s.collapsed[t.getAttribute('data-tier')]) t.classList.add('collapsed');
  });
  function filter(){
    var q=(box?box.value:'').trim().toLowerCase();
    document.querySelectorAll('.navtier').forEach(function(t){
      var any=false;
      t.querySelectorAll('.navnode').forEach(function(n){
        var hit=!q||(n.getAttribute('data-search')||'').indexOf(q)>=0;
        n.style.display=hit?'':'none'; if(hit) any=true;
      });
      t.style.display=(!q||any)?'':'none';
    });
  }
  if(box) box.addEventListener('input',function(){ s.q=box.value; save(); filter(); });
  document.querySelectorAll('.navhdr').forEach(function(h){
    h.addEventListener('click',function(){
      var t=h.parentNode;
      t.classList.toggle('collapsed');
      s.collapsed=s.collapsed||{}; s.collapsed[h.getAttribute('data-tier')]=t.classList.contains('collapsed'); save();
    });
  });
  filter();
})();
"""


def render_html(results, feed, risk, refresh=5):
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
    content = (f'<h1>cyberware · fleet control — who fired what, where '
               f'<a class="hlink" href="/accounting">accounting →</a></h1>'
               f'<div class="layout">{_sidebar(results)}'
               f'<section class="main">{_banner(risk)}'
               f'<table><thead><tr><th>when (utc)</th><th>where (node)</th><th>who (principal)</th>'
               f'<th>what (skill/perk)</th><th>exec</th><th>outcome</th></tr></thead><tbody>{body}</tbody></table>'
               f'<p class="muted">click a node or a run for detail · central mirror of {len(feed)} runs · '
               f'{up}/{len(results)} nodes live · auto-refresh {refresh}s</p>'
               f'</section></div><script>{_NAVJS}</script>')
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


def _spend_rollup(feed):
    """Per-actor CREDIT spend across the fleet, from the mirrored value-free `cost`. Returns rows sorted by
    spend (desc), each {actor, spent, allows, runs, nodes, _spent}."""
    from infra.settle.money import Money
    agg = {}
    for x in feed:
        a = x.get("principal") or "?"
        e = agg.setdefault(a, {"actor": a, "_spent": Money.zero("CREDITS"), "allows": 0, "runs": 0, "nodes": set()})
        e["runs"] += 1
        e["nodes"].add(x.get("node"))
        if x.get("decision") == "allow" and x.get("cost"):
            try:
                e["_spent"] = e["_spent"] + Money(str(x["cost"]), "CREDITS")
                e["allows"] += 1
            except (TypeError, ValueError):
                pass
    rows = [{"actor": e["actor"], "spent": str(e["_spent"].amount), "allows": e["allows"],
             "runs": e["runs"], "nodes": len(e["nodes"]), "_spent": e["_spent"]} for e in agg.values()]
    rows.sort(key=lambda r: r["_spent"].amount, reverse=True)
    return rows


def render_accounting(feed, refresh=5):
    """The fleet ACCOUNTANT page: per-actor CREDIT spend across the fleet (from the mirrored cost), gauged
    relative to the top spender. Click an actor for their cross-fleet account. (The per-node allowance/balance
    gauge lives on each node's own monitor — that node holds the budget ledger.)"""
    from infra.settle.money import Money
    rows = _spend_rollup(feed)
    total = Money.zero("CREDITS")
    for r in rows:
        total = total + r["_spent"]
    top = max((r["_spent"].amount for r in rows), default=0) or 1
    body = []
    for r in rows:
        pct = int(r["_spent"].amount * 100 / top)                    # relative bar (exact Decimal, no float)
        body.append(f'<tr class="run" onclick="location=\'/principal/{_esc(r["actor"])}\'">'
                    f'<td><b>{_esc(r["actor"])}</b></td>'
                    f'<td><div class="gauge"><div class="gbar"><div class="gfill" style="width:{pct}%"></div></div>'
                    f'<span class="glab">{_esc(r["spent"])}</span></div></td>'
                    f'<td>{r["allows"]}/{r["runs"]}</td><td>{r["nodes"]}</td></tr>')
    rows_html = "".join(body) or '<tr><td colspan="4" class="muted">no metered runs yet</td></tr>'
    content = ('<a class="back" href="/">← fleet</a><h1>fleet accounting — credit spend by actor</h1>'
               f'<p class="kv">total spent across the fleet: <b>{_esc(str(total.amount))}</b> CREDITS · '
               f'{len(rows)} actors · click an actor for their account · the per-node allowance/balance gauge '
               f'is on each node\'s monitor (it holds the budget ledger).</p>'
               '<table><thead><tr><th>actor</th><th>spend (relative)</th><th>allowed/runs</th><th>nodes</th>'
               f'</tr></thead><tbody>{rows_html}</tbody></table>')
    return _page("fleet — accounting", content, refresh)


def render_principal(actor, feed, refresh=5):
    """The individual ACCOUNTANT page: one actor's runs + credit spend across the fleet."""
    from infra.settle.money import Money
    mine = [x for x in feed if (x.get("principal") or "?") == actor]
    spent = Money.zero("CREDITS")
    rows = []
    for x in sorted(mine, key=lambda d: d.get("ts") or "", reverse=True)[:300]:
        if x.get("decision") == "allow" and x.get("cost"):
            try:
                spent = spent + Money(str(x["cost"]), "CREDITS")
            except (TypeError, ValueError):
                pass
        cls = {"allow": "ok", "reject": "no", "push_back": "warn"}.get(x.get("decision"), "")
        rows.append(f'<tr class="run" onclick="location=\'/run/{_esc(x["node"])}/{_esc(x.get("run_id") or "")}\'">'
                    f'<td class="t">{_esc(str(x.get("ts"))[:19])}</td><td>{_esc(x["node"])}</td>'
                    f'<td>{_esc(x.get("skill"))}/{_esc(x.get("perk"))}</td><td>{_esc(x.get("cost") or "—")}</td>'
                    f'<td class="{cls}">{_esc(x.get("decision"))}</td></tr>')
    rows_html = "".join(rows) or '<tr><td colspan="5" class="muted">no runs</td></tr>'
    content = (f'<a class="back" href="/accounting">← accounting</a><h1>{_esc(actor)} — credit account</h1>'
               f'<p class="kv">spent across the fleet: <b>{_esc(str(spent.amount))}</b> CREDITS · {len(mine)} runs</p>'
               '<table><thead><tr><th>when</th><th>node</th><th>what</th><th>cost</th><th>outcome</th></tr></thead>'
               f'<tbody>{rows_html}</tbody></table>')
    return _page(f"{_esc(actor)} — account", content, refresh)


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


def _details(summary, inner):
    return f'<details><summary>{summary}</summary>{inner}</details>'


def render_run(name, run_id, detail, has_svg=False):
    """Per-run LEDGER INSPECTION — local-monitor parity from the durable mirror: the full value-free record
    (claim + approval, the step plan, the event chain, plan + closure pins, the model-check + provenance) + the
    blueprint/oversight FLOW svg + a raw-JSON view. Fully inspectable even when the node is OFFLINE."""
    back = f'<a class="back" href="/node/{_esc(name)}">← {_esc(name)}</a>'
    if not detail:
        return _page("run", back + f'<h1>run {_esc(run_id)}</h1>'
                     '<p class="muted">not in the central mirror (the node may not have run it, or the mirror has not polled it yet)</p>')
    rid, node_e = _esc(run_id), _esc(detail.get("_node", name))
    dcls = {"allow": "ok", "reject": "no", "push_back": "warn"}.get(detail.get("decision"), "")

    by_step = {e.get("step"): e for e in detail.get("events", []) if e.get("type") == "step_result"}
    granted = {e.get("step") for e in detail.get("events", []) if e.get("type") == "granted"}
    srows = []
    for i, tool in enumerate(detail.get("seq", []), 1):
        e = by_step.get(str(i))
        state = ("ok" if e and e.get("status") == "ok" else "error" if e
                 else "granted" if str(i) in granted else "pending")
        cls = {"ok": "ok", "error": "no", "granted": "warn"}.get(state, "")
        srows.append(f'<tr><td>{i}</td><td>{_esc(tool)}</td><td>{_esc((e or {}).get("authority","—"))}</td>'
                     f'<td>{_esc((e or {}).get("exit","—"))}</td><td class="{cls}">{_esc(state)}</td></tr>')
    steps = "".join(srows) or '<tr><td colspan="5" class="muted">no steps declared</td></tr>'

    chain = "".join(                                          # the event chain — the ledger itself
        f'<tr><td>{_esc(e.get("type"))}</td><td>{_esc(e.get("step","—"))}</td>'
        f'<td>{_esc(e.get("status","—"))}</td><td>{_esc(e.get("authority","—"))}</td>'
        f'<td><code>{_esc(str(e.get("exod_keyid") or e.get("keyid") or "")[:18]) or "—"}</code></td>'
        f'<td class="t">{_esc(str(e.get("ts"))[:19])}</td></tr>'
        for e in detail.get("events", [])) or '<tr><td colspan="6" class="muted">no events recorded</td></tr>'

    snip = detail.get("snippet_shas") or {}
    sniprows = "".join(f'<tr><td>{_esc(k)}</td><td><code>{_esc(str(v)[:32])}</code></td></tr>'
                       for k, v in snip.items()) or '<tr><td colspan="2" class="muted">none</td></tr>'
    probs = ", ".join((p.get("id", "?") if isinstance(p, dict) else str(p))
                      for p in detail.get("problems", [])) or "none"
    tlc = detail.get("tlc")
    tlc_str = ("✓ proven" if tlc in (True, "ok", "pass") else "—" if tlc in (None, "") else _esc(tlc))
    tp = detail.get("traceparent") or ""

    extras = ""
    if detail.get("wrapper"):
        extras += _details("blessed wrapper (run.sh)", f'<pre>{_esc(detail["wrapper"])}</pre>')
    if detail.get("tlc_tla"):
        extras += _details("model-check spec (TLA+)", f'<pre>{_esc(detail["tlc_tla"])}</pre>')
    if detail.get("tlc_log"):
        extras += _details("model-check log", f'<pre>{_esc(detail["tlc_log"])}</pre>')
    flow = (f'<h2>flow — blueprint &amp; oversight</h2><img src="/flow/{node_e}/{rid}" alt="run flow" '
            'style="max-width:100%;background:#fff;border-radius:8px;padding:6px">' if has_svg else "")

    content = (back + f'<h1>{_esc(detail.get("skill"))}/{_esc(detail.get("perk"))} '
               f'<span class="{dcls}">{_esc(detail.get("decision"))}</span> {_risk_pill(detail)}</h1>'
               f'<p class="kv">where <b>{node_e}</b> · who <b>{_esc(detail.get("principal","?"))}</b> · when '
               f'<b>{_esc(str(detail.get("ts"))[:19])}</b> · run <code>{rid}</code> · '
               f'<a href="/raw/{node_e}/{rid}">raw ledger ↗</a></p>'

               '<h2>claim &amp; approval</h2>'
               f'<p class="kv">destructive <b>{_esc(detail.get("destructive",False))}</b> · '
               f'approved <b>{_esc(detail.get("approved",[]) or "—")}</b> · '
               f'credential keys <b>{_esc(detail.get("credential_ids",[]) or "—")}</b> · '
               f'problems <b class="{"no" if probs != "none" else ""}">{_esc(probs)}</b></p>'

               f'<h2>steps</h2><table><thead><tr><th>#</th><th>tool</th><th>exec (authority)</th><th>exit</th>'
               f'<th>state</th></tr></thead><tbody>{steps}</tbody></table>'

               f'<h2>ledger — event chain ({len(detail.get("events",[]))})</h2>'
               f'<table><thead><tr><th>type</th><th>step</th><th>status</th><th>authority</th><th>keyid</th>'
               f'<th>when</th></tr></thead><tbody>{chain}</tbody></table>'

               '<h2>plan &amp; closure</h2>'
               f'<p class="kv">plan_sha <code>{_esc((detail.get("plan_sha") or "")[:32]) or "—"}</code> · '
               f'var_keys <b>{_esc(detail.get("var_keys",[]))}</b></p>'
               f'<table><thead><tr><th>closure file</th><th>pinned sha256</th></tr></thead><tbody>{sniprows}</tbody></table>'

               '<h2>verification &amp; provenance</h2>'
               f'<p class="kv">model-check <b class="{"ok" if tlc in (True,"ok","pass") else ""}">{tlc_str}</b> · '
               f'traceparent <code>{_esc(tp[:40]) or "—"}</code> · '
               f'<a href="/proxy/{node_e}/trace/{rid}">trace ↗</a> · '
               f'<a href="/proxy/{node_e}/intoto/{rid}">in-toto ↗</a></p>'
               + (f'<h2>artifacts</h2>{extras}' if extras else "")
               + flow)
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
            self._bytes(code, "text/html; charset=utf-8", page.encode())

        def _bytes(self, code, ctype, data, extra=None):
            self.send_response(code)
            self.send_header("Content-Type", ctype)
            self.send_header("Content-Length", str(len(data)))
            for k, v in (extra or {}).items():
                self.send_header(k, v)
            self.end_headers()
            self.wfile.write(data)

        def _embed(self, up):
            """Serve the individual-monitor SPA (`/embed/<node>/`) or proxy ONE of its data fetches to the node
            (token added server-side; the dummy ?token is stripped). The SPA is the TRUSTED repo asset; only
            value-free JSON / a sanitized flow SVG flow back, so a node can never inject script into this origin."""
            seg = up.path[len("/embed/"):]
            node_name, _, sub = seg.partition("/")
            node = by_name.get(urllib.parse.unquote(node_name))
            if not node:
                return self._send(404, _page("404", "unknown node"))
            if not sub:                                              # the dashboard HTML (trusted, from the repo)
                nonce = secrets.token_urlsafe(12)
                csp = (f"default-src 'self'; script-src 'nonce-{nonce}'; style-src 'unsafe-inline'; "
                       "img-src 'self' data:; connect-src 'self'; frame-ancestors 'self'")
                return self._bytes(200, "text/html; charset=utf-8",
                                   _embed_html(urllib.parse.unquote(node_name), nonce),
                                   extra={"Content-Security-Policy": csp})
            sub = urllib.parse.unquote(sub)
            if not _embed_proxiable(sub):
                return self._send(404, _page("404", "not proxiable"))
            target = node["url"].rstrip("/") + "/" + urllib.parse.quote(sub, safe="/")
            tok = _token(node)
            q = [(k, v) for k, v in urllib.parse.parse_qsl(up.query) if k != "token"]   # drop the dummy token
            if q:
                target += "?" + urllib.parse.urlencode(q)
            try:
                _ct, data = _get_raw(target, tok)
            except urllib.error.HTTPError as e:
                return self._bytes(e.code, "application/json", b'{"error":"upstream"}')
            except Exception:
                return self._bytes(502, "application/json", b'{"error":"node unreachable"}')
            if tok and tok.encode() in data:                        # a node must NEVER echo our token to the browser
                data = data.replace(tok.encode(), b"[redacted]")
            if sub.startswith("flow/run/"):                          # the SPA innerHTMLs this — sanitize it
                return self._bytes(200, "image/svg+xml; charset=utf-8", _sanitize_svg(data))
            return self._bytes(200, "application/json; charset=utf-8", data)

        def do_GET(self):
            up = urllib.parse.urlparse(self.path)
            if up.path.startswith("/embed/"):                       # the individual-monitor iframe + its proxy
                try:
                    return self._embed(up)
                except Exception as e:
                    return self._send(500, _page("error", f'<p class="muted">{_esc(e)}</p>'))
            parts = [urllib.parse.unquote(s) for s in up.path.strip("/").split("/") if s]
            try:
                if not parts:                                       # overview (mirror-backed)
                    results, feed = fleet_from_mirror(nodes, mirror_dir)
                    return self._send(200, render_html(results, feed, risk_summary(feed), refresh))
                if parts[0] == "risk":                              # fleet-wide risk / approval queue
                    results, feed = fleet_from_mirror(nodes, mirror_dir)
                    return self._send(200, render_risk(feed, risk_summary(feed), refresh))
                if parts[0] == "accounting":                        # fleet CREDIT accounting (spend by actor)
                    _, feed = fleet_from_mirror(nodes, mirror_dir)
                    return self._send(200, render_accounting(feed, refresh))
                if parts[0] == "principal" and len(parts) == 2:     # one actor's cross-fleet credit account
                    _, feed = fleet_from_mirror(nodes, mirror_dir)
                    return self._send(200, render_principal(parts[1], feed, refresh))
                if parts[0] == "node" and len(parts) == 2:          # per-node = the LIVE individual-monitor UI (iframe)
                    node = by_name.get(parts[1])
                    if not node:
                        return self._send(404, _page("404", '<a class="back" href="/">← fleet</a><p class="muted">unknown node</p>'))
                    try:
                        _get(node["url"].rstrip("/") + "/health")
                        reachable = True
                    except Exception:
                        reachable = False
                    return self._send(200, render_node_iframe(node, reachable))
                if parts[0] == "mnode" and len(parts) == 2:         # the durable central MIRROR board (offline-capable)
                    node = by_name.get(parts[1])
                    if not node:
                        return self._send(404, _page("404", '<a class="back" href="/">← fleet</a><p class="muted">unknown node</p>'))
                    results, _ = fleet_from_mirror([node], mirror_dir)
                    return self._send(200, render_node(node, results[0], refresh))
                if parts[0] == "run" and len(parts) == 3:           # per-run LEDGER INSPECTION (durable mirror)
                    node = by_name.get(parts[1])
                    if not node:
                        return self._send(404, _page("404", '<a class="back" href="/">← fleet</a><p class="muted">unknown node</p>'))
                    has_svg = load_run_svg(mirror_dir, node["name"], parts[2]) is not None if mirror_dir else False
                    return self._send(200, render_run(node["name"], parts[2],
                                                      load_run(mirror_dir, node["name"], parts[2]) if mirror_dir else None,
                                                      has_svg))
                if parts[0] == "raw" and len(parts) == 3:           # the raw ledger record (value-free JSON)
                    node = by_name.get(parts[1])
                    detail = load_run(mirror_dir, node["name"], parts[2]) if node and mirror_dir else None
                    body = _esc(json.dumps(detail, indent=2)) if detail else "not in the mirror"
                    return self._send(200, _page("raw ledger", f'<a class="back" href="/run/{_esc(parts[1])}/{_esc(parts[2])}">← run</a>'
                                                 f'<h1>raw ledger · {_esc(parts[2])}</h1><pre>{body}</pre>'))
                if parts[0] == "flow" and len(parts) == 3:          # the blueprint/oversight SVG (mirror, else live)
                    node = by_name.get(parts[1])
                    if not node:
                        return self._send(404, _page("404", "unknown node"))
                    svg = load_run_svg(mirror_dir, node["name"], parts[2]) if mirror_dir else None
                    if svg is None:                                 # not mirrored — proxy live (token server-side)
                        try:
                            _ct, svg = _get_raw(node["url"].rstrip("/") + "/flow/run/" + urllib.parse.quote(parts[2]), _token(node))
                        except Exception:
                            svg = None
                    if not svg:
                        return self._send(404, _page("404", "no flow recorded"))
                    return self._bytes(200, "image/svg+xml; charset=utf-8", svg)
                if parts[0] == "proxy" and len(parts) >= 3:         # token-injecting read proxy to a node endpoint
                    node = by_name.get(parts[1])
                    sub = "/".join(parts[2:])
                    if not node or not _proxiable(sub):
                        return self._send(404, _page("404", "not proxiable"))
                    try:
                        _ct, data = _get_raw(node["url"].rstrip("/") + "/" + urllib.parse.quote(sub, safe="/"), _token(node))
                        # NEVER pass the node's Content-Type through — a node returning text/html would XSS the
                        # dashboard origin. Serve every proxied read as inert text/plain (raw JSON is readable).
                        return self._bytes(200, "text/plain; charset=utf-8", data)
                    except urllib.error.HTTPError as e:
                        return self._send(e.code, _page("upstream", f'<p class="muted">node returned HTTP {e.code}</p>'))
                    except Exception as e:
                        return self._send(502, _page("upstream", f'<p class="muted">{_esc(type(e).__name__)}</p>'))
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
            results = [{"name": r["name"], "role": r["role"], "fleet_tier": r.get("fleet_tier"),
                        "url": r["url"], "reachable": r["ok"],
                        "health": r.get("health"), "index": {}, "count": 0} for r in live]
            feed = []
            for r in live:
                for d in r.get("decisions", []):
                    feed.append({"node": r["name"], "role": r["role"], **d})
            feed.sort(key=lambda x: x.get("ts") or "", reverse=True)
        print(render_text(results, feed, risk_summary(feed), a.limit))


if __name__ == "__main__":
    main()
