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
import argparse, concurrent.futures, html, ipaddress, json, os, re, secrets, threading, time, urllib.error, urllib.parse, urllib.request
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
_RUN_KEYS = ("run_id", "ts", "principal", "skill", "perk", "decision", "destructive", "approved", "cost",
             "seq", "plan_sha", "snippet_shas", "credential_ids", "wrapper", "var_keys", "problems",
             "tlc", "tlc_tla", "tlc_log", "traceparent", "sources", "restored", "failed", "progress",
             "needs_approve")
_EVENT_KEYS = ("type", "step", "status", "exit", "reason", "span", "authority", "keyid",
               "snippet_shas", "meter", "ts", "traceparent", "result_nonce", "exod_keyid", "plan_sha",
               "values_sha")   # tier-2 commitment (a hash) — the value-free per-step link into the value ledger
# the compact per-run row the accounting/risk feeds read — MUST include `cost`, or the fleet credit-spend
# rollup (_spend_rollup / render_accounting) always reads 0 (the per-run detail carries it, the row dropped it).
# Same trap for `needs_approve`/`approved`: the risk queue and the supersession pass read the FEED rows, so a
# field missing here silently vanishes fleet-wide even though the per-run detail kept it.
_INDEX_KEYS = ("run_id", "ts", "principal", "skill", "perk", "decision", "destructive", "cost",
               "needs_approve", "approved", "failed", "progress")


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
            # carry the decision-feed metadata the run dir may not have (principal/ts/decision/destructive/
            # needs_approve/problems — a non-allow run often has no detail record, so the feed is the only source)
            for k in ("skill", "perk", "decision", "destructive", "ts", "principal", "needs_approve", "problems"):
                if detail.get(k) is None and d.get(k) is not None:
                    detail[k] = d.get(k)
            detail = _value_free(detail)                      # ALLOWLIST — never trust the node to be value-free
            detail["run_id"], detail["_node"], detail["_mirrored_at"] = rid, name, snap.get("now")
            # DERIVE failed/progress centrally from the value-free events — govd computes them only in its own
            # monitor snapshot (never in the decision feed or /monitor/run detail), so without this the board's
            # `failed` tag and the run page's live-refresh gate would always read empty for a real node.
            sr = [e for e in detail.get("events", []) if e.get("type") == "step_result"]
            if sr or detail.get("seq"):
                detail["failed"] = any(e.get("status") != "ok" for e in sr)
                detail["progress"] = f"{sum(1 for e in sr if e.get('status') == 'ok')}/{len(detail.get('seq') or [])}"
            _atomic_write(os.path.join(runs_dir, _safe(rid) + ".json"), detail)
            svg_path = os.path.join(runs_dir, _safe(rid) + ".svg")
            if not os.path.exists(svg_path):                  # the blueprint/oversight FLOW svg — record-static, fetch once
                try:
                    ct, svg = _get_raw(node["url"].rstrip("/") + "/flow/run/" + urllib.parse.quote(rid), tok)
                    if svg[:5] in (b"<svg ", b"<?xml"):
                        _atomic_write_bytes(svg_path, svg)
                except Exception:
                    pass
            index[rid] = {k: detail.get(k) for k in _INDEX_KEYS}
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
    if mirror_dir is None:                                   # --no-mirror: there is no durable copy to read
        return {"health": None, "index": {}}
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
_PROXY_PREFIX = ("trace/", "intoto/", "flow/run/", "ledger/", "monitor/run/", "monitor/values/")
_PROXY_EXACT = ("catalog", "oversight")


def _proxiable(sub):
    """Whether `sub` is a safe node read-endpoint to proxy. Prefixes require a trailing-slash boundary; catalog
    and oversight match EXACTLY — so `catalogX` / `oversightWrite` / `govern` are NOT proxiable."""
    return sub in _PROXY_EXACT or any(sub.startswith(p) for p in _PROXY_PREFIX)


def _embed_proxiable(sub):
    """The endpoints the individual-monitor iframe (the embedded SPA) is allowed to reach on a node."""
    return sub in _EMBED_EXACT or any(sub.startswith(p) for p in _EMBED_PREFIX)


def render_node_iframe(node, reachable, refresh=None):
    """The per-node view = the ACTUAL individual-monitor UI in an iframe (the trusted SPA, served from
    /embed/<node>/, talking to the token-injecting proxy). When the node is down there is no live UI, so point
    at the durable central mirror board instead — that page auto-refreshes (pass `refresh`) so it recovers by
    itself when the node returns; the live variant must NOT refresh (a reload would tear down the SPA's state)."""
    name = _esc(node.get("name"))
    links = (f'<p class="crumb"><a href="/">fleet</a> / {name} · '
             f'<a href="/mnode/{name}">central mirror board ↗</a>'
             f' · <span class="role">{_esc(node.get("role", "-"))}</span></p>')
    if not reachable:
        return _page(f"{node.get('name')}", links + f'<h1>{name} <span class="off">offline</span></h1>'
                     f'<p class="muted">node unreachable — the live monitor UI needs the node. '
                     f'<a href="/mnode/{name}">open the central mirror board ↗</a> (durable, inspectable offline). '
                     'this page retries automatically.</p>', refresh)
    content = (links + f'<iframe src="/embed/{name}/?token=proxied" title="{name} monitor" '
               'style="width:100%;height:calc(100vh - 128px);border:1px solid var(--line);border-radius:8px;'
               'background:#0a0e14;margin-top:4px"></iframe>')
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


def _claim_key(x):
    """The value-free identity of a claim: node + principal + skill + perk (the axes an approval decision keys
    on). Values never enter — two rm claims on different targets share a key, which is why supersession must be
    COUNT-based, never 'any later allow', or a second pending claim would vanish behind the first's approval."""
    return (x.get("node"), x.get("principal"), x.get("skill"), x.get("perk"))


def mark_superseded(feed, risk):
    """Annotate approval-queue entries a later approved run has already answered. The mirror never deletes, so
    every push_back in history stays in the queue forever unless we recognise its resolution: an `allow` of the
    same claim that carries a non-empty approval IS the operator's answer (the agent re-submitted with it).

    Counting, not 'any later allow', is the safety property: with two DISTINCT pending push_backs of the same
    value-free tuple and a single approval, only ONE was answered — so we mark the oldest N (FIFO) superseded
    where N = the tuple's approved-allow count, leaving the newest push_backs visibly pending. Pending can then
    never drop below (#push_backs − #approvals), so a genuinely-unanswered destructive claim is never hidden
    behind a false 'queue clear'. Derived purely from the ledger — no server-side ack state."""
    approvals = {}
    for y in feed:
        if y.get("decision") == "allow" and y.get("approved"):
            approvals[_claim_key(y)] = approvals.get(_claim_key(y), 0) + 1
    by_key = {}
    for a in risk.get("approval", []):
        by_key.setdefault(_claim_key(a), []).append(a)
    for key, items in by_key.items():
        items.sort(key=lambda a: str(a.get("ts") or ""))         # oldest first — approvals answer FIFO
        answered = approvals.get(key, 0)
        for i, a in enumerate(items):
            a["_superseded"] = i < answered
    return risk


