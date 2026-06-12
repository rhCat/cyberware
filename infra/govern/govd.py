#!/usr/bin/env python3
"""govd.py — the cyberware governance server. A control/audit plane: it governs the CLAIM and records
STATUS. It never sees task data and it never executes.

The agent sends a CLAIM — skill, perk, and var KEYS (names only; no values, no file contents, no
secrets). govd checks the claim against its OWN trusted registry and blesses a value-free execution
PLAN (the tool sequence + each snippet's sha256 + a wrapper with `${VAR}` placeholders), pinning the
plan's sha256. The agent binds its own vars LOCALLY and runs LOCALLY; over a per-run WebSocket it
reports STATUS only (step ran, exit, ok/fail). govd monitors the plan HASH — not the content — and
records the provenance. Like a bank session: the ledger, not the contents of your box.

Principles enforced here:
  * No data crosses the boundary. Only the claim (keys) and status. Secrets are refused as plaintext
    keys — pass a `*_FILE` pointer; the snippet reads it at runtime via `cat`.
  * Destructiveness is a property of the DECLARED perk (`destructive:true`), gated by approval — govd
    never inspects payload to decide it.
  * Oversight monitors the plan sha256. On an inconsistency it investigates by PLAIN TEXT DIFF
    (`plan_diff`), never by executing/sourcing/piping a submitted plan.
  * Each run is a private session (a per-run token gates the WS and the ledger read). The provenance
    ledger is server-owned; the upstream-order gate can't be forged.

HTTP:
  GET  /health                        -> mode, port, registry, run count
  GET  /catalog                       -> value-free discovery: skills · perks · var-KEYS · skill_sha · verified
  GET  /flow/<skill>                  -> the skill's blueprint.svg (lifecycle diagram; value-free, for the dashboard)
  POST /govern  {skill,perk,var_keys,approve?}
                  -> 200 allow      {run_id, decision, plan, plan_sha, session_token, ws}   (plan = value-free)
                     409 push_back  {run_id, decision, needs_approve, ...}                   (destructive: approve)
                     403 reject     {run_id, decision, problems, ...}
  GET  /ledger/<run_id>?token=…       -> the server-side provenance chain (requires the run's token)

WebSocket  /oversight   (per-run session; status only):
  -> {"type":"hello","run_id","token"}                      <- hello_ack(authorized)
  -> {"type":"step_request","step","plan_sha"}              <- grant | refuse   (plan-hash + upstream)
  -> {"type":"step_result","step","plan_sha","status","exit"} <- recorded       (server-side ledger)

  python3 infra/govd.py [--config infra/govd_config.json] [--mode local|remote] [--port N]
"""
from __future__ import annotations
import argparse, base64, collections, hashlib, hmac, json, os, re, secrets, sys, threading, time, urllib.parse, uuid
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

from infra.govern import compiler
from infra.govern import composer
from infra.tool import skill_index   # verify the registry matches its committed per-skill authenticity index
import difflib             # the inconsistency path is a plain text diff — never execute a submitted plan

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
DEFAULT_CONFIG = os.path.join(HERE, "govd_config.json")
WS_GUID = "258EAFA5-E914-47DA-95CA-C5AB0DC85B11"             # RFC 6455 magic
VALID_KEY = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")          # a safe shell var name
SECRET_KEY = re.compile(r"(?i)(password|passwd|secret|token|api[_-]?key|access[_-]?key|private[_-]?key)")
MAX_BODY = 1 << 20                                           # cap a /govern request body at 1 MiB (keys only)
MAX_WS_FRAME = 1 << 20                                       # refuse a WebSocket frame larger than 1 MiB
SOCKET_TIMEOUT = 600                                         # per-read socket timeout (s) — kills slowloris
SNAPSHOT_RUNS = 150  # most-recent runs the dashboard lists/aggregates
MAX_RUNS = 8192                                             # in-memory run cap; oldest evicted (disk retained)


def now(): return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def plan_diff(blessed_text, submitted_text):
    """When a plan hash is inconsistent, investigate by PLAIN TEXT DIFF — read as strings, compared as
    strings. Never execute, source, or pipe a submitted plan (that would be RCE); only diff it."""
    a = (blessed_text or "").splitlines()
    b = (submitted_text or "").splitlines()
    return "\n".join(difflib.unified_diff(a, b, "blessed", "submitted", lineterm=""))


# ───────────────────────── config ─────────────────────────

