#!/usr/bin/env python3
"""infra/govern/fleetd.py — the FLEET discovery/coordination plane (:8773), a DEFAULT-ON core service that
runs beside the local govd (:5773).

govd (:5773) governs + executes for THIS node. fleetd (:8773) answers WHERE: which fleet nodes exist, which
are alive, which one offers which skill — so an agent can locate a node and then claim+govern on that node's
:5773. fleetd INDEXES govd instances; it never governs and never executes (faithful to the boundary — govd
proposes and records, exod executes confined; discovery only points).

Design invariants (see deploy/FLEET-VALIDATION.md):
  * DEFAULT-ON + GRACEFUL-STANDALONE — with no roster the fleet is exactly [self]: no error, :5773 untouched.
    The no-config path mirrors principals.load_principals (empty-not-throw).
  * SAME TRUST ROOT — /fleet/* reuse govd's principals registry (the SHARED cfg['principals']): Bearer-gated,
    deny-by-default, rate-limited, no new credential, no node keypair. A token revoked in the registry is
    denied here on the next request. govd.serve() refuses to START this plane on a non-loopback bind with no
    registry (the require_closed_auth equivalent), so the auth-disabled path is loopback-only.
  * NO SHARED WRITTEN STATE — there is NO register/gossip write surface. Each node only ever reports what it
    itself scrapes LIVE from peers' ungated :5773 /health + /catalog, so a fleet-token holder cannot forge
    "I run skill X at «attacker:5773»" and have it propagate (no roster-poisoning amplification).
  * SSRF-FENCED — the peer probe + the roster fetch use http/https ONLY (no file/ftp/data handlers, no
    redirects) and a wall-clock deadline + byte cap, so a roster URL cannot read disk / scan internal ports /
    stall a worker.
  * TAILNET-ONLY — binds govd's interface; the host `-p <tailnet-ip>:8773:8773` mapping fences it.
  * ROSTER FROM CONFIG, NEVER THE REPO — FLEETD_FLEET_URL > FLEETD_FLEET (file) > self-only; supplied to the
    container the same configurable way as GOVD_PRINCIPALS (never hardcoded, never committed).
"""
from __future__ import annotations
import json
import os
import socket
import time
import urllib.error
import urllib.parse
import urllib.request
from concurrent.futures import ThreadPoolExecutor
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

from infra.govern import principals

FLEET_PORT = 8773
PROBE_TIMEOUT = 2.0            # per-peer probe WALL-CLOCK deadline; a slow/dead peer never stalls past this
PROBE_MAX_BYTES = 256 * 1024  # cap a peer/roster response — a compromised source cannot OOM the handler
CACHE_TTL = 5.0               # collapse query bursts (matches the repo's 5s poll convention)
SOCKET_TIMEOUT = 15.0         # per-connection read timeout — no slowloris on the fleet plane

_TIER_RANK = {"core": 0, "verified": 1, "community": 2}   # catalog TRUST order (core = most trusted)
_CACHE: dict = {}             # {"roster": (ts, [descriptor, ...])} — tiny in-process TTL cache


# ───────────────────────── SSRF-fenced HTTP (http/https only, no redirects) ─────────────────────────
class _NoRedirect(urllib.request.HTTPRedirectHandler):
    """A peer/provider must not be able to redirect our request somewhere else (SSRF/loop guard)."""
    def redirect_request(self, *a, **k):
        return None


def _build_opener():
    """An opener with ONLY http/https + no-redirect — deliberately WITHOUT the default File/FTP/Data/Unknown
    handlers, so a roster `url` of file:///… / ftp:// / data: cannot read disk or reach a non-HTTP service."""
    o = urllib.request.OpenerDirector()
    for h in (urllib.request.HTTPHandler(), urllib.request.HTTPSHandler(),
              _NoRedirect(), urllib.request.HTTPErrorProcessor()):
        o.add_handler(h)
    return o


_OPENER = _build_opener()


def _safe_url(u) -> bool:
    """True iff `u` is an http/https URL — the only schemes the discovery plane will ever dereference."""
    try:
        return isinstance(u, str) and urllib.parse.urlparse(u).scheme in ("http", "https")
    except Exception:
        return False