def _risk_pending(risk):
    """How many approval-queue entries still NEED a decision (superseded ones are answered, not actionable)."""
    return sum(1 for x in risk.get("approval", []) if not x.get("_superseded"))


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
    na = _risk_pending(risk)
    hi, rj = (len(risk.get(k, [])) for k in ("high", "reject"))
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
# One product, one theme: the token block below is a byte-copy of govd_dashboard.html's :root, so the fleet
# pages and the embedded per-node monitor read as the same surface (and future palette drift is diffable).
_STYLE = """
 :root{
   --bg:#0a0e14; --panel:#0f1722; --panel2:#131d2b; --line:#1e2c3d; --ink:#cdd9e5;
   --dim:#6b7d92; --accent:#39d0d8; --allow:#36d399; --push:#fbbd23; --reject:#f87272;
   --destructive:#c084fc; --restored:#7f8fa3; --mono:'SF Mono',ui-monospace,'JetBrains Mono',Menlo,Consolas,monospace;
 }
 *{box-sizing:border-box}
 html{scroll-padding-top:60px}                                  /* #approval/#high/#reject jumps clear the sticky topbar */
 body{margin:0;background:var(--bg);color:var(--ink);font:13px/1.5 var(--mono);
   background-image:radial-gradient(circle at 18% -10%,rgba(57,208,216,.08),transparent 42%)}
 a{color:var(--accent);text-decoration:none} a:hover{text-decoration:underline}
 a:focus-visible,.cp:focus-visible,button:focus-visible{outline:2px solid var(--accent);outline-offset:2px;border-radius:4px}
 header.top{display:flex;align-items:center;gap:12px;padding:9px 18px;border-bottom:1px solid var(--line);
   position:sticky;top:0;background:rgba(10,14,20,.94);backdrop-filter:blur(6px);z-index:50;flex-wrap:wrap}
 .brand{font-size:14px;letter-spacing:.05em;color:var(--ink);white-space:nowrap} .brand b{color:var(--accent);font-weight:600}
 .topnav{display:flex;gap:2px;flex-wrap:wrap}
 .topnav a{padding:3px 10px;border-radius:6px;color:var(--dim);font-size:12px}
 .topnav a:hover{color:var(--ink);text-decoration:none;background:var(--panel)}
 .topnav a.on{color:var(--accent);background:var(--panel);box-shadow:inset 0 -2px 0 var(--accent)}
 .riskchip{padding:2px 9px;border-radius:12px;font-size:11px;font-weight:600;border:1px solid var(--push);
   color:var(--push);background:rgba(251,189,35,.08)}
 .riskchip:hover{text-decoration:none;background:rgba(251,189,35,.18)}
 .grow{flex:1}
 .asof{color:var(--dim);font-size:11px;white-space:nowrap} .asof .lag{color:var(--push)}
 .pausebtn{font:12px var(--mono);padding:2px 9px;background:var(--panel);border:1px solid var(--line);
   border-radius:6px;color:var(--dim);cursor:pointer} .pausebtn.on{color:var(--push);border-color:var(--push)}
 /* tier-2 tool-use reveal: a themed action button + high-contrast decrypted-value rows */
 .cwbtn{font:12px var(--mono);padding:5px 13px;background:rgba(57,208,216,.07);border:1px solid var(--accent);
   border-radius:6px;color:var(--accent);cursor:pointer;letter-spacing:.03em;transition:background .15s,box-shadow .15s}
 .cwbtn:hover{background:rgba(57,208,216,.15);box-shadow:0 0 0 1px var(--accent),0 0 12px rgba(57,208,216,.22)}
 .cwvals{margin-top:8px}
 .cwvals .cwstep{margin:12px 0 3px;color:var(--accent);font-weight:600;letter-spacing:.03em}
 .cwvals .cwsha{color:var(--dim);font-weight:400;margin-left:6px;font-size:11px}
 .cwvals .cwerr{color:var(--reject);margin:2px 0}
 .cwvals table{width:100%;border-collapse:collapse}
 .cwvals td{padding:3px 8px;border-bottom:1px solid var(--line);vertical-align:top}
 .cwvals .cwk{color:var(--ink);white-space:nowrap;padding-right:18px}
 .cwvals .cwv{color:#eaf2f9;font-weight:600;text-align:right;word-break:break-all}
 .tzwrap{color:var(--dim);font-size:11px;display:flex;align-items:center;gap:5px}
 .tzwrap select{background:var(--panel);color:var(--ink);border:1px solid var(--line);border-radius:5px;
   font:11px var(--mono);padding:2px 4px}
 #tzlabel{color:var(--dim)}
 .page{padding:16px 18px}
 h1{font-size:15px;color:var(--ink);margin:0 0 12px;letter-spacing:.03em;font-weight:600}
 h2{font-size:10px;color:var(--dim);margin:0;text-transform:uppercase;letter-spacing:.12em;font-weight:600;display:inline}
 section.card{background:var(--panel);border:1px solid var(--line);border-radius:10px;margin:0 0 14px;overflow:hidden;overflow-x:auto}
 section.card>.hd{padding:9px 13px;border-bottom:1px solid var(--line)}
 section.card>.pad{padding:10px 13px}
 section.card table{margin:0}
 .muted{color:var(--dim);text-align:center;padding:18px} .back{font-size:12px;color:var(--dim)}
 .crumb{font-size:12px;color:var(--dim);margin:0 0 10px} .crumb a{color:var(--dim)} .crumb a:hover{color:var(--accent)}
 .layout{display:flex;gap:18px;align-items:flex-start}
 .sidebar{flex:0 0 250px;position:sticky;top:56px} .main{flex:1 1 auto;min-width:0}
 .navsearch,.feedsearch{width:100%;box-sizing:border-box;background:var(--panel);border:1px solid var(--line);border-radius:6px;color:var(--ink);padding:6px 8px;margin:0 0 10px;font:12px var(--mono)}
 .navsearch:focus,.feedsearch:focus{outline:none;border-color:var(--accent)}
 .navsearch::placeholder,.feedsearch::placeholder{color:var(--dim)}
 .navtier{margin-bottom:8px}
 .navhdr{cursor:pointer;color:var(--dim);text-transform:uppercase;font-size:10px;letter-spacing:.12em;font-weight:600;padding:4px 2px;user-select:none}
 .navhdr .caret{display:inline-block;width:12px;color:var(--dim)}
 .navtier.collapsed .navlist{display:none} .navtier.collapsed .caret{transform:rotate(-90deg)}
 .tcount,.navnode .cnt{color:var(--dim)}
 .navlist{display:flex;flex-direction:column;gap:4px;margin-top:4px}
 .navnode{display:flex;align-items:center;gap:6px;background:var(--panel);border:1px solid var(--line);border-radius:6px;padding:5px 8px;color:var(--ink)}
 .navnode:hover{background:var(--panel2);text-decoration:none}
 .navnode .role{margin-left:0} .navnode .cnt{margin-left:auto}
 .navnode .swarn{color:var(--push)}
 .dot{display:inline-block;width:8px;height:8px;border-radius:50%;flex:0 0 8px}
 .dot.up{background:var(--allow)} .dot.down{background:var(--reject)} .dot.stale{background:var(--dim)}
 .navempty,.navlegend{color:var(--dim);font-size:11px;padding:6px 2px}
 .navlegend{display:flex;gap:10px;align-items:center} .navlegend .dot{width:7px;height:7px;flex:0 0 7px}
 @media(max-width:760px){.layout{flex-direction:column}.sidebar{flex:none;width:100%;position:static}.page{padding:12px}}
 table{width:100%;border-collapse:collapse} th,td{text-align:left;padding:5px 8px;border-bottom:1px solid var(--line)}
 td{font-variant-numeric:tabular-nums}
 th{color:var(--dim);font-weight:600;text-transform:uppercase;font-size:10px;letter-spacing:.1em} td.t{color:var(--dim);white-space:nowrap}
 tr:last-child td{border-bottom:0}
 tr.run{cursor:pointer} tr.run:hover td,tr.run:focus-within td{background:var(--panel2)}
 .rowlink{color:inherit;display:block;margin:-5px -8px;padding:5px 8px} .rowlink:hover{text-decoration:none}
 .ok{color:var(--allow)} .no{color:var(--reject)} .warn{color:var(--push)} .role{color:var(--dim)}
 .kv{color:var(--dim);font-size:12px} .kv b{color:var(--ink);font-weight:600} code{color:var(--accent)}
 .meta{display:grid;grid-template-columns:auto 1fr;gap:4px 14px;font-size:12px} .meta .k{color:var(--dim)}
 .badge{display:inline-block;padding:1px 7px;border-radius:6px;font-size:10px;border:1px solid var(--line);color:var(--dim)}
 .badge.b-allow{color:var(--allow);border-color:var(--allow)} .badge.b-push{color:var(--push);border-color:var(--push)}
 .badge.b-reject{color:var(--reject);border-color:var(--reject)}
 .tag-dest{color:var(--destructive);border:1px solid var(--destructive);border-radius:6px;padding:0 6px;font-size:10px;white-space:nowrap}
 .tag-fail{color:var(--reject);border:1px solid var(--reject);border-radius:6px;padding:0 6px;font-size:10px}
 .banner{display:flex;gap:10px;margin:0 0 14px;flex-wrap:wrap}
 .bn{border-radius:8px;padding:9px 14px;font-weight:600;border:1px solid}
 .bn.approval{background:rgba(251,189,35,.08);border-color:var(--push);color:var(--push)}
 .bn.high{background:rgba(192,132,252,.08);border-color:var(--destructive);color:var(--destructive)}
 .bn.reject{background:var(--panel);border-color:var(--line);color:var(--dim)}
 .bn.clear{background:rgba(54,211,153,.07);border-color:var(--allow);color:var(--allow)}
 .pill{display:inline-block;border-radius:6px;padding:1px 7px;font-size:10px;font-weight:600;border:1px solid}
 .pill.approval{border-color:var(--push);color:var(--push)} .pill.high{border-color:var(--destructive);color:var(--destructive)}
 .pill.reject{border-color:var(--line);color:var(--dim)}
 tr.superseded td{opacity:.5} tr.superseded .pill{text-decoration:line-through}
 .fbar{display:flex;gap:8px;align-items:center;flex-wrap:wrap;margin:0 0 10px}
 .fbar .feedsearch{flex:1;min-width:180px;margin:0}
 .fchips{display:flex;gap:5px;flex-wrap:wrap}
 .fchip{font:10px var(--mono);text-transform:uppercase;letter-spacing:.08em;padding:4px 10px;background:var(--panel);
   border:1px solid var(--line);border-radius:6px;color:var(--dim);cursor:pointer}
 .fchip b{font-size:11px;color:var(--ink)} .fchip:hover{color:var(--ink)} .fchip.on{color:var(--accent);border-color:var(--accent)}
 .callout{border:1px solid var(--push);background:rgba(251,189,35,.06);border-radius:10px;padding:12px 14px;margin:0 0 14px}
 .callout b{color:var(--push)} .callout pre{margin:8px 0 0}
 .off{color:var(--reject);font-size:11px} .stalez{color:var(--dim);font-size:11px}
 .hlink{font-size:12px;margin-left:10px}
 .age{color:var(--dim);font-size:11px;white-space:nowrap}
 .gauge{display:flex;align-items:center;gap:8px}
 .gbar{flex:1;min-width:80px;height:10px;background:var(--panel2);border:1px solid var(--line);border-radius:5px;overflow:hidden}
 .gfill{height:100%;background:var(--accent);opacity:.75}
 .glab{min-width:70px;color:var(--dim);font-size:11px}
 .cp{cursor:pointer;border-bottom:1px dashed var(--line)} .cp:hover{border-bottom-color:var(--accent)}
 .cp.copied{color:var(--allow)}
 pre{background:var(--panel2);border:1px solid var(--line);border-radius:6px;padding:10px;overflow:auto;max-height:340px;color:var(--ink);white-space:pre-wrap;word-break:break-word;font-size:11px}
 details{margin:6px 0} summary{cursor:pointer;color:var(--accent);padding:4px 0}
 img{display:block;margin:8px 0}
 .flowbox{background:var(--panel2);border:1px solid var(--line);border-radius:8px;padding:10px;overflow-x:auto}
 .flowbox img{margin:0 auto;max-width:100%}
 html{scrollbar-width:thin;scrollbar-color:#1e2c3d #0a0e14}
 ::-webkit-scrollbar{width:11px;height:11px}
 ::-webkit-scrollbar-track{background:#0a0e14}
 ::-webkit-scrollbar-thumb{background:#1e2c3d;border-radius:6px;border:2px solid #0a0e14}
 ::-webkit-scrollbar-thumb:hover{background:#2a3b52}
"""