def load_config(path=None):
    p = path or os.environ.get("GOVD_CONFIG") or DEFAULT_CONFIG
    cfg = json.load(open(p)) if os.path.isfile(p) else {}
    cfg.setdefault("mode", "local")
    cfg.setdefault("local", {}).setdefault("host", "127.0.0.1")
    cfg["local"].setdefault("ports", [5773, 4773, 3773, 6773])
    cfg.setdefault("remote", {}).setdefault("host", "0.0.0.0")
    cfg["remote"].setdefault("port", 5773)
    cfg["record_root"] = os.environ.get("GOVD_RECORD_ROOT") or cfg.get("record_root") or "~/cyberware_govd"
    # the monitor (dashboard) token — gates the dashboard. env > config; the default is filled by
    # ensure_monitor_token() once the FINAL mode is known (after any --mode override).
    cfg["monitor_token"] = os.environ.get("GOVD_MONITOR_TOKEN") or cfg.get("monitor_token") or None
    return cfg


def ensure_monitor_token(cfg):
    """Fill the monitor-token default by the final mode: a friendly 'admin' for LOCAL use, a strong random
    token for REMOTE (network-exposed) so it is never guessable. Override anytime with GOVD_MONITOR_TOKEN."""
    if not cfg.get("monitor_token"):
        cfg["monitor_token"] = "admin" if cfg.get("mode") == "local" else secrets.token_urlsafe(18)
    return cfg["monitor_token"]


# ───────────────────────── governance core ─────────────────────────

_TLC_CACHE = {}                                          # blueprint sha -> (ok, msg); blueprints are static
_VERIFY_CACHE = {}                                       # skill -> (ok, drift); the registry is static at runtime
_CATALOG_CACHE = {}                                      # the value-free discovery catalog; registry static


def verify_skill(skill):
    """Cached authenticity check: does the server's registry for `skill` match its committed index.json?"""
    if skill not in _VERIFY_CACHE:
        _VERIFY_CACHE[skill] = skill_index.verify(skill)
    return _VERIFY_CACHE[skill]


def catalog_snapshot():
    """The value-free discovery catalog of govd's OWN registry (skills · perks · var-KEYS · skill_sha ·
    verified), cached because the registry is static at runtime. This is what an agent reads to discover
    what's governed — and to learn which of its OWN skills are blessed (sha match) vs new (unverified)."""
    if "c" not in _CATALOG_CACHE:
        _CATALOG_CACHE["c"] = skill_index.catalog()
    return _CATALOG_CACHE["c"]
_TLC_LOCK = threading.Lock()


def tlc_check(bp):
    """The TLA+/TLC deadlock model check, run here in the control plane and cached per blueprint (so TLC
    runs once per skill). Returns (ok, msg, tla, output): the verdict plus the TLA+ spec and TLC's FULL log
    (ok None = TLC unavailable, structural check governs; in the container the jar is present so it's real)."""
    key = hashlib.sha256(json.dumps(bp, sort_keys=True).encode()).hexdigest()
    with _TLC_LOCK:
        if key in _TLC_CACHE:
            return _TLC_CACHE[key]
    tla = composer.emit_tla(bp)
    ok, msg, out = composer.run_tlc(tla, "task")
    with _TLC_LOCK:
        _TLC_CACHE[key] = (ok, msg, tla, out)
    return _TLC_CACHE[key]