def _read_capped(r, deadline) -> bytes:
    """Read a response body in chunks under a WALL-CLOCK deadline + byte cap. A trickle-feed peer (urllib's
    socket timeout resets per recv) cannot hold the worker past the deadline."""
    chunks, total = [], 0
    while total <= PROBE_MAX_BYTES:
        if time.monotonic() > deadline:
            raise TimeoutError("peer read exceeded deadline")
        chunk = r.read(min(8192, PROBE_MAX_BYTES - total + 1))
        if not chunk:
            break
        chunks.append(chunk)
        total += len(chunk)
    return b"".join(chunks)[:PROBE_MAX_BYTES]


def _get_json(url: str) -> dict:
    """GET + parse JSON from a peer, http/https only, no redirects, deadline + size bounded."""
    deadline = time.monotonic() + PROBE_TIMEOUT
    with _OPENER.open(urllib.request.Request(url, method="GET"), timeout=PROBE_TIMEOUT) as r:
        raw = _read_capped(r, deadline)
    return json.loads(raw)


# ───────────────────────── roster (config, never the repo) ─────────────────────────
def load_roster(cfg) -> list:
    """The peer roster: FLEETD_FLEET_URL (remote provider) > FLEETD_FLEET (mounted file) > [] (self-only).
    Absent/empty/unreadable/non-http -> [] — graceful standalone, NEVER raises (mirrors load_principals)."""
    url = os.environ.get("FLEETD_FLEET_URL")
    if url:
        if not _safe_url(url):
            return []                                      # only http/https topology providers
        try:
            tok = os.environ.get("FLEETD_FLEET_TOKEN", "")
            req = urllib.request.Request(url, headers={"Authorization": "Bearer " + tok} if tok else {})
            deadline = time.monotonic() + PROBE_TIMEOUT
            with _OPENER.open(req, timeout=PROBE_TIMEOUT) as r:   # no-redirect, http/https only
                return _nodes_of(json.loads(_read_capped(r, deadline)))
        except Exception:
            return []          # a flaky/hostile topology provider must not break the local plane
    path = os.environ.get("FLEETD_FLEET") or (cfg.get("fleet") or {}).get("roster")
    if path and os.path.isfile(path):
        try:
            with open(path) as fh:
                return _nodes_of(json.load(fh))
        except Exception:
            return []
    return []


def _nodes_of(d) -> list:
    nodes = d.get("nodes") if isinstance(d, dict) else d
    return [n for n in (nodes or []) if isinstance(n, dict) and _safe_url(n.get("url"))]


def _roster_source(cfg) -> str:
    """The roster ORIGIN category (network-free — only inspects env + cfg, never fetches)."""
    if os.environ.get("FLEETD_FLEET_URL"):
        return "url"
    if os.environ.get("FLEETD_FLEET") or (cfg.get("fleet") or {}).get("roster"):
        return "file"
    return "self"


# ───────────────────────── capability descriptor (only existing data) ─────────────────────────
def _src(prov) -> str:
    """A node's chip provenance as a one-line string — the same shape govd prints at boot."""
    if (prov or {}).get("mode") == "cloud":
        return f"cloud {prov.get('source')} @ {prov.get('ref')} ({str(prov.get('commit'))[:12]})"
    return "local (baked)"


def _self_descriptor(cfg, self_url) -> dict:
    """This node's row — built in-process from govd's own helpers (ZERO network)."""
    skills, chip, prov = [], None, {}
    exec_mode = cfg.get("exec_mode", "cooperative")
    try:
        from infra.govern import govd            # lazy: govd is loaded by the time a request lands
        cat = govd.catalog_snapshot()
        skills = sorted(s.get("skill") for s in (cat.get("skills") or []) if s.get("skill"))
        chip = govd.chip_sha()
        prov = govd.chip_provenance() or {}
    except Exception:
        pass
    ex = cfg.get("exod") or {}
    exod = bool(ex.get("socket") and ex.get("grant_key") and ex.get("pub"))
    f = cfg.get("fleet") or {}
    return {"node_id": f.get("node_id") or socket.gethostname(), "url": self_url,
            "role": f.get("role", "node"), "arch": (f.get("arch") or None),
            "chip_sha": chip, "chip_source": _src(prov), "skills": skills, "tier": (f.get("tier") or None),
            "exec_mode": exec_mode, "exod_attached": exod,
            "healthy": True, "last_seen": int(time.time())}