def _esc(s):
    return html.escape(str(s))


def _ts(ts):
    """A timestamp rendered in the operator's CHOSEN timezone (default: their browser-local tz). The server
    emits the stored UTC instant in `data-utc`; the page's tz control rewrites the visible text client-side,
    so no node clock or server locale is assumed (UTC is the wire format, not the display)."""
    iso = str(ts or "")
    return f'<span class="ts" data-utc="{_esc(iso)}">{_esc(iso[:19])}</span>'


# The favicon is an inline data URI (no asset to serve); it flips to the alert glyph server-side whenever
# approvals are pending, so a backgrounded tab works as the pager.
_FAV = ("data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 16 16'%3E"
        "%3Crect width='16' height='16' rx='3' fill='%230a0e14'/%3E"
        "%3Cpath d='M4 5h8M4 8h8M4 11h5' stroke='{c}' stroke-width='2' stroke-linecap='round'/%3E%3C/svg%3E")

# A fleet-wide DISPLAY-timezone control (in the topbar, on every page). The instant on the wire stays UTC;
# only the rendering changes. The choice persists in localStorage and survives the page's auto-refresh.
_TZSEL = ('<span class="tzwrap">🕐 <select id="tzsel" aria-label="display timezone" title="display timezone">'
          '<option value="local">Local</option><option value="UTC">UTC</option>'
          '<option value="America/Los_Angeles">US/Pacific</option>'
          '<option value="America/Denver">US/Mountain</option>'
          '<option value="America/Chicago">US/Central</option>'
          '<option value="America/New_York">US/Eastern</option>'
          '<option value="America/Sao_Paulo">São Paulo</option>'
          '<option value="Europe/London">London</option><option value="Europe/Berlin">Berlin</option>'
          '<option value="Asia/Kolkata">India</option><option value="Asia/Shanghai">China</option>'
          '<option value="Asia/Tokyo">Japan</option><option value="Australia/Sydney">Sydney</option>'
          '</select> <span id="tzlabel"></span></span>')

# The one shared client script. Each feature wires itself only when its elements exist on the page:
#   tz        — rewrite every .ts span from its data-utc into the chosen display timezone (key cw-tz)
#   ages      — render .age spans as a relative age from the same data-utc (triage: new vs stale)
#   nav/feed  — client-side filters for the node sidebar + the run feed, persisted under cw-nav
#   copy      — click/Enter on a .cp element copies its data-full (the untruncated hash/id)
#   refresh   — the POLITE reload: fires only when it cannot stomp the operator (never while the tab is
#               hidden or paused, an input has focus, text is selected, a <details> is open, or the pointer
#               is over a run row — the misclick window on a shifting table). <noscript> falls back to the
#               plain meta refresh.
_PAGEJS = """
<script>(function(){
"use strict";
var TZKEY='cw-tz', tzsel=document.getElementById('tzsel');
function tzZone(v){return v==='local'?Intl.DateTimeFormat().resolvedOptions().timeZone:v;}
function tzFmt(u,z){if(!u)return u;var s=/(?:Z|[+-]\\d\\d:?\\d\\d)$/.test(u)?u:u+'Z';
  var d=new Date(s);if(isNaN(d.getTime()))return u.slice(0,19);
  try{return d.toLocaleString('sv-SE',{timeZone:z});}catch(e){return u.slice(0,19);}}
function tzApply(){var v=localStorage.getItem(TZKEY)||'local',z=tzZone(v);
  document.querySelectorAll('.ts').forEach(function(e){var u=e.getAttribute('data-utc');if(u)e.textContent=tzFmt(u,z);});
  var l=document.getElementById('tzlabel');if(l)l.textContent=z;if(tzsel)tzsel.value=v;}
if(tzsel)tzsel.addEventListener('change',function(){localStorage.setItem(TZKEY,tzsel.value);tzApply();});
tzApply();
function parseUtc(u){var s=/(?:Z|[+-]\\d\\d:?\\d\\d)$/.test(u)?u:u+'Z';var t=new Date(s).getTime();return isNaN(t)?null:t;}
document.querySelectorAll('.age').forEach(function(e){var u=e.getAttribute('data-utc');if(!u)return;var t=parseUtc(u);if(t==null)return;
  var m=Math.max(0,Math.round((Date.now()-t)/60000));
  e.textContent=m<1?'just now':(m<60?m+'m ago':(m<1440?Math.round(m/60)+'h ago':Math.round(m/1440)+'d ago'));});
var asf=document.getElementById('asofts');
if(asf){var t=parseUtc(asf.getAttribute('data-utc')||'');if(t!=null&&Date.now()-t>60000)asf.classList.add('lag');}
var NKEY='cw-nav', ns={};
try{ns=JSON.parse(localStorage.getItem(NKEY))||{}}catch(e){}
function nsave(){try{localStorage.setItem(NKEY,JSON.stringify(ns))}catch(e){}}
var box=document.getElementById('navsearch');
if(box&&ns.q)box.value=ns.q;
document.querySelectorAll('.navtier').forEach(function(t){
  if(ns.collapsed&&ns.collapsed[t.getAttribute('data-tier')])t.classList.add('collapsed');});
function navFilter(){var q=(box?box.value:'').trim().toLowerCase(),shown=0;
  document.querySelectorAll('.navtier').forEach(function(t){var any=false;
    t.querySelectorAll('.navnode').forEach(function(n){
      var hit=!q||(n.getAttribute('data-search')||'').indexOf(q)>=0;
      n.style.display=hit?'':'none';if(hit){any=true;shown++;}});
    t.style.display=(!q||any)?'':'none';});
  var none=document.getElementById('navnone');if(none)none.style.display=(q&&!shown)?'':'none';}
if(box){box.addEventListener('input',function(){ns.q=box.value;nsave();navFilter();});
  box.addEventListener('keydown',function(e){if(e.key==='Escape'){box.value='';ns.q='';nsave();navFilter();}});}
document.querySelectorAll('.navhdr').forEach(function(h){
  h.addEventListener('click',function(){var t=h.parentNode;t.classList.toggle('collapsed');
    ns.collapsed=ns.collapsed||{};ns.collapsed[h.getAttribute('data-tier')]=t.classList.contains('collapsed');nsave();});});
navFilter();
var fbox=document.getElementById('feedsearch'), fchips=document.querySelectorAll('.fchip');
function feedFilter(){if(!fbox&&!fchips.length)return;
  var q=(fbox?fbox.value:'').trim().toLowerCase(),c=ns.fd||'all',shown=0,rows=0;
  document.querySelectorAll('tr.run[data-search]').forEach(function(r){rows++;
    var okq=!q||(r.getAttribute('data-search')||'').indexOf(q)>=0;
    var okc=c==='all'||r.getAttribute('data-risk')===c||r.getAttribute('data-decision')===c;
    r.style.display=(okq&&okc)?'':'none';if(okq&&okc)shown++;});
  var active=q||c!=='all';                                      // only cry 'no match' when a filter is actually on
  var none=document.getElementById('feednone');if(none)none.style.display=(active&&rows&&!shown)?'':'none';
  fchips.forEach(function(b){b.classList.toggle('on',(b.getAttribute('data-f')||'all')===c);});}
function feedReset(){if(fbox){fbox.value='';ns.fq='';}ns.fd='all';nsave();feedFilter();}
if(fbox){if(ns.fq)fbox.value=ns.fq;
  fbox.addEventListener('input',function(){ns.fq=fbox.value;nsave();feedFilter();});
  fbox.addEventListener('keydown',function(e){if(e.key==='Escape')feedReset();});}
fchips.forEach(function(b){b.addEventListener('click',function(){ns.fd=b.getAttribute('data-f');nsave();feedFilter();});});
feedFilter();
document.addEventListener('keydown',function(e){
  if(e.key!=='/'||e.ctrlKey||e.metaKey||e.altKey)return;
  var a=document.activeElement;if(a&&/^(INPUT|SELECT|TEXTAREA)$/.test(a.tagName))return;
  var t=fbox||box;if(t){e.preventDefault();t.focus();}});
// Whole-row navigation by delegation (not an inline onclick): keeps run_id/actor OUT of an inline JS string
// (no HTML-attribute JS-context XSS from a hostile node's run_id) and respects modifier/middle clicks — a
// cmd/ctrl/shift/middle click, or a click on the row's real <a>/.cp, is left to the browser (open-in-tab, copy).
document.addEventListener('click',function(e){
  if(e.button!==0||e.metaKey||e.ctrlKey||e.shiftKey||e.altKey)return;
  if(e.target.closest('a,button,input,select,textarea,.cp'))return;
  var tr=e.target.closest('tr.run[data-href]');if(!tr)return;
  var s=window.getSelection&&window.getSelection();if(s&&String(s).length)return;
  location=tr.getAttribute('data-href');});
function doCopy(el){var v=el.getAttribute('data-full')||el.textContent;
  function done(){var old=el.textContent;el.textContent='copied';el.classList.add('copied');
    setTimeout(function(){el.textContent=old;el.classList.remove('copied');},900);}
  function fallback(){var ta=document.createElement('textarea');ta.value=v;ta.style.position='fixed';ta.style.opacity='0';
    document.body.appendChild(ta);ta.select();try{document.execCommand('copy');done();}catch(e){}document.body.removeChild(ta);}
  if(navigator.clipboard&&window.isSecureContext)navigator.clipboard.writeText(v).then(done,fallback);else fallback();}
document.querySelectorAll('.cp').forEach(function(el){
  el.addEventListener('click',function(){doCopy(el);});
  el.addEventListener('keydown',function(e){if(e.key==='Enter'||e.key===' '){e.preventDefault();doCopy(el);}});});
var R=Number(document.body.getAttribute('data-refresh')||0), pb=document.getElementById('pausebtn'), PKEY='cw-pause';
function paused(){return localStorage.getItem(PKEY)==='1';}
function pupd(){if(!pb)return;pb.textContent=paused()?'▶':'⏸';pb.classList.toggle('on',paused());
  pb.title=paused()?'auto-refresh paused — click to resume':'auto-refresh on — click to pause';}
if(pb)pb.addEventListener('click',function(){localStorage.setItem(PKEY,paused()?'0':'1');pupd();});
pupd();
function busy(){if(paused()||document.hidden)return true;
  var a=document.activeElement;if(a&&/^(INPUT|SELECT|TEXTAREA)$/.test(a.tagName))return true;
  var s=window.getSelection&&window.getSelection();if(s&&String(s).length)return true;
  if(document.querySelector('details[open]'))return true;
  return false;}
if(R>0)setInterval(function(){if(!busy())location.reload();},R*1000);
})();</script>
"""