def govern(ledger, cfg):
    """Govern a CLAIM — never payload. The agent sends skill, perk, and var KEYS (names only, no values,
    no file contents, no secrets); govd checks the claim against its OWN trusted registry and blesses a
    value-free execution PLAN (sequence + snippet hashes + wrapper), pinning its sha256. Destructiveness
    is a property of the declared perk, gated by approval — govd never inspects task data to decide it.
    Pure: returns a verdict dict, writes nothing."""
    skill, perk = ledger.get("skill"), ledger.get("perk")
    var_keys = list(ledger.get("var_keys") or ledger.get("vars") or [])   # accept a name list or a dict's keys
    approve = list(ledger.get("approve", []))
    problems = []

    if not skill or not perk:
        return {"decision": "reject", "problems": [{"id": "missing_skill_or_perk"}]}
    pdir = os.path.join(ROOT, "skills", skill, "perks", perk)
    if not os.path.isdir(pdir):
        return {"decision": "reject", "problems": [{"id": "unknown_skill_perk", "detail": f"{skill}/{perk}"}]}

    # 1. var-KEY hygiene — names only. A key like "X=1; rm -rf /; A" would break the agent's `export`;
    #    a plaintext-secret key (PGPASSWORD, *_TOKEN, …) is refused — pass a *_FILE pointer instead.
    bad = [k for k in var_keys if not VALID_KEY.match(k)]
    if bad:
        problems.append({"id": "bad_var_key", "detail": bad,
                         "reason": "var keys must match ^[A-Za-z_][A-Za-z0-9_]*$ (shell-injection guard)"})
    secretish = [k for k in var_keys if SECRET_KEY.search(k) and not k.endswith("_FILE")]
    if secretish:
        problems.append({"id": "plaintext_secret_key", "detail": secretish,
                         "reason": "secrets must be passed as a *_FILE pointer (read via cat at runtime), "
                                   "never as a plaintext value"})

    try:
        contract = json.load(open(os.path.join(pdir, "src", "contracts.json")))
        bp = json.load(open(os.path.join(ROOT, "skills", skill, "blueprint.json")))
        perks = json.load(open(os.path.join(ROOT, "skills", skill, "perks.json")))["perks"]
    except (OSError, ValueError, KeyError) as e:
        return {"decision": "reject", "problems": [{"id": "registry_error", "detail": str(e)}]}
    destructive = next((p.get("destructive", False) for p in perks if p.get("id") == perk), False)

    # authenticity gate: the server won't bless a registry that doesn't match its committed index
    ok_idx, drift = verify_skill(skill)
    if not ok_idx:
        problems.append({"id": "registry_drift", "detail": drift[:5],
                         "reason": f"{skill} files do not match index.json — regenerate with "
                                   f"`python3 -m infra.tool.skill_index --skill {skill}`"})

    # 2. required inputs present — checked BY NAME against the declared keys (no values needed)
    present = set(var_keys)
    for k, spec in contract.get("inputs", {}).items():
        if spec.get("required") and k not in present:
            problems.append({"id": "missing_input", "detail": k})

    # 3. compose — structural reachability + the TLA+/TLC model check (TLC is real in the container,
    #    skipped to structural-only otherwise). A deadlock by either route rejects the claim.
    for s in composer.structural(bp):
        problems.append({"id": "structural", "detail": s})
    tlc_ok, tlc_msg, tlc_tla, tlc_out = tlc_check(bp)
    if tlc_ok is False:
        problems.append({"id": "deadlock_tlc", "detail": tlc_msg})

    # 4. bless the value-free plan and hash it (the thing oversight monitors)
    try:
        plan = compiler.build_plan(skill, perk)
    except Exception as e:
        return {"decision": "reject", "problems": problems + [{"id": "plan_error", "detail": str(e)}]}
    psha = compiler.plan_sha(plan)

    # 5. decide on the CLAIM: structural problems reject; a destructive perk needs explicit approval
    needs_approve = []
    if destructive and not ({perk, "destructive"} & set(approve)):
        needs_approve = [perk]
    decision = "reject" if problems else ("push_back" if needs_approve else "allow")
    return {"decision": decision, "problems": problems, "destructive": destructive,
            "approved": [a for a in approve if a in (perk, "destructive")],
            "plan": plan, "plan_sha": psha, "seq": plan["sequence"],
            "tlc": tlc_msg, "tlc_tla": tlc_tla, "tlc_log": tlc_out,   # the model-check spec + full log
            "needs_approve": needs_approve}


# ───────────────────────── server-side provenance store ─────────────────────────