def _probe(node: dict) -> dict:
    """Live-probe one peer's UNGATED :5773 /health + /catalog. A dead/unreachable peer is KEPT (never silently
    dropped) but marked healthy:false with last_seen=None. Bounded by PROBE_TIMEOUT — never hangs the handler."""
    base = {"node_id": node.get("name") or node.get("node_id"), "url": node["url"],
            "role": node.get("role"), "arch": node.get("arch"), "tier": (node.get("tier") or None)}
    u = node["url"].rstrip("/")
    try:
        h = _get_json(u + "/health")
        c = _get_json(u + "/catalog")
        base.update({"chip_sha": h.get("chip_sha"), "chip_source": _src(h.get("chip") or {}),
                     "skills": sorted(s.get("skill") for s in (c.get("skills") or []) if s.get("skill")),
                     "exec_mode": h.get("exec_mode"), "exod_attached": h.get("exod_attached"),
                     "healthy": h.get("status") == "ok", "last_seen": int(time.time())})
    except Exception:
        base.update({"chip_sha": None, "chip_source": None, "skills": [],
                     "exec_mode": None, "exod_attached": None, "healthy": False, "last_seen": None})
    return base


def fleet_roster(cfg, self_url) -> list:
    """[self] + a LIVE probe of each roster peer (probed concurrently, bounded). TTL-cached. Self is always
    present and ALIVE; self is never double-listed even if it appears in the roster file."""
    now = time.time()
    c = _CACHE.get("roster")
    if c and now - c[0] < CACHE_TTL:
        return c[1]
    me = _self_descriptor(cfg, self_url)
    seen = {me["url"].rstrip("/")}
    peers = []
    for n in load_roster(cfg):
        k = n["url"].rstrip("/")
        if k in seen:
            continue
        seen.add(k)
        peers.append(n)
    nodes = [me]
    if peers:
        with ThreadPoolExecutor(max_workers=min(8, len(peers))) as ex:
            nodes.extend(ex.map(_probe, peers))
    _CACHE["roster"] = (time.time(), nodes)            # stamp AFTER the build — a slow build is not born-expired
    return nodes


def _tier_ok(node_tier, want) -> bool:
    """Trust-ceiling filter: node is AT LEAST as trusted as `want` (core>verified>community). An unrecognized
    `want` imposes no constraint. A node with no/unknown tier is treated as the LEAST-trusted (community) — it
    satisfies only loose filters and can NEVER win a `tier=core`/`tier=verified` query (no unearned trust)."""
    if want not in _TIER_RANK:
        return True
    nt = _TIER_RANK.get(node_tier, _TIER_RANK["community"])   # unknown/untiered -> least trusted, never elevated
    return nt <= _TIER_RANK[want]


def _leaf(skill_id: str) -> str:
    return skill_id.split(":", 1)[1] if ":" in skill_id else skill_id


def _skill_matches(query: str, rid: str) -> bool:
    """Does discovery query `query` match a roster skill id `rid`? fleetd is chip-AGNOSTIC (it aggregates peer
    catalogs and cannot canonicalize), so the match is leaf-tolerant across the v1(bare)->v2(ns:name) cutover:
      - a BARE query (`fs`) matches any namespace's same leaf (`general:fs`) or a flat node (`fs`) — discovery
        by leaf, the pre-cutover behaviour preserved AND extended over namespaced rosters;
      - a NAMESPACED query (`general:fs`) matches that exact id or a legacy FLAT advertisement of the leaf
        (`fs`), but NOT a different namespace (`magnumopus:fs`) — namespaced queries stay precise."""
    if query == rid:
        return True
    if ":" in query:
        return rid == _leaf(query)                            # ns query: exact, or a flat node's bare leaf
    return _leaf(rid) == query                                # bare query: any namespace's same leaf