def _header(nav=None, risk_n=0, as_of=None, refresh=None):
    """The persistent topbar: brand, the three destinations, the pending-approval chip, the snapshot stamp,
    the pause toggle (only on auto-refreshing pages) and the display-timezone control."""
    on = ' class="on"'
    links = "".join(f'<a href="{href}"{on if key == nav else ""}>{label}</a>'
                    for key, href, label in (("board", "/", "board"), ("risk", "/risk", "risk"),
                                             ("accounting", "/accounting", "accounting")))
    chip = (f'<a class="riskchip" href="/risk#approval">⚠ {risk_n} approval{"s" if risk_n != 1 else ""}</a>'
            if risk_n else "")
    asof = (f'<span class="asof">updated <span class="ts" id="asofts" data-utc="{_esc(as_of)}">'
            f'{_esc(str(as_of)[:19])}</span></span>' if as_of else "")
    pause = ('<button class="pausebtn" id="pausebtn" type="button" title="pause auto-refresh">⏸</button>'
             if refresh else "")
    return ('<header class="top"><span class="brand">cyberware · <b>fleet</b> control</span>'
            f'<nav class="topnav">{links}</nav>{chip}<span class="grow"></span>{asof}{pause}{_TZSEL}</header>')


def _page(title, content, refresh=None, nav=None, risk_n=0, as_of=None):
    noscript = f'<noscript><meta http-equiv="refresh" content="{refresh}"></noscript>' if refresh else ""
    fav = _FAV.format(c="%23f87272" if risk_n else "%2339d0d8")
    full_title = (f"[{risk_n} approval{'s' if risk_n != 1 else ''}] " if risk_n else "") + title
    body_attr = f' data-refresh="{refresh}"' if refresh else ""
    return ('<!doctype html><html lang="en"><head><meta charset="utf-8">'
            '<meta name="viewport" content="width=device-width, initial-scale=1">'
            f'<link rel="icon" href="{fav}">' + noscript + "<title>" + _esc(full_title)
            + "</title><style>" + _STYLE + "</style></head><body" + body_attr + ">"
            + _header(nav, risk_n, as_of, refresh) + '<div class="page">' + content + "</div>"
            + _PAGEJS + "</body></html>")


def _banner(risk):
    """The high-risk / needs-approval banner — the first thing the operator sees, fleet-wide. Superseded
    approvals (a later approved run answered the claim) are excluded from the actionable count."""
    na = _risk_pending(risk)
    superseded = len(risk.get("approval", [])) - na
    hi, rj = (len(risk.get(k, [])) for k in ("high", "reject"))
    items = []
    if na:
        items.append(f'<a class="bn approval" href="/risk#approval">⚠ {na} NEED APPROVAL</a>')
    if hi:
        items.append(f'<a class="bn high" href="/risk#high">{hi} high-risk ran</a>')
    if rj:
        items.append(f'<a class="bn reject" href="/risk#reject">{rj} rejected</a>')
    if not items:
        items.append('<span class="bn clear">✓ no high-risk or pending-approval work</span>')
    elif not na and superseded:
        items.insert(0, '<span class="bn clear">✓ approval queue clear</span>')
    return '<div class="banner">' + "".join(items) + "</div>"


def _notfound(msg, back="/", back_label="← fleet"):
    """A styled 404 with a way back (the bare-string dead ends used to strand the operator)."""
    return _page("404", f'<p class="crumb"><a href="{_esc(back)}">{_esc(back_label)}</a></p>'
                 f'<p class="muted">{_esc(msg)}</p>')


_DECISION_CLS = {"allow": "b-allow", "reject": "b-reject", "push_back": "b-push"}


def _badge(decision):
    """The one decision→badge mapping every page shares (same atoms as the per-node monitor SPA)."""
    return f'<span class="badge {_DECISION_CLS.get(decision, "")}">{_esc(decision or "?")}</span>'


def _dest_tag(d):
    return ' <span class="tag-dest" title="destructive claim">D</span>' if d.get("destructive") else ""


def _as_list(v):
    """Coerce a node-supplied field to a list of strings — a malformed node sending a scalar (needs_approve=5)
    or a non-string element must never crash a render (`", ".join` over a scalar/int raises)."""
    if v is None:
        return []
    return [str(x) for x in v] if isinstance(v, (list, tuple)) else [str(v)]


def _cp(value, n=16, title="click to copy"):
    """A truncated hash/id that copies its FULL value on click (all ids/hashes — value-free by construction)."""
    s = str(value or "")
    if not s:
        return "—"
    shown = _esc(s[:n]) + ("…" if len(s) > n else "")
    return (f'<code class="cp" tabindex="0" role="button" data-full="{_esc(s)}" '
            f'title="{_esc(title)}">{shown}</code>')


def _risk_pill(d):
    c = classify_risk(d)
    if not c:
        return ""
    label = "superseded" if (c == "approval" and d.get("_superseded")) else c
    return f'<span class="pill {c}">{label}</span>'


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
    """The hierarchical, searchable node nav: a filter box + nodes grouped under collapsible fleet-tiers.
    Each node row carries its liveness dot, run count, and — when the last mirror sweep errored — an amber ⚠
    whose tooltip says why (an auth-rotted token looks 'up' on /health; the sweep error is what tells)."""
    parts = ['<input class="navsearch" id="navsearch" placeholder="filter nodes… ( / )" autocomplete="off" '
             'aria-label="filter nodes">']
    if not results:
        parts.append('<div class="navempty">no nodes in the roster — add nodes to fleet.json</div>')
    for ft, nodes in _node_groups(results):
        label = _esc(ft if ft is not None else "untiered")
        items = []
        for r in nodes:
            reach = r.get("reachable")
            dot = "up" if reach else ("down" if reach is False else "stale")
            live = {"up": "live", "down": "unreachable", "stale": "not probed yet"}[dot]
            name, role = _esc(r.get("name", "?")), _esc(r.get("role") or "")
            search = _esc(" ".join(str(x) for x in (r.get("name"), r.get("role"), ft) if x).lower())
            err = r.get("sweep_error")
            warn = f' <span class="swarn" title="last mirror sweep: {_esc(err)}">⚠</span>' if err else ""
            items.append(f'<a class="navnode" data-search="{search}" href="/node/{name}" '
                         f'title="{name} — {live}{" · sweep: " + _esc(err) if err else ""}">'
                         f'<span class="dot {dot}"></span><b>{name}</b>{warn}'
                         f'<span class="role">{role}</span><span class="cnt" title="runs mirrored">{r.get("count", 0)}</span></a>')
        parts.append(f'<div class="navtier" data-tier="{label}">'
                     f'<div class="navhdr" data-tier="{label}"><span class="caret">▾</span>{label} '
                     f'<span class="tcount">{len(nodes)}</span></div>'
                     f'<div class="navlist">{"".join(items)}</div></div>')
    parts.append('<div class="navempty" id="navnone" style="display:none">no nodes match — Esc clears</div>')
    parts.append('<div class="navlegend"><span class="dot up"></span>live <span class="dot down"></span>down '
                 '<span class="dot stale"></span>not probed</div>')
    return '<aside class="sidebar">' + "".join(parts) + '</aside>'


def _feed_row(x):
    """One merged-feed row: a real link on the `when` cell (middle-click/keyboard friendly; the whole row
    stays a click target) + value-free filter haystack attributes for the client-side filter bar."""
    rid = _esc(x.get("run_id") or "")
    node = _esc(x["node"])
    what = _esc(f"{x.get('skill')}/{x.get('perk')}") + _dest_tag(x)
    if x.get("failed"):
        what += ' <span class="tag-fail" title="a step errored">failed</span>'
    hay = _esc(" ".join(str(v) for v in (x.get("node"), x.get("role"), x.get("principal"), x.get("skill"),
                                         x.get("perk"), x.get("decision"), x.get("run_id"),
                                         str(x.get("ts") or "")[:10]) if v).lower())
    risk_c = classify_risk(x) or ""
    if risk_c == "approval" and x.get("_superseded"):        # answered — don't let it match the 'needs approval' chip
        risk_c = ""
    return (f'<tr class="run" data-search="{hay}" data-decision="{_esc(x.get("decision"))}" data-risk="{risk_c}" '
            f'data-href="/run/{node}/{rid}">'
            f'<td class="t"><a class="rowlink" href="/run/{node}/{rid}">{_ts(x.get("ts"))}</a></td>'
            f'<td><b>{node}</b> <span class="role">{_esc(x["role"])}</span></td>'
            f'<td>{_esc(x.get("principal"))}</td><td>{what}</td>'
            f'<td>{_esc(x.get("authority") or "—")}</td>'
            f'<td>{_badge(x.get("decision"))} {_risk_pill(x)}</td></tr>')