class Store:
    """The provenance ledger — server-owned, one private session per run. One dir per run under
    record_root; the agent never writes here. In-memory runs are capped (oldest evicted, disk retained)
    so the server stays bounded under high concurrency."""

    def __init__(self, root, max_runs=MAX_RUNS):
        self.root = os.path.abspath(os.path.expanduser(root))
        os.makedirs(self.root, exist_ok=True)
        self.lock = threading.Lock()
        self.runs = {}                                       # insertion-ordered -> oldest is first
        self.max_runs = max_runs
        self.decisions = collections.deque(maxlen=500)       # every /govern verdict (metadata, for the monitor)
        self._hydrate()                                      # load persisted ledgers (mounted record_root)

    def _path(self, run_id): return os.path.join(self.root, run_id, "ledger.json")

    def _hydrate(self):
        """Load existing per-run ledgers from disk (most recent up to max_runs) so a restarted server with
        a MOUNTED record_root still shows history for review. Rebuilds the decisions feed from them too."""
        found = []
        for name in os.listdir(self.root):
            p = self._path(name)
            if os.path.isfile(p):
                try:
                    found.append((os.path.getmtime(p), json.load(open(p))))
                except (OSError, ValueError):
                    continue
        found.sort(key=lambda t: t[0])                       # oldest first; newest survive the cap
        for _, rec in found[-self.max_runs:]:
            rid = rec.get("run_id")
            if not rid:
                continue
            rec["restored"] = True                           # loaded from disk (a prior session)
            self.runs[rid] = rec
            self.decisions.append({"run_id": rid, "ts": rec.get("ts"), "skill": rec.get("skill"),
                                   "perk": rec.get("perk"), "decision": rec.get("decision"),
                                   "destructive": rec.get("destructive", False),
                                   "var_keys": rec.get("var_keys", []), "plan_sha": (rec.get("plan_sha") or "")[:12],
                                   "tlc": rec.get("tlc"), "problems": [p.get("id") for p in rec.get("problems", [])],
                                   "needs_approve": [], "restored": True})

    def _persist(self, run_id, snapshot):
        os.makedirs(os.path.join(self.root, run_id), exist_ok=True)
        open(self._path(run_id), "w").write(snapshot)

    def create(self, run_id, record):
        with self.lock:
            self.runs[run_id] = record
            while len(self.runs) > self.max_runs:            # evict the oldest (its ledger stays on disk)
                self.runs.pop(next(iter(self.runs)), None)
            snapshot = json.dumps(record, indent=2)
        self._persist(run_id, snapshot)                      # disk write outside the lock — less contention

    def get(self, run_id):
        with self.lock:
            return self.runs.get(run_id)

    def append(self, run_id, event):
        with self.lock:
            rec = self.runs.get(run_id)
            if rec is None:
                return None
            rec["events"].append(event)
            snapshot = json.dumps(rec, indent=2)
        self._persist(run_id, snapshot)
        return rec

    def ran_ok(self, run_id):
        with self.lock:
            rec = self.runs.get(run_id) or {}
            return {e["step"] for e in list(rec.get("events", []))
                    if e.get("type") == "step_result" and e.get("status") == "ok"}

    def steps_seen(self, run_id):
        """(granted, recorded) step-id sets — used to bind a step_result to a prior grant."""
        with self.lock:
            evs = list((self.runs.get(run_id) or {}).get("events", []))
        granted = {e["step"] for e in evs if e.get("type") == "granted"}
        done = {e["step"] for e in evs if e.get("type") == "step_result"}
        return granted, done

    def record_decision(self, summary):
        with self.lock:
            self.decisions.append(summary)

    def run_detail(self, run_id):
        """The full value-free record for one run (events, steps, plan hash, tlc) — for the review panel.
        Strips the session token; never holds values/output anyway."""
        with self.lock:
            rec = self.runs.get(run_id)
            rec = dict(rec) if rec else None
        return {k: v for k, v in rec.items() if k != "token"} if rec else None

    def monitor_snapshot(self):
        """A value-free snapshot for the dashboard: recent decisions, the recent runs with per-step
        progress, aggregate tool usage, and totals. Metadata only — no tokens, no values, no output."""
        with self.lock:
            decisions = list(self.decisions)
            allruns = [dict(r) for r in self.runs.values()]
        runs = sorted(allruns, key=lambda r: r.get("ts") or "", reverse=True)[:SNAPSHOT_RUNS]
        totals = collections.Counter(d["decision"] for d in decisions)
        tools, run_views, feed = {}, [], []
        for r in runs:
            seq = r.get("seq", [])
            ev = r.get("events", [])
            by_step = {e["step"]: e for e in ev if e.get("type") == "step_result"}
            granted = {e["step"] for e in ev if e.get("type") == "granted"}
            steps = []
            for i, tool in enumerate(seq, 1):
                res = by_step.get(str(i))
                state = ("ok" if res and res.get("status") == "ok" else
                         "error" if res else "granted" if str(i) in granted else "pending")
                steps.append({"n": i, "tool": tool, "state": state})
                t = tools.setdefault(tool, {"granted": 0, "ok": 0, "error": 0})
                if state == "ok":
                    t["ok"] += 1
                elif state == "error":
                    t["error"] += 1
                elif state == "granted":
                    t["granted"] += 1
            done = sum(1 for s in steps if s["state"] in ("ok", "error"))
            run_views.append({"run_id": r["run_id"], "ts": r.get("ts"), "skill": r.get("skill"),
                              "perk": r.get("perk"), "decision": r.get("decision"),
                              "destructive": r.get("destructive", False), "plan_sha": (r.get("plan_sha") or "")[:12],
                              "tlc": r.get("tlc"), "var_keys": r.get("var_keys", []), "steps": steps,
                              "restored": r.get("restored", False),
                              "progress": f"{done}/{len(seq)}" if seq else "-"})
            for e in ev:
                feed.append({"run_id": r["run_id"], "skill": r.get("skill"), "perk": r.get("perk"), **e})
        run_views.sort(key=lambda r: r["ts"] or "", reverse=True)
        feed.sort(key=lambda e: e.get("ts") or "", reverse=True)
        return {"now": now(), "totals": dict(totals), "runs_live": len(allruns),
                "decisions": list(reversed(decisions))[:200], "runs": run_views,
                "tools": tools, "feed": feed[:120]}