# ───────────────────────── the :8773 handler ─────────────────────────
class FleetHandler(BaseHTTPRequestHandler):
    server_version = "cyberware-fleetd/1.0"
    protocol_version = "HTTP/1.1"
    timeout = SOCKET_TIMEOUT

    def log_message(self, *a):       # quiet — fleetd is an index, not a logger
        pass

    def _json(self, code, obj):
        body = json.dumps(obj, indent=2).encode()
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _auth(self):
        """Reuse govd's EXACT trust root — the SHARED principals registry. Returns the principal id, or None
        (-> 401). With NO registry, auth is disabled and returns the sentinel "local"; govd.serve() refuses to
        start this plane on a non-loopback bind without a registry, so that open path is loopback-only."""
        reg = self.server.cfg.get("principals") or {}
        if not reg:
            return "local"
        return principals.authenticate(principals.bearer_of(self.headers.get("Authorization", "")), reg)

    def _rate_ok(self, pid) -> bool:
        reg = self.server.cfg.get("principals") or {}
        spec = reg.get(pid) or {}
        bucket = self.server.rate_buckets.setdefault(pid, {})
        return principals.rate_ok(bucket, time.time(), float(spec.get("rate", 2.0)), float(spec.get("burst", 20.0)))

    def do_GET(self):
        path = self.path.split("?", 1)[0]
        cfg, self_url = self.server.cfg, self.server.self_url

        if path == "/fleet/health":          # UNGATED — own liveness ONLY; NO roster I/O on the anon path
            return self._json(200, {"status": "ok", "service": "cyberware-fleetd",
                                    "self_url": self_url, "roster_source": _roster_source(cfg)})

        # everything below is Bearer-gated — the AGGREGATE roster discloses the whole fleet, never to anon
        reg = cfg.get("principals") or {}
        pid = self._auth()
        if pid is None:
            return self._json(401, {"error": "missing/invalid Authorization: Bearer token"})
        if reg and not self._rate_ok(pid):           # rate-limit gates on REGISTRY presence, not the pid string
            return self._json(429, {"error": "rate limited"})

        if path == "/fleet/nodes":
            return self._json(200, {"nodes": fleet_roster(cfg, self_url)})

        if path == "/fleet/find":
            qs = urllib.parse.parse_qs(urllib.parse.urlparse(self.path).query)
            skill = (qs.get("skill") or [""])[0]
            tier = (qs.get("tier") or [None])[0]
            want_all = (qs.get("all") or ["0"])[0] in ("1", "true", "yes")
            if not skill:
                return self._json(400, {"error": "skill query param required", "usage": "/fleet/find?skill=<id>&tier=<core|verified|community>&all=1"})
            matches = [n for n in fleet_roster(cfg, self_url)
                       if n.get("healthy") and any(_skill_matches(skill, rid) for rid in (n.get("skills") or []))
                       and _tier_ok(n.get("tier"), tier)]
            if want_all:
                return self._json(200, {"skill": skill, "count": len(matches), "nodes": matches})
            if not matches:
                return self._json(404, {"skill": skill, "url": None, "reason": "no healthy node offers this skill"})
            m = matches[0]
            return self._json(200, {"skill": skill, "url": m["url"], "node_id": m.get("node_id"),
                                    "tier": m.get("tier"), "exec_mode": m.get("exec_mode"),
                                    "exod_attached": m.get("exod_attached")})

        return self._json(404, {"error": "not found",
                                "fleet_endpoints": ["/fleet/health", "/fleet/nodes", "/fleet/find?skill="]})


# ───────────────────────── start (called default-on from govd.serve) ─────────────────────────
def _default_self_url(cfg, host) -> str:
    """This node's OWN :5773 base — what peers/agents call to claim. Precedence: FLEETD_ADVERTISE_URL >
    cfg.fleet.advertise_url > derived (remote host + govd port) > loopback. The deployment supplies the
    tailnet URL (the container can't know its own tailnet IP); standalone falls back to loopback."""
    f = cfg.get("fleet") or {}
    adv = os.environ.get("FLEETD_ADVERTISE_URL") or f.get("advertise_url")
    if adv:
        return adv.rstrip("/")
    gport = (cfg.get("remote") or {}).get("port") or ((cfg.get("local") or {}).get("ports") or [5773])[0]
    ghost = f.get("advertise_host") or (cfg.get("remote") or {}).get("host") or host
    if ghost in ("0.0.0.0", "::", None):
        ghost = "127.0.0.1"
    return f"http://{ghost}:{gport}"


def start(cfg, host, port=FLEET_PORT, self_url=None):
    """Bind the fleet plane and return the (unstarted) server. The caller runs serve_forever() on a daemon
    thread. Shares cfg (so cfg['principals'] is the live trust root). Binds `host`; the host -p mapping fences
    it to the tailnet, exactly like :5773."""
    srv = ThreadingHTTPServer((host, port), FleetHandler)
    srv.daemon_threads = True
    srv.cfg = cfg
    srv.rate_buckets = {}
    srv.self_url = self_url or _default_self_url(cfg, host)
    return srv