def _feed_filterbar(window):
    """The run-feed filter: free text + decision/risk chips with live counts, all client-side over the
    rendered window (values persist in localStorage, so the filter survives the auto-refresh)."""
    n = {"all": len(window), "allow": 0, "approval": 0, "high": 0, "reject": 0}
    for x in window:
        c = classify_risk(x)
        if c == "approval" and x.get("_superseded"):        # answered — matches the data-risk the row carries
            c = None
        if c in n:
            n[c] += 1
        if x.get("decision") == "allow":
            n["allow"] += 1
    chips = "".join(f'<button class="fchip" type="button" data-f="{key}">{label} <b>{n[key]}</b></button>'
                    for key, label in (("all", "all"), ("allow", "allow"), ("approval", "needs approval"),
                                       ("high", "high-risk"), ("reject", "reject")))
    return ('<div class="fbar"><input class="feedsearch" id="feedsearch" '
            'placeholder="filter runs — node, principal, skill, run id… ( / )" autocomplete="off" '
            f'aria-label="filter runs"><div class="fchips">{chips}</div></div>')


def render_html(results, feed, risk, refresh=5, as_of=None):
    window = feed[:300]
    rows = [_feed_row(x) for x in window]
    body = "".join(rows) or '<tr><td colspan="6" class="muted">no runs mirrored yet — they appear as nodes run governed work</td></tr>'
    body += '<tr id="feednone" style="display:none"><td colspan="6" class="muted">no runs match — Esc clears the filter</td></tr>'
    up = sum(1 for r in results if r.get("reachable"))
    shown = f"showing latest {len(window)} of {len(feed)}" if len(feed) > len(window) else f"{len(feed)} runs"
    content = ('<h1>who fired what, where — the fleet\'s value-free ledgers '
               '<a class="hlink" href="/accounting">accounting →</a></h1>'
               f'<div class="layout">{_sidebar(results)}'
               f'<section class="main">{_banner(risk)}{_feed_filterbar(window)}'
               f'<section class="card"><table><thead><tr><th>when</th><th>where (node)</th><th>who (principal)</th>'
               f'<th>what (skill/perk)</th><th title="which limb signed the steps (exod = confined body)">exec</th>'
               f'<th>outcome</th></tr></thead><tbody>{body}</tbody></table></section>'
               f'<p class="muted">click a run for its ledger · central mirror · {shown} · '
               f'{up}/{len(results)} nodes live · auto-refresh {refresh}s (pausable — ⏸ above)</p>'
               '</section></div>')
    return _page("cyberware — fleet control", content, refresh, nav="board",
                 risk_n=_risk_pending(risk), as_of=as_of)


def render_risk(feed, risk, refresh=5, as_of=None):
    """The /risk drill-down: every needs-approval / high-risk / rejected run across the fleet, grouped.
    Approval rows show their age and the approve-token list (value-free ids — WHAT to approve); entries a
    later approved run answered sink to the bottom of their section, dimmed as `superseded`."""
    def row(x, extra=""):
        rid, node = _esc(x.get("run_id") or ""), _esc(x["node"])
        sup = " superseded" if x.get("_superseded") else ""
        return (f'<tr class="run{sup}" data-href="/run/{node}/{rid}">'
                f'<td class="t"><a class="rowlink" href="/run/{node}/{rid}">{_ts(x.get("ts"))}</a></td>'
                f'<td class="age" data-utc="{_esc(x.get("ts") or "")}"></td><td><b>{node}</b></td>'
                f'<td>{_esc(x.get("principal"))}</td><td>{_esc(x.get("skill"))}/{_esc(x.get("perk"))}{_dest_tag(x)}</td>'
                f'<td>{extra}</td><td>{_risk_pill(x)}</td></tr>')

    def section(key, title, hint, extra=lambda x: ""):
        items = risk.get(key, [])
        live = [x for x in items if not x.get("_superseded")]
        done = [x for x in items if x.get("_superseded")]
        rows = "".join(row(x, extra(x)) for x in live + done)
        rows = rows or '<tr><td colspan="7" class="muted">none</td></tr>'
        count = f"{len(live)}" + (f" + {len(done)} superseded" if done else "")
        return (f'<section class="card"><div class="hd"><h2 id="{key}">{title} ({count})</h2></div>'
                f'<div class="pad"><p class="kv" style="margin-top:0">{hint}</p></div>'
                f'<table><thead><tr><th>when</th><th>age</th><th>where</th><th>who</th><th>what</th>'
                f'<th>approve</th><th>risk</th></tr></thead><tbody>{rows}</tbody></table></section>')

    def approve_of(x):
        toks = _as_list(x.get("needs_approve") or x.get("approved"))
        return f'<code>{_esc(", ".join(toks))}</code>' if toks else "—"

    content = ('<h1>high-risk &amp; approval queue</h1>' + _banner(risk)
               + section("approval", "needs approval",
                         "destructive claims govd PUSHED BACK — re-submit the claim with the listed approve "
                         "tokens to proceed (govd never auto-approves). `superseded` = a later approved run "
                         "already answered this claim.", approve_of)
               + section("high", "high-risk (ran)", "destructive operations that were approved and executed — audit them.")
               + section("reject", "rejected", "claims govd refused (structural problems)."))
    return _page("fleet — risk queue", content, refresh, nav="risk",
                 risk_n=_risk_pending(risk), as_of=as_of)


def _spend_rollup(feed):
    """Per-actor CREDIT spend across the fleet, from the mirrored value-free `cost`. Returns rows sorted by
    spend (desc), each {actor, spent, spent24, allows, runs, nodes, last_ts, _spent}. `spent24` is the last
    24 hours — the rate answers 'who is burning credits NOW' where the all-time bar cannot."""
    from infra.settle.money import Money
    cutoff = time.strftime("%Y-%m-%dT%H:%M:%S", time.gmtime(time.time() - 86400))
    agg = {}
    for x in feed:
        a = x.get("principal") or "?"
        e = agg.setdefault(a, {"actor": a, "_spent": Money.zero("CREDITS"), "_spent24": Money.zero("CREDITS"),
                               "allows": 0, "runs": 0, "nodes": set(), "last_ts": ""})
        e["runs"] += 1
        e["nodes"].add(x.get("node"))
        e["last_ts"] = max(e["last_ts"], str(x.get("ts") or ""))
        if x.get("decision") == "allow" and x.get("cost"):
            try:
                m = Money(str(x["cost"]), "CREDITS")
                e["_spent"] = e["_spent"] + m
                if str(x.get("ts") or "") >= cutoff:
                    e["_spent24"] = e["_spent24"] + m
                e["allows"] += 1
            except (TypeError, ValueError):
                pass
    rows = [{"actor": e["actor"], "spent": str(e["_spent"].amount), "spent24": str(e["_spent24"].amount),
             "allows": e["allows"], "runs": e["runs"], "nodes": len(e["nodes"]), "last_ts": e["last_ts"],
             "_spent": e["_spent"]} for e in agg.values()]
    rows.sort(key=lambda r: r["_spent"].amount, reverse=True)
    return rows


def render_accounting(feed, refresh=5, as_of=None):
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
        actor = _esc(r["actor"])
        body.append(f'<tr class="run" data-href="/principal/{actor}">'
                    f'<td><a class="rowlink" href="/principal/{actor}"><b>{actor}</b></a></td>'
                    f'<td><div class="gauge" role="img" aria-label="{actor} spent {_esc(r["spent"])} credits">'
                    f'<div class="gbar"><div class="gfill" style="width:{pct}%"></div></div>'
                    f'<span class="glab">{_esc(r["spent"])}</span></div></td>'
                    f'<td>{_esc(r["spent24"])}</td>'
                    f'<td>{r["allows"]}/{r["runs"]}</td><td>{r["nodes"]}</td>'
                    f'<td class="t">{_ts(r["last_ts"])}</td></tr>')
    rows_html = "".join(body) or '<tr><td colspan="6" class="muted">no metered runs yet</td></tr>'
    content = ('<h1>fleet accounting — credit spend by actor</h1>'
               f'<p class="kv">total spent across the fleet: <b>{_esc(str(total.amount))}</b> CREDITS · '
               f'{len(rows)} actors · click an actor for their account · the per-node allowance/balance gauge '
               f'is on each node\'s monitor (it holds the budget ledger).</p>'
               '<section class="card"><table><thead><tr><th>actor</th><th>spend (relative)</th>'
               '<th title="credits spent in the last 24 hours">24h</th><th>allowed/runs</th><th>nodes</th>'
               f'<th>last active</th></tr></thead><tbody>{rows_html}</tbody></table></section>')
    return _page("fleet — accounting", content, refresh, nav="accounting",
                 risk_n=_risk_pending(mark_superseded(feed, risk_summary(feed))), as_of=as_of)