def authorize_step(store, run_id, step, plan_sha):
    """The live, server-side per-step gate: monitor the PLAN HASH (not the content), in order.
    The plan_sha the agent presents must equal the one govd pinned — anything else is inconsistent."""
    rec = store.get(run_id)
    if rec is None:
        return False, "unknown run_id"
    if rec["decision"] != "allow":
        return False, f"run not authorized (decision={rec['decision']})"
    if not plan_sha:
        return False, "missing plan_sha — cannot confirm the running plan is the blessed one"
    if plan_sha != rec["plan_sha"]:
        return False, "plan_sha inconsistent — the plan differs from the blessed one (diff to investigate)"
    if not str(step).isdigit() or int(step) < 1:
        return False, f"invalid step {step!r}"
    n = len(rec.get("seq", []))
    if int(step) > n:
        return False, f"step {step} > {n} declared"
    missing = [str(i) for i in range(1, int(step)) if str(i) not in store.ran_ok(run_id)]
    if missing:
        return False, f"upstream not recorded: {', '.join(missing)}"
    return True, "granted"


def result_acceptable(store, run_id, step, plan_sha):
    """A step_result (status only — never output) is recorded only if it follows a grant for that exact
    step with the blessed plan_sha and has not already been recorded — so the provenance/upstream ledger
    cannot be forged with unsolicited `status:ok` events."""
    rec = store.get(run_id)
    if rec is None:
        return False, "unknown run_id"
    if not plan_sha or plan_sha != rec["plan_sha"]:
        return False, "missing/inconsistent plan_sha"
    granted, done = store.steps_seen(run_id)
    if step not in granted:
        return False, f"step {step} was never granted — result rejected"
    if step in done:
        return False, f"step {step} already recorded"
    return True, "ok"


# ───────────────────────── minimal RFC 6455 WebSocket (stdlib only) ─────────────────────────

def _read_exact(rfile, n):
    buf = b""
    while len(buf) < n:
        chunk = rfile.read(n - len(buf))
        if not chunk:
            return None
        buf += chunk
    return buf


def ws_recv(rfile, max_len=MAX_WS_FRAME):
    """Read one client frame -> (opcode, payload bytes). 0x8 (close) is returned for EOF, an oversized
    frame, an unmasked data frame, or a truncated header — so the caller closes instead of buffering."""
    h = _read_exact(rfile, 2)
    if not h:
        return None, None
    opcode = h[0] & 0x0F
    masked = h[1] & 0x80
    ln = h[1] & 0x7F
    if ln == 126:
        ext = _read_exact(rfile, 2)
        if ext is None:
            return 0x8, b""
        ln = int.from_bytes(ext, "big")
    elif ln == 127:
        ext = _read_exact(rfile, 8)
        if ext is None:
            return 0x8, b""
        ln = int.from_bytes(ext, "big")
    if ln > max_len:                                     # refuse before reading the body (DoS guard)
        return 0x8, b""
    if not masked and opcode in (0x0, 0x1, 0x2):         # RFC 6455 §5.1: client data frames MUST be masked
        return 0x8, b""
    mask = _read_exact(rfile, 4) if masked else b"\x00\x00\x00\x00"
    if mask is None:
        return 0x8, b""
    data = _read_exact(rfile, ln) if ln else b""
    if ln and data is None:
        return 0x8, b""
    data = bytearray(data)
    if masked:
        for i in range(len(data)):
            data[i] ^= mask[i % 4]
    return opcode, bytes(data)


def ws_send(wfile, payload, opcode=0x1):
    """Send one server frame (unmasked, single-frame)."""
    if isinstance(payload, str):
        payload = payload.encode()
    ln = len(payload)
    hdr = bytearray([0x80 | opcode])
    if ln < 126:
        hdr.append(ln)
    elif ln < 65536:
        hdr.append(126); hdr += ln.to_bytes(2, "big")
    else:
        hdr.append(127); hdr += ln.to_bytes(8, "big")
    wfile.write(bytes(hdr) + payload)
    wfile.flush()


# ───────────────────────── HTTP / WS handler ─────────────────────────