def render_principal(actor, feed, refresh=5, as_of=None):
    """The individual ACCOUNTANT page: one actor's runs + credit spend across the fleet. The totals are
    computed over the actor's FULL feed — only the rendered rows are windowed (they must agree with
    /accounting's rollup, which never windows)."""
    from infra.settle.money import Money
    mine = [x for x in feed if (x.get("principal") or "?") == actor]
    spent = Money.zero("CREDITS")
    for x in mine:
        if x.get("decision") == "allow" and x.get("cost"):
            try:
                spent = spent + Money(str(x["cost"]), "CREDITS")
            except (TypeError, ValueError):
                pass
    window = sorted(mine, key=lambda d: d.get("ts") or "", reverse=True)[:300]
    rows = []
    for x in window:
        node, rid = _esc(x["node"]), _esc(x.get("run_id") or "")
        rows.append(f'<tr class="run" data-href="/run/{node}/{rid}">'
                    f'<td class="t"><a class="rowlink" href="/run/{node}/{rid}">{_ts(x.get("ts"))}</a></td>'
                    f'<td>{node}</td>'
                    f'<td>{_esc(x.get("skill"))}/{_esc(x.get("perk"))}{_dest_tag(x)}</td><td>{_esc(x.get("cost") or "—")}</td>'
                    f'<td>{_badge(x.get("decision"))}</td></tr>')
    rows_html = "".join(rows) or '<tr><td colspan="5" class="muted">no runs</td></tr>'
    shown = f"showing newest {len(window)} of {len(mine)} runs" if len(mine) > len(window) else f"{len(mine)} runs"
    content = (f'<p class="crumb"><a href="/accounting">accounting</a> / {_esc(actor)}</p>'
               f'<h1>{_esc(actor)} — credit account</h1>'
               f'<p class="kv">spent across the fleet: <b>{_esc(str(spent.amount))}</b> CREDITS · {shown}</p>'
               '<section class="card"><table><thead><tr><th>when</th><th>node</th><th>what</th><th>cost</th>'
               f'<th>outcome</th></tr></thead><tbody>{rows_html}</tbody></table></section>')
    return _page(f"{_esc(actor)} — account", content, refresh, nav="accounting", as_of=as_of,
                 risk_n=_risk_pending(mark_superseded(feed, risk_summary(feed))))


def render_node(node, summary, refresh=5, as_of=None):
    """Per-node board, rendered from the node's MIRRORED runs (+ live health overlay)."""
    name = _esc(node.get("name"))
    h = summary.get("health") or {}
    reach = summary.get("reachable")
    runs = sorted(summary.get("index", {}).values(), key=lambda d: d.get("ts") or "", reverse=True)
    rows = []
    for d in runs:
        rid = _esc(d.get("run_id") or "")
        rows.append(f'<tr class="run" data-href="/run/{name}/{rid}">'
                    f'<td class="t"><a class="rowlink" href="/run/{name}/{rid}">{_ts(d.get("ts"))}</a></td>'
                    f'<td>{_esc(d.get("principal", "?"))}</td>'
                    f'<td>{_esc(d.get("skill"))}/{_esc(d.get("perk"))}{_dest_tag(d)}</td>'
                    f'<td>{_esc(d.get("authority") or "—")}</td>'
                    f'<td>{_badge(d.get("decision"))} {_risk_pill(d)}</td></tr>')
    tbody = "".join(rows) or '<tr><td colspan="5" class="muted">no runs mirrored for this node yet</td></tr>'
    livetag = "" if reach is None else ('<span class="ok">live</span>' if reach else '<span class="off">OFFLINE — showing the central mirror</span>')
    err = summary.get("sweep_error")
    errline = f' · last sweep <span class="warn">{_esc(err)}</span>' if err else ""
    content = (f'<p class="crumb"><a href="/">fleet</a> / {name} (central mirror)</p>'
               f'<h1>{name} <span class="role">{_esc(node.get("role", "-"))}</span> {livetag}</h1>'
               f'<p class="kv">mode <b>{_esc(h.get("mode", "?"))}</b> · exec_mode <b>{_esc(h.get("exec_mode", "?"))}</b> · '
               f'exod_attached <b>{_esc(h.get("exod_attached", "?"))}</b> · runs <b>{_esc(h.get("runs", "?"))}</b> · '
               f'chip {_cp(h.get("chip_sha") or "?")} · <a href="/node/{name}">live monitor ↗</a>{errline}</p>'
               f'<section class="card"><div class="hd"><h2>runs ({len(runs)} mirrored — durable, survives the node)</h2></div>'
               f'<table><thead><tr><th>when</th><th>who</th>'
               f'<th>what</th><th>exec</th><th>outcome</th></tr></thead><tbody>{tbody}</tbody></table></section>')
    return _page(f"{node.get('name')} — node board", content, refresh, as_of=as_of)


def _details(summary, inner):
    return f'<details><summary>{summary}</summary>{inner}</details>'


def _card(title, inner, hd_extra=""):
    return (f'<section class="card"><div class="hd"><h2>{title}</h2>{hd_extra}</div>'
            f'<div class="pad">{inner}</div></section>')


def _run_live(detail):
    """Whether the record can still change (an allowed run with steps not yet resulted). push_back and reject
    are immutable ledger records — the answer arrives as a NEW run — so their pages stay static. A FAILED run is
    terminal too: govd blocks every downstream step once one errors, so its results never reach len(seq); keying
    'live' off the count alone would reload that page every refresh forever, so a failed/errored run is static."""
    if not detail or detail.get("decision") != "allow" or detail.get("failed"):
        return False
    results = [e for e in detail.get("events", []) if e.get("type") == "step_result"]
    if any(e.get("status") != "ok" for e in results):
        return False                                             # an errored step is terminal — govd stops here
    done = {e.get("step") for e in results}
    return len(done) < len(detail.get("seq") or [])


def _values_reveal_script():
    """The reveal button's client script: fetch the node-proxied /monitor/values/<run_id> and render each
    step's decrypted inputs. EVERY node-supplied string is written via textContent (never innerHTML) — the
    inline-onclick / raw-interpolation XSS sink is deliberately avoided (see the fleetdash UX pass)."""
    return ('<script>(function(){'
            'var b=document.getElementById("cw-reveal");if(!b)return;'
            'b.addEventListener("click",function(){'
            'var out=document.getElementById("cw-values");out.textContent="loading…";'
            'fetch("/proxy/"+b.dataset.node+"/monitor/values/"+b.dataset.run)'
            '.then(function(r){return r.json()}).then(function(d){'
            'out.textContent="";var steps=(d&&d.steps)||[];'
            'if(!steps.length){out.textContent="no recorded values for this run";return}'
            'steps.forEach(function(s){'
            'var h=document.createElement("div");'
            'var t=document.createElement("div");t.className="cwstep";'
            't.textContent="step "+s.step;'
            'var sh=document.createElement("span");sh.className="cwsha";'
            'sh.textContent=(s.values_sha||"").slice(0,16);t.appendChild(sh);h.appendChild(t);'
            'if(s.error){var er=document.createElement("div");er.className="cwerr";'
            'er.textContent="decrypt error: "+s.error;h.appendChild(er)}'
            'var tbl=document.createElement("table");var body=document.createElement("tbody");'
            'var vv=s.values||{};'
            'Object.keys(vv).sort().forEach(function(k){var tr=document.createElement("tr");'
            'var kd=document.createElement("td");kd.className="cwk";kd.textContent=k;'
            'var vd=document.createElement("td");vd.className="cwv";vd.textContent=String(vv[k]);'
            'tr.appendChild(kd);tr.appendChild(vd);'
            'body.appendChild(tr)});tbl.appendChild(body);h.appendChild(tbl);out.appendChild(h)})'
            '}).catch(function(e){out.textContent="fetch failed: "+e})});'
            '})();</script>')


def render_run(name, run_id, detail, has_svg=False, refresh=None):
    """Per-run LEDGER INSPECTION — local-monitor parity from the durable mirror: the full value-free record
    (claim + approval, the step plan, the event chain, plan + closure pins, the model-check + provenance) + the
    blueprint/oversight FLOW svg + a raw-JSON view. Fully inspectable even when the node is OFFLINE. Ordered
    for triage: what is it → what to do about it → how it went → the evidence."""
    crumb = (f'<p class="crumb"><a href="/">fleet</a> / <a href="/mnode/{_esc(name)}">{_esc(name)}</a> / '
             f'run {_esc(str(run_id)[:16])}</p>')
    if not detail:
        return _page("run", crumb + f'<h1>run {_esc(run_id)}</h1>'
                     '<p class="muted">not in the central mirror (the node may not have run it, or the mirror has not polled it yet)</p>',
                     refresh)
    rid, node_e = _esc(run_id), _esc(detail.get("_node", name))

    by_step = {e.get("step"): e for e in detail.get("events", []) if e.get("type") == "step_result"}
    granted = {e.get("step") for e in detail.get("events", []) if e.get("type") == "granted"}
    srows = []
    any_values = False
    for i, tool in enumerate(detail.get("seq", []), 1):
        e = by_step.get(str(i))
        state = ("ok" if e and e.get("status") == "ok" else "error" if e
                 else "granted" if str(i) in granted else "pending")
        cls = {"ok": "ok", "error": "no", "granted": "warn"}.get(state, "")
        vsha = (e or {}).get("values_sha")
        any_values = any_values or bool(vsha)
        srows.append(f'<tr><td>{i}</td><td>{_esc(tool)}</td><td>{_esc((e or {}).get("authority", "—"))}</td>'
                     f'<td>{_esc((e or {}).get("exit", "—"))}</td><td class="{cls}">{_esc(state)}</td>'
                     f'<td class="t">{_cp(vsha, 16) if vsha else "—"}</td></tr>')
    steps = "".join(srows) or '<tr><td colspan="6" class="muted">no steps declared</td></tr>'

    def ev_note(e):
        note = e.get("reason") or ""
        return f' <span class="role">{_esc(note)}</span>' if note else ""

    chain = "".join(                                          # the event chain — the ledger itself
        f'<tr><td>{_esc(e.get("type"))}</td><td>{_esc(e.get("step", "—"))}</td>'
        f'<td>{_esc(e.get("status", "—"))}{ev_note(e)}</td><td>{_esc(e.get("authority", "—"))}</td>'
        f'<td>{_cp(e.get("exod_keyid") or e.get("keyid"), 18)}</td>'
        f'<td class="t">{_ts(e.get("ts"))}</td></tr>'
        for e in detail.get("events", [])) or '<tr><td colspan="6" class="muted">no events recorded</td></tr>'

    snip = detail.get("snippet_shas") or {}
    sniprows = "".join(f'<tr><td>{_esc(k)}</td><td>{_cp(v, 32)}</td></tr>'
                       for k, v in snip.items()) or '<tr><td colspan="2" class="muted">none</td></tr>'

    def prob_line(p):
        if not isinstance(p, dict):
            return _esc(p)
        det = p.get("detail")
        det = " — " + _esc(", ".join(_as_list(det))) if det else ""
        why = f' · {_esc(p["reason"])}' if p.get("reason") else ""
        return _esc(p.get("id", "?")) + det + why

    probs = detail.get("problems") or []
    probs_html = ("; ".join(prob_line(p) for p in probs)) or "none"
    tlc = detail.get("tlc")
    tlc_str = ("✓ proven" if tlc in (True, "ok", "pass") else "—" if tlc in (None, "") else _esc(tlc))

    callout = ""
    if detail.get("decision") == "push_back":
        toks = _as_list(detail.get("needs_approve") or detail.get("approved"))
        claim = {"skill": detail.get("skill"), "perk": detail.get("perk"),
                 "var_keys": _as_list(detail.get("var_keys")), "approve": toks or ["<approval tokens>"]}
        callout = ('<div class="callout"><b>⚠ awaiting operator approval</b> — govd never auto-approves. '
                   'to proceed, the agent re-submits the claim WITH the approval (value-free — keys and '
                   f'tokens only):<pre>{_esc(json.dumps(claim, indent=1))}</pre></div>')

    extras = ""
    if detail.get("wrapper"):
        extras += _details("blessed wrapper (run.sh) — value-free, ${KEY} placeholders", f'<pre>{_esc(detail["wrapper"])}</pre>')
    for src_name, code in (detail.get("sources") or {}).items() if isinstance(detail.get("sources"), dict) else []:
        extras += _details(f"porter · {_esc(src_name)}", f'<pre>{_esc(code)}</pre>')
    if detail.get("tlc_tla"):
        extras += _details("model-check spec (TLA+)", f'<pre>{_esc(detail["tlc_tla"])}</pre>')
    if detail.get("tlc_log"):
        extras += _details("model-check log", f'<pre>{_esc(detail["tlc_log"])}</pre>')

    flow = ""
    if has_svg:                                              # only when the blueprint SVG is actually mirrored —
        flow = _card("flow — blueprint &amp; oversight",     # never emit an <img> that triggers a live node fetch per view
                     f'<div class="flowbox"><img src="/flow/{node_e}/{rid}" alt="run flow — the value-free task blueprint" '
                     'onerror="this.closest(\'section\').style.display=\'none\'"></div>'
                     '<p class="kv">var keys render as ${KEY}, the run dir as $RUN — the values never reach govd '
                     'or this mirror (the SHELL//BLESS boundary).</p>')

    cost = detail.get("cost")
    who = _esc(detail.get("principal", "?"))
    content = (crumb + f'<h1>{_esc(detail.get("skill"))}/{_esc(detail.get("perk"))} '
               f'{_badge(detail.get("decision"))}{_dest_tag(detail)} {_risk_pill(detail)}</h1>'
               f'<p class="kv">where <b><a href="/mnode/{node_e}">{node_e}</a></b> · '
               f'who <b><a href="/principal/{who}">{who}</a></b> · when '
               f'<b>{_ts(detail.get("ts"))}</b> · cost <b>{_esc(cost) if cost else "—"}</b>'
               f'{" CREDITS" if cost else ""} · run {_cp(run_id, 20)} · '
               f'<a href="/raw/{node_e}/{rid}">raw ledger ↗</a></p>'
               + callout
               + _card("steps", f'<table><thead><tr><th>#</th><th>tool</th><th>exec (authority)</th><th>exit</th>'
                       f'<th>state</th><th>tool-use (values_sha)</th></tr></thead><tbody>{steps}</tbody></table>')
               + (_card("tool-use detail — decrypted step inputs",
                        f'<p class="kv" style="margin-top:0">Each step\'s <b>values_sha</b> above commits the '
                        'exact declared, non-secret inputs into the value-free chain. The values themselves are '
                        'encrypted at rest (tier-2 ledger); reveal decrypts them <b>live on the node</b> with its '
                        'recipient key (secrets never recorded — they stay <code>*_FILE</code> pointers).</p>'
                        f'<button id="cw-reveal" class="cwbtn" data-node="{node_e}" data-run="{rid}">reveal tool-use detail ↗</button>'
                        '<div id="cw-values" class="cwvals"></div>'
                        + _values_reveal_script()) if any_values else "")
               + flow
               + _card("claim &amp; approval",
                       f'<p class="kv" style="margin:0">destructive <b>{_esc(detail.get("destructive", False))}</b> · '
                       f'approved <b>{_esc(detail.get("approved", []) or "—")}</b> · '
                       f'needs approve <b>{_esc(detail.get("needs_approve", []) or "—")}</b> · '
                       f'credential keys <b>{_esc(detail.get("credential_ids", []) or "—")}</b> · '
                       f'problems <b class="{"no" if probs else ""}">{probs_html}</b></p>')
               + _card("plan &amp; closure",
                       f'<p class="kv" style="margin-top:0">plan_sha {_cp(detail.get("plan_sha"), 32)} · '
                       f'var_keys <b>{_esc(detail.get("var_keys", []))}</b> (keys only — values stay agent-side)</p>'
                       f'<table><thead><tr><th>closure file</th><th>pinned sha256</th></tr></thead><tbody>{sniprows}</tbody></table>')
               + _card("verification &amp; provenance",
                       f'<p class="kv" style="margin:0">model-check <b class="{"ok" if tlc in (True, "ok", "pass") else ""}">{tlc_str}</b> · '
                       f'traceparent {_cp(detail.get("traceparent"), 40)} · '
                       f'<a href="/proxy/{node_e}/trace/{rid}">trace ↗</a> · '
                       f'<a href="/proxy/{node_e}/intoto/{rid}">in-toto ↗</a> '
                       '<span class="role">(live — need the node)</span></p>')
               + _card(f'ledger — event chain ({len(detail.get("events", []))})',
                       f'<table><thead><tr><th>type</th><th>step</th><th>status</th><th>authority</th><th>keyid</th>'
                       f'<th>when</th></tr></thead><tbody>{chain}</tbody></table>')
               + (_card("artifacts", extras) if extras else ""))
    return _page(f"{detail.get('skill')}/{detail.get('perk')} · {str(run_id)[:8]} — {detail.get('_node', name)}",
                 content, refresh if _run_live(detail) else None)


def load_nodes(path):
    cfg = json.load(open(_expand(path)))
    return cfg["nodes"] if isinstance(cfg, dict) else cfg


def _is_loopback(host):
    try:
        return ipaddress.ip_address(host).is_loopback
    except ValueError:
        return host in ("localhost", "")