class Handler(BaseHTTPRequestHandler):
    server_version = "cyberware-govd/1.0"
    protocol_version = "HTTP/1.1"
    timeout = SOCKET_TIMEOUT                 # StreamRequestHandler applies this to the socket — no slowloris

    def log_message(self, *a):    # quiet — govd prints its own audit lines
        pass

    def _json(self, code, obj):
        body = json.dumps(obj, indent=2).encode()
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    # --- GET ---
    def do_GET(self):
        cfg, store = self.server.cfg, self.server.store
        host, port = self.server.server_address[0], self.server.server_address[1]
        if self.path == "/health":
            return self._json(200, {"status": "ok", "service": "cyberware-govd", "mode": cfg["mode"],
                                    "host": host, "port": port, "registry": os.path.join(ROOT, "skills"),
                                    "runs": len(store.runs)})
        path = self.path.split("?", 1)[0]
        if path == "/catalog":
            # value-free discovery (names · perks · var-KEYS · skill_sha · verified) — ungated like /health,
            # so an agent can ask "what do you govern?" before it claims. No values, no run data.
            return self._json(200, catalog_snapshot())
        if path.startswith("/flow/"):
            # the skill's lifecycle diagram (blueprint.svg) for the dashboard Flow tab — a value-free
            # registry artifact, ungated like /catalog. Path-safe: only an EXACT known skill name is
            # served, so the path can never escape the registry.
            skill = urllib.parse.unquote(path[len("/flow/"):])
            if skill in set(skill_index.all_skills()):
                svgp = os.path.join(ROOT, "skills", skill, "blueprint.svg")
                if os.path.isfile(svgp):
                    return self._svg(open(svgp, "rb").read())
            return self._json(404, {"error": "no flow diagram", "skill": skill})
        if path in ("/", "/dashboard"):
            return self._dashboard()
        if path == "/monitor/state":
            if not self._monitor_authed(cfg):
                return self._json(403, {"error": "missing/invalid monitor token (?token= or X-Govd-Monitor)"})
            return self._json(200, store.monitor_snapshot())
        if path.startswith("/monitor/run/"):
            if not self._monitor_authed(cfg):
                return self._json(403, {"error": "missing/invalid monitor token"})
            detail = store.run_detail(path.split("/monitor/run/", 1)[1])
            return self._json(200 if detail else 404, detail or {"error": "unknown run_id"})
        if self.path.startswith("/ledger/"):
            tail = self.path.split("/ledger/", 1)[1]
            run_id = tail.split("?", 1)[0]
            rec = store.get(run_id)
            if rec is None:
                return self._json(404, {"error": "unknown run_id"})
            if not self._authed(rec):                        # bank-session: the run's token, or no access
                return self._json(403, {"error": "missing/invalid session token for this run"})
            return self._json(200, {k: v for k, v in rec.items() if k != "token"})
        if self.path == "/oversight":
            return self._ws_oversight()
        return self._json(404, {"error": "not found", "path": self.path})

    def _token_presented(self):
        q = urllib.parse.urlparse(self.path).query
        return self.headers.get("X-Govd-Token") or urllib.parse.parse_qs(q).get("token", [None])[0]

    def _authed(self, rec):
        want = str(rec.get("token") or "")
        got = str(self._token_presented() or "")
        return bool(want) and hmac.compare_digest(got, want)

    def _monitor_authed(self, cfg):
        want = str(cfg.get("monitor_token") or "")
        q = urllib.parse.urlparse(self.path).query
        got = str(self.headers.get("X-Govd-Monitor") or urllib.parse.parse_qs(q).get("token", [""])[0])
        return bool(want) and hmac.compare_digest(got, want)

    def _dashboard(self):
        try:
            body = open(os.path.join(HERE, "govd_dashboard.html"), "rb").read()
        except OSError:
            return self._json(500, {"error": "dashboard asset missing"})
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _svg(self, body):
        self.send_response(200)
        self.send_header("Content-Type", "image/svg+xml")
        self.send_header("Cache-Control", "max-age=300")     # the lifecycle diagram is static per skill
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    # --- POST /govern ---
    def do_POST(self):
        if self.path != "/govern":
            return self._json(404, {"error": "not found", "path": self.path})
        cfg, store = self.server.cfg, self.server.store
        try:
            n = int(self.headers.get("Content-Length", 0))
            if n > MAX_BODY:
                return self._json(413, {"error": f"request body too large ({n} > {MAX_BODY})"})
            ledger = json.loads(_read_exact(self.rfile, n) or b"{}") if n else {}
        except Exception as e:
            return self._json(400, {"error": f"bad request body: {e}"})
        if not isinstance(ledger, dict):
            return self._json(400, {"error": "request body must be a JSON object (task-ledger)"})

        try:
            v = govern(ledger, cfg)
        except Exception as e:                           # never leak a stack trace; never 500 the thread
            return self._json(400, {"error": f"govern failed: {type(e).__name__}: {e}"})
        run_id = uuid.uuid4().hex[:16]
        # a per-run session token — the run's private credential (like a bank session). Issued once, here,
        # only to the caller; required to open the WS or read the ledger for this run.
        token = secrets.token_urlsafe(32) if v["decision"] == "allow" else None
        # the record is value-free: var KEYS (names), the perk metadata, and the blessed plan + its hash.
        # No values, no file contents, no secrets, no command output ever enter the ledger.
        var_keys = sorted(ledger.get("var_keys") or ledger.get("vars") or [])
        plan = v.get("plan")
        record = {"run_id": run_id, "ts": now(), "skill": ledger.get("skill"), "perk": ledger.get("perk"),
                  "token": token, "var_keys": var_keys, "decision": v["decision"],
                  "destructive": v.get("destructive", False), "approved": v.get("approved", []),
                  "plan_sha": v.get("plan_sha"), "snippet_shas": (plan or {}).get("snippet_shas", {}),
                  "seq": v.get("seq", []), "wrapper": (plan or {}).get("wrapper", ""), "tlc": v.get("tlc"),
                  "tlc_tla": v.get("tlc_tla"), "tlc_log": v.get("tlc_log"),   # the model-check spec + full output
                  "problems": v.get("problems", []), "events": []}
        if v["decision"] == "allow":                     # only authorized runs are persisted (bounds growth)
            store.create(run_id, record)
        # every decision (incl. push_back/reject) is logged for the monitor — metadata only, no token
        store.record_decision({"run_id": run_id, "ts": record["ts"], "skill": record["skill"],
                               "perk": record["perk"], "decision": v["decision"],
                               "destructive": v.get("destructive", False), "var_keys": var_keys,
                               "plan_sha": (v.get("plan_sha") or "")[:12], "tlc": v.get("tlc"),
                               "problems": [p.get("id") for p in v.get("problems", [])],
                               "needs_approve": v.get("needs_approve", [])})
        print(f"  /govern {ledger.get('skill')}/{ledger.get('perk')} -> {v['decision']}  (run {run_id})")

        # advertise a ws host the caller can actually dial: the Host it used, not our bind address (0.0.0.0)
        ws_host = cfg.get("advertise_host") or self.headers.get("Host") or host_for_ws(self.server)
        resp = {"run_id": run_id, "decision": v["decision"], "problems": v.get("problems", []),
                "destructive": v.get("destructive", False), "needs_approve": v.get("needs_approve", []),
                "plan_sha": v.get("plan_sha"), "tlc": v.get("tlc"), "ws": f"ws://{ws_host}/oversight"}
        if v["decision"] == "allow":
            resp["plan"] = plan                          # value-free: sequence + wrapper + src-closure hashes
            resp["session_token"] = token                # present this on the WS and to GET /ledger
        code = {"allow": 200, "push_back": 409, "reject": 403}[v["decision"]]
        return self._json(code, resp)

    # --- WS /oversight ---
    def _ws_oversight(self):
        self.close_connection = True
        key = self.headers.get("Sec-WebSocket-Key")
        if not key:
            return self._json(400, {"error": "expected a WebSocket upgrade on /oversight"})
        accept = base64.b64encode(hashlib.sha1((key + WS_GUID).encode()).digest()).decode()
        self.send_response(101)
        self.send_header("Upgrade", "websocket")
        self.send_header("Connection", "Upgrade")
        self.send_header("Sec-WebSocket-Accept", accept)
        self.end_headers()
        store = self.server.store
        bound = None                                              # the run_id this session is authenticated to
        try:
            while True:
                op, data = ws_recv(self.rfile)
                if op is None or op == 0x8:                       # closed
                    break
                if op == 0x9:                                    # ping -> pong
                    ws_send(self.wfile, data, 0xA); continue
                if op != 0x1:
                    continue
                try:
                    msg = json.loads(data.decode())
                except Exception:
                    ws_send(self.wfile, json.dumps({"type": "error", "reason": "bad json"})); continue
                t = msg.get("type")
                if t == "hello":
                    # bank-session auth: bind ONLY with the run's session token; otherwise close.
                    rid = msg.get("run_id")
                    rec = store.get(rid)
                    if rec is None or not hmac.compare_digest(str(msg.get("token") or ""),
                                                              str(rec.get("token") or "")):
                        ws_send(self.wfile, json.dumps({"type": "hello_ack", "run_id": rid, "authorized": False,
                                "reason": "unknown run or invalid session token"}))
                        break
                    bound = rid
                    ws_send(self.wfile, json.dumps({"type": "hello_ack", "run_id": rid, "authorized": True,
                            "decision": rec["decision"]}))
                elif not bound:                                  # every step op requires an authenticated session
                    ws_send(self.wfile, json.dumps({"type": "error",
                            "reason": "not authenticated — send hello with the run's session token first"}))
                elif t == "step_request":
                    step = str(msg.get("step"))                  # the session is bound — operate only on `bound`
                    psha = msg.get("plan_sha")
                    ok, reason = authorize_step(store, bound, step, psha)
                    reply = {"type": "grant" if ok else "refuse", "step": msg.get("step"), "reason": reason}
                    if ok:                                       # record the grant so a result can bind to it
                        store.append(bound, {"type": "granted", "ts": now(), "step": step, "plan_sha": psha})
                    else:
                        ev = {"type": "step_refused", "ts": now(), "step": step, "reason": reason}
                        # inconsistency path: investigate by PLAIN TEXT DIFF, never by executing the plan.
                        # The diff goes back to the authenticated caller; the ledger keeps only a line count
                        # (agent free text never lands in the server-side audit record).
                        if "inconsistent" in reason and msg.get("plan_wrapper") is not None:
                            diff = plan_diff((store.get(bound) or {}).get("wrapper", ""), msg.get("plan_wrapper"))
                            ev["diff_lines"] = sum(1 for ln in diff.splitlines()
                                                   if ln[:1] in "+-" and not ln.startswith(("+++", "---")))
                            reply["diff"] = diff
                        store.append(bound, ev)
                    ws_send(self.wfile, json.dumps(reply))
                elif t == "step_result":
                    step = str(msg.get("step"))                  # STATUS only — never command output/content
                    ok, why = result_acceptable(store, bound, step, msg.get("plan_sha"))
                    if not ok:                                   # a result that did not follow a grant is rejected
                        ws_send(self.wfile, json.dumps({"type": "error", "step": step, "reason": why}))
                        continue
                    ev = {"type": "step_result", "ts": now(), "step": step,
                          "status": msg.get("status"), "exit": msg.get("exit")}
                    rec = store.append(bound, ev)
                    ws_send(self.wfile, json.dumps({"type": "recorded" if rec else "error",
                            "step": ev["step"], "index": len(rec["events"]) if rec else None}))
                else:
                    ws_send(self.wfile, json.dumps({"type": "error", "reason": f"unknown type {t}"}))
        except (ConnectionError, OSError):
            pass