def serve(nodes, port, refresh, mirror_dir, mirror_interval, bind="127.0.0.1"):
    # FAIL CLOSED on a non-loopback bind — the dashboard has NO app-auth and carries a monitor-token-injecting
    # read proxy (/proxy, /embed, /flow), so binding a routable/tailnet/0.0.0.0 interface publishes every node's
    # ledger + that proxy to anyone who reaches :PORT. Mirror govd's require_closed_auth / fleetd's 0.0.0.0 gate:
    # refuse unless the operator explicitly acknowledges (FLEETDASH_ALLOW_OPEN=1), having gated :PORT with
    # deny-by-default tailscale ACLs. The default 127.0.0.1 stays open for local use.
    if not _is_loopback(bind) and os.environ.get("FLEETDASH_ALLOW_OPEN") != "1":
        raise SystemExit(
            f"fleetdash: --bind {bind} exposes a NO-app-auth dashboard (every node's value-free ledger + the "
            f"monitor-token read proxy) on that interface. Bind 127.0.0.1, or — once deny-by-default tailscale "
            f"ACLs gate :{port} to operator devices — re-run with FLEETDASH_ALLOW_OPEN=1 to acknowledge.")
    by_name = {n.get("name"): n for n in nodes}
    # Serve every page from a background-refreshed SNAPSHOT so NO request does live network I/O. The cause of
    # the dashboard hanging: fleet_from_mirror's live /health overlay probes each node per request, so every
    # page blocked for the slowest unreachable node (≈one probe timeout), and a synchronous seed did the same
    # at startup. Now the background sweep owns all node probing; the request path reads a cached snapshot
    # (instant). The snapshot is seeded once from the DURABLE on-disk mirror with NO live probe, so the first
    # page is populated immediately (last-known fleet) and the sweep refreshes liveness every mirror_interval.
    _snap = {"results": [], "feed": [], "as_of": None}
    _snap_lock = threading.Lock()

    def _refresh(live, sweeps=None):
        r, f = fleet_from_mirror(nodes, mirror_dir, live_health=live)
        if sweeps:                                          # last sweep errors ride on the node summaries (the
            for row in r:                                   # sidebar's ⚠: an auth-rotted token still pings /health)
                err = (sweeps.get(row["name"]) or {}).get("error")
                if err:
                    row["sweep_error"] = err
        with _snap_lock:
            _snap["results"], _snap["feed"] = r, f
            _snap["as_of"] = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())

    def _fleet():                                            # the request path: the cached snapshot, never the network
        if mirror_dir is None:                              # --no-mirror (live proxy-only): keep the live behaviour
            r, f = fleet_from_mirror(nodes, mirror_dir, live_health=True)
            return r, f, None
        with _snap_lock:
            return list(_snap["results"]), list(_snap["feed"]), _snap["as_of"]

    def _mirror_loop():                                      # keep the durable copy + the snapshot fresh in the background
        while True:
            try:
                sums = mirror_all(nodes, mirror_dir)
                # the slow live /health probe happens HERE, off the hot path
                _refresh(live=True, sweeps={s.get("node"): s for s in sums})
            except Exception:
                pass
            time.sleep(max(2, mirror_interval))

    if mirror_dir:
        os.makedirs(_expand(mirror_dir), exist_ok=True)      # fail fast on a bad mirror dir (cheap, no network)
        try:
            _refresh(live=False)                            # instant seed from the durable mirror (no probe) so page 1 has data
        except Exception:
            pass
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
                return self._send(404, _notfound("unknown node"))
            if not sub:                                              # the dashboard HTML (trusted, from the repo)
                nonce = secrets.token_urlsafe(12)
                csp = (f"default-src 'self'; script-src 'nonce-{nonce}'; style-src 'unsafe-inline'; "
                       "img-src 'self' data:; connect-src 'self'; frame-ancestors 'self'")
                return self._bytes(200, "text/html; charset=utf-8",
                                   _embed_html(urllib.parse.unquote(node_name), nonce),
                                   extra={"Content-Security-Policy": csp})
            sub = urllib.parse.unquote(sub)
            if not _embed_proxiable(sub):
                return self._send(404, _notfound("not proxiable"))
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
                    results, feed, as_of = _fleet()
                    risk = mark_superseded(feed, risk_summary(feed))
                    return self._send(200, render_html(results, feed, risk, refresh, as_of=as_of))
                if parts[0] == "risk":                              # fleet-wide risk / approval queue
                    results, feed, as_of = _fleet()
                    risk = mark_superseded(feed, risk_summary(feed))
                    return self._send(200, render_risk(feed, risk, refresh, as_of=as_of))
                if parts[0] == "accounting":                        # fleet CREDIT accounting (spend by actor)
                    _, feed, as_of = _fleet()
                    return self._send(200, render_accounting(feed, refresh, as_of=as_of))
                if parts[0] == "principal" and len(parts) == 2:     # one actor's cross-fleet credit account
                    _, feed, as_of = _fleet()
                    return self._send(200, render_principal(parts[1], feed, refresh, as_of=as_of))
                if parts[0] == "node" and len(parts) == 2:          # per-node = the LIVE individual-monitor UI (iframe)
                    node = by_name.get(parts[1])
                    if not node:
                        return self._send(404, _notfound("unknown node"))
                    res, _, _ = _fleet()                    # reachability from the cached snapshot, not a live probe
                    reachable = bool(next((r["reachable"] for r in res if r["name"] == parts[1]), False))
                    return self._send(200, render_node_iframe(node, reachable, refresh=refresh))
                if parts[0] == "mnode" and len(parts) == 2:         # the durable central MIRROR board (offline-capable)
                    node = by_name.get(parts[1])
                    if not node:
                        return self._send(404, _notfound("unknown node"))
                    results, _ = fleet_from_mirror([node], mirror_dir, live_health=False)   # durable mirror, no live probe
                    res, _, as_of = _fleet()                # liveness + sweep state from the cached snapshot
                    cached = next((r for r in res if r["name"] == parts[1]), {})
                    results[0]["reachable"] = cached.get("reachable")
                    if cached.get("sweep_error"):
                        results[0]["sweep_error"] = cached["sweep_error"]
                    return self._send(200, render_node(node, results[0], refresh, as_of=as_of))
                if parts[0] == "run" and len(parts) == 3:           # per-run LEDGER INSPECTION (durable mirror)
                    node = by_name.get(parts[1])
                    if not node:
                        return self._send(404, _notfound("unknown node"))
                    has_svg = load_run_svg(mirror_dir, node["name"], parts[2]) is not None if mirror_dir else False
                    return self._send(200, render_run(node["name"], parts[2],
                                                      load_run(mirror_dir, node["name"], parts[2]) if mirror_dir else None,
                                                      has_svg, refresh=refresh))
                if parts[0] == "raw" and len(parts) == 3:           # the raw ledger record (value-free JSON)
                    node = by_name.get(parts[1])
                    detail = load_run(mirror_dir, node["name"], parts[2]) if node and mirror_dir else None
                    body = _esc(json.dumps(detail, indent=2)) if detail else "not in the mirror"
                    copy_btn = (f' <span class="cp" tabindex="0" role="button" data-full="{_esc(json.dumps(detail, indent=2))}"'
                                ' title="copy the full JSON">copy json</span>') if detail else ""
                    return self._send(200, _page("raw ledger",
                                                 f'<p class="crumb"><a href="/run/{_esc(parts[1])}/{_esc(parts[2])}">← run</a></p>'
                                                 f'<h1>raw ledger · {_esc(parts[2])}</h1>'
                                                 '<p class="kv">the value-free record — decisions, hashes, exit codes, '
                                                 f'key names. no command output or values are ever recorded.{copy_btn}</p>'
                                                 f'<pre style="max-height:none">{body}</pre>'))
                if parts[0] == "flow" and len(parts) == 3:          # the blueprint/oversight SVG (mirror, else live)
                    node = by_name.get(parts[1])
                    if not node:
                        return self._send(404, _notfound("unknown node"))
                    svg = load_run_svg(mirror_dir, node["name"], parts[2]) if mirror_dir else None
                    if svg is None:                                 # not mirrored — proxy live (token server-side)
                        try:
                            _ct, svg = _get_raw(node["url"].rstrip("/") + "/flow/run/" + urllib.parse.quote(parts[2]), _token(node))
                        except Exception:
                            svg = None
                    if not svg:
                        return self._send(404, _notfound("no flow recorded for this run"))
                    return self._bytes(200, "image/svg+xml; charset=utf-8", svg)
                if parts[0] == "proxy" and len(parts) >= 3:         # token-injecting read proxy to a node endpoint
                    node = by_name.get(parts[1])
                    sub = "/".join(parts[2:])
                    if not node or not _proxiable(sub):
                        return self._send(404, _notfound("not proxiable"))
                    try:
                        _ct, data = _get_raw(node["url"].rstrip("/") + "/" + urllib.parse.quote(sub, safe="/"), _token(node))
                        # NEVER pass the node's Content-Type through — a node returning text/html would XSS the
                        # dashboard origin. Serve every proxied read as inert text/plain (raw JSON is readable).
                        return self._bytes(200, "text/plain; charset=utf-8", data)
                    except urllib.error.HTTPError as e:
                        return self._send(e.code, _page("upstream", f'<p class="muted">node returned HTTP {e.code}</p>'))
                    except Exception as e:
                        return self._send(502, _page("upstream", f'<p class="muted">{_esc(type(e).__name__)}</p>'))
                return self._send(404, _notfound("not found"))
            except Exception as e:
                return self._send(500, _page("error", f'<p class="muted">{_esc(e)}</p>'))

    httpd = ThreadingHTTPServer((bind, port), H)
    print(f"fleet control → http://{bind}:{port}  (central mirror → {_expand(mirror_dir) if mirror_dir else 'OFF'} · "
          f"every {mirror_interval}s · {len(nodes)} nodes)")
    httpd.serve_forever()


def main():
    ap = argparse.ArgumentParser(description="cyberware fleet control — central monitor + durable ledger mirror")
    ap.add_argument("--config", required=True, help="fleet.json: {nodes:[{name,role,url,token_file}]}")
    ap.add_argument("--serve", type=int, metavar="PORT", help="serve the live, click-through HTML dashboard on BIND:PORT")
    ap.add_argument("--bind", default="127.0.0.1", metavar="HOST",
                    help="interface to bind the dashboard (default 127.0.0.1 = local only; pass the node's tailnet "
                         "IP to reach it across the tailnet — the dashboard has NO app-auth, so gate :PORT with "
                         "deny-by-default tailscale ACLs)")
    ap.add_argument("--refresh", type=int, default=5, help="dashboard auto-refresh seconds (default 5)")
    ap.add_argument("--mirror-dir", default=DEFAULT_MIRROR, help=f"central durable ledger copy (default {DEFAULT_MIRROR})")
    ap.add_argument("--mirror-interval", type=int, default=10, help="background mirror sweep seconds (default 10)")
    ap.add_argument("--no-mirror", action="store_true", help="do not keep a central copy (live-proxy only)")
    ap.add_argument("--limit", type=int, default=40, help="rows in the text view (default 40)")
    a = ap.parse_args()
    nodes = load_nodes(a.config)
    mirror_dir = None if a.no_mirror else a.mirror_dir
    if a.serve:
        serve(nodes, a.serve, a.refresh, mirror_dir, a.mirror_interval, a.bind)
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
        print(render_text(results, feed, mark_superseded(feed, risk_summary(feed)), a.limit))


if __name__ == "__main__":
    main()