def host_for_ws(server):
    h, p = server.server_address[0], server.server_address[1]
    return f"{h}:{p}"


# ───────────────────────── serve ─────────────────────────

def bind_server(host, ports, handler=Handler):
    """Bind the first free port — 'monitor rotate if one is occupied' (local mode)."""
    for p in ports:
        try:
            return ThreadingHTTPServer((host, p), handler), p
        except OSError as e:
            print(f"  port {p} unavailable ({e.errno}) — rotating", file=sys.stderr)
    return None, None


def serve(cfg):
    Handler.timeout = cfg.get("socket_timeout", SOCKET_TIMEOUT)
    ensure_monitor_token(cfg)                            # final mode is known here (after --mode)
    store = Store(cfg["record_root"])
    if cfg["mode"] == "remote":
        host, ports = cfg["remote"]["host"], [cfg["remote"]["port"]]
    else:
        host, ports = cfg["local"]["host"], cfg["local"]["ports"]
    httpd, port = bind_server(host, ports)
    if httpd is None:
        raise SystemExit(f"govd: no free port among {ports}")
    httpd.daemon_threads = True
    httpd.cfg, httpd.store = cfg, store
    dash_host = "127.0.0.1" if host in ("0.0.0.0", "::") else host
    print(f"govd · {cfg['mode']} · http://{host}:{port}  ·  ws://{host}:{port}/oversight")
    print(f"  registry={os.path.join(ROOT, 'skills')}   record_root={store.root}")
    print(f"  dashboard:  http://{dash_host}:{port}/?token={cfg['monitor_token']}"
          + ("   (default local token 'admin' — set GOVD_MONITOR_TOKEN to change)"
             if cfg["monitor_token"] == "admin" else ""))
    print("  control/audit plane — govd governs the claim + records status; it never sees data, never runs.")
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        print("\ngovd: shutting down")
        httpd.shutdown()


def main():
    ap = argparse.ArgumentParser(description="cyberware governance server (observe + govern)")
    ap.add_argument("--config", default=None)
    ap.add_argument("--mode", choices=["local", "remote"], default=None)
    ap.add_argument("--port", type=int, default=None)
    a = ap.parse_args()
    cfg = load_config(a.config)
    if a.mode:
        cfg["mode"] = a.mode
    if a.port:
        if cfg["mode"] == "remote":
            cfg["remote"]["port"] = a.port
        else:
            cfg["local"]["ports"] = [a.port]
    serve(cfg)


if __name__ == "__main__":
    main()
