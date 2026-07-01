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
  GET  /health                        -> mode, port, registry, chip_sha + acquisition provenance, run count
  GET  /catalog                       -> value-free discovery: skills · perks · var-KEYS · skill_sha · verified
  GET  /flow/run/<run_id>             -> THIS run's task-blueprint SVG (perk's gated sequence; value-free; monitor-gated)
  GET  /flow/<skill>                  -> the skill's generic lifecycle blueprint.svg (value-free; fallback)
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

from infra import registry
from infra.cwp import canonical
from infra.govern import compiler
from infra.govern import composer
from infra.govern import delegate    # P2-T12: server-side execution delegated to exod the limb (containment)
from infra.govern import feed        # P5-T02: SSE framing + pagination + change-digest (prose-clean core)
from infra.govern import lease as _lease  # P5-T04: active-passive single-writer advisory-lock lease (off by default)
from infra.govern import principals  # P1-T08: Bearer-principal auth + token-bucket rate-limit at /govern
from infra.govern import skillacl     # ACCESS-1: the skill's intrinsic access policy (access.json), gate 2 of 3
from infra.govern import tracing     # P5-T05: W3C traceparent across planes + in-toto run provenance
from infra.tool import skill_index   # verify the registry matches its committed per-skill authenticity index
from infra.settle import budget, credit_price   # per-actor CREDIT budget — the gauge + the pricing-stage shutoff
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
DECISIONS_PER_PAGE = 200  # default page size for the paginated decisions feed (P5-T02)
SSE_MAX_STREAMS = 32      # cap on concurrent /monitor/stream connections (P5-T02; bounds thread/socket use)
_SSE_LOCK = threading.Lock()
_SSE_ACTIVE = [0]         # live SSE stream count (list = a mutable box guarded by _SSE_LOCK)
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
    cfg["node_name"] = os.environ.get("GOVD_NODE_NAME") or cfg.get("node_name")   # local-mode runs attribute HERE
    # the monitor (dashboard) token — gates the dashboard. env > config; the default is filled by
    # ensure_monitor_token() once the FINAL mode is known (after any --mode override).
    cfg["monitor_token"] = os.environ.get("GOVD_MONITOR_TOKEN") or cfg.get("monitor_token") or None
    # P1-T08: the principals registry (id -> token_sha -> quota). A present registry makes Authorization:
    # Bearer mandatory at /govern; absent (local dev) -> auth off, every record carries principal "local".
    pr_path = os.environ.get("GOVD_PRINCIPALS") or cfg.get("principals_path")
    cfg["principals"] = principals.load_principals(pr_path) if pr_path else (cfg.get("principals") or {})
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
_FLOW_CACHE = {}                                         # run_id -> the rendered task-blueprint SVG (record static)


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


def chip_sha():
    """The chip's identity — the roll-up sha from the chip manifest (cached; the chip is static at runtime)."""
    if "sha" not in _CATALOG_CACHE:
        mp = os.path.join(registry.SKILLCHIP, registry.CHIP_MANIFEST)
        _CATALOG_CACHE["sha"] = json.load(open(mp)).get("chip_sha") if os.path.isfile(mp) else None
    return _CATALOG_CACHE["sha"]


def chip_provenance():
    """How this chip was acquired (chipfetch hands it over: local baked, or cloud source@ref#commit)."""
    try:
        return json.loads(os.environ.get("GOVD_CHIP_PROVENANCE") or "null")
    except ValueError:
        return None


def task_flow_svg(rec):
    """The run's TASK blueprint as SVG — the perk's actual gated sequence with each gate bound to the
    concrete contract check it stands for (NOT the generic skill lifecycle). Rendered VALUE-FREE: var KEYS
    appear as `${KEY}` placeholders (never values) and the run dir as `$RUN`, so it's built purely from the
    value-free record (skill · perk · seq · var_keys). Cached per run (the record is static)."""
    rid = rec.get("run_id")
    if rid in _FLOW_CACHE:
        return _FLOW_CACHE[rid]
    from infra.tool import visualize
    keys = rec.get("var_keys") or []
    L = {"skill": rec.get("skill"), "perk": rec.get("perk"), "vars": {k: "${" + k + "}" for k in keys}}
    bp = compiler.task_blueprint(L, "$RUN", rec.get("seq") or None)   # $RUN placeholder — no real path either
    out = visualize.svg(bp, (bp.get("task") or {}).get("tools"))
    _FLOW_CACHE[rid] = out
    return out
_TLC_LOCK = threading.Lock()


def tlc_check(bp):
    """The TLA+/TLC deadlock model check, run here in the control plane and cached per blueprint (so TLC
    runs once per skill). Returns (ok, msg, tla, output): the verdict plus the TLA+ spec and TLC's FULL log
    (ok None = TLC unavailable, structural check governs; in the container the jar is present so it's real)."""
    key = canonical.digest(bp)
    with _TLC_LOCK:
        if key in _TLC_CACHE:
            return _TLC_CACHE[key]
    tla = composer.emit_tla(bp)
    ok, msg, out = composer.run_tlc(tla, "task")
    with _TLC_LOCK:
        _TLC_CACHE[key] = (ok, msg, tla, out)
    return _TLC_CACHE[key]


def govern(ledger, cfg, *, scope=None, principal=None, local_dev=False, principal_tier=None, strict=False,
           now=None, budget_enforce=False, budget_balance=None, budget_configured=False):
    """Govern a CLAIM — never payload. The agent sends skill, perk, and var KEYS (names only, no values,
    no file contents, no secrets); govd checks the claim against its OWN trusted registry and blesses a
    value-free execution PLAN (sequence + snippet hashes + wrapper), pinning its sha256. Destructiveness
    is a property of the declared perk, gated by approval — govd never inspects task data to decide it.
    `scope` is the authenticated principal's per-actor ACL (M0; None = unscoped, `strict` denies the
    unscoped case); it can only ADD a hard, non-self-approvable reject, never relax another gate.
    Pure: returns a verdict dict, writes nothing."""
    skill, perk = ledger.get("skill"), ledger.get("perk")
    var_keys = list(ledger.get("var_keys") or ledger.get("vars") or [])   # accept a name list or a dict's keys
    approve = list(ledger.get("approve", []))
    problems = []

    if not skill or not perk:
        return {"decision": "reject", "problems": [{"id": "missing_skill_or_perk"}]}
    # NAMESPACE shim: canonicalize a BARE claim to its `ns:name` against THIS govd's registry (existing agents
    # keep working); an AMBIGUOUS bare name (>=2 namespaces own it) is REJECTED here, never silently routed; a
    # namespaced claim passes through. Everything downstream then sees the ONE canonical id.
    skill = registry.canonicalize(skill)
    if skill == registry.AMBIGUOUS:
        return {"decision": "reject", "problems": [{"id": "ambiguous_skill_id", "detail": ledger.get("skill")}]}
    # canonical-name guard: the perk, like the skill, must be a single safe path segment — never `/`, `..`,
    # `./perk`, or `perk/` (which `os.path.join` would collapse so a DIFFERENT perk runs than the one the
    # ACL/destructive/tier checks see). The byte-exact id match below closes the case-insensitive-FS variant.
    if not registry.valid_skill_name(perk):
        return {"decision": "reject", "problems": [{"id": "noncanonical_name", "detail": f"{skill}/{perk}"}]}
    pdir = os.path.join(registry.skill_dir(skill), "perks", perk)
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
        sdir = registry.skill_dir(skill)
        bp = json.load(open(os.path.join(sdir, "blueprint.json")))
        perks = json.load(open(os.path.join(sdir, "perks.json")))["perks"]
    except (OSError, ValueError, KeyError) as e:
        return {"decision": "reject", "problems": [{"id": "registry_error", "detail": str(e)}]}
    destructive = next((p.get("destructive", False) for p in perks if p.get("id") == perk), False)

    # canonical-id check: `skill`/`perk` must be the BYTE-EXACT on-disk ids, not merely an isdir hit — on a
    # case-insensitive FS `CWS-FS`/`READ` resolve to the real dir but would mismatch the (case-sensitive) ACL
    # and read the wrong destructive/tier. Reject the variant so the string the ACL checks is the one that runs.
    if skill not in set(skill_index.all_skills()) or perk not in {p.get("id") for p in perks}:
        return {"decision": "reject", "problems": [{"id": "noncanonical_name", "detail": f"{skill}/{perk}"}]}

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

    # per-actor ACL gate (M0): the authenticated principal's capability scope (None = unscoped). A PURE
    # RESTRICTION — it only APPENDS a problem (a hard, non-self-approvable reject), never relaxes a gate.
    # perk_tier + credentialed come from govd's OWN trusted registry + the blessed plan, never task data.
    perk_tier = delegate.perk_sandbox_tier(skill, perk)
    credentialed = bool((plan or {}).get("credential_ids"))
    parameterized = bool(ledger.get("binds"))       # claim-declared dir binds -> params axis (values re-gated at the WS step)
    acl_ok, acl_problem = principals.acl_allows(scope, skill, perk, perk_tier, destructive, credentialed,
                                                parameterized=parameterized, now=now, strict=strict)
    if not acl_ok:
        problems.append(acl_problem)

    # ACCESS-1 (skill-intrinsic): the skill's OWN access policy (access.json), independent of WHO claims it —
    # an independent fail-closed AND beside the per-actor ACL, a pure restriction that only APPENDS a problem.
    # Local govd mode / a local_dev principal is open; otherwise a declared policy governs, and an undeclared
    # skill is remote-closed only once the `skillacl_enforce` rollout flag is on (back-compat until then).
    sa_ok, sa_problem = skillacl.access_allows(
        skillacl.load_access(skill), mode=(cfg.get("mode") or "local"), is_local_dev=local_dev,
        principal=principal, principal_tier=principal_tier, perk=perk,
        enforce_default_closed=bool(cfg.get("skillacl_enforce")))
    if not sa_ok:
        problems.append(sa_problem)

    # 5. decide on the CLAIM: structural problems reject; a destructive perk needs explicit approval
    needs_approve = []
    if destructive and not ({perk, "destructive"} & set(approve)):
        needs_approve = [perk]

    # 6. BUDGET gate — the LAST restriction (a CREDIT / shutoff gate). Price the otherwise-allowable, non-
    #    pending claim in CREDITS and check the actor's balance (do_POST read it + passes the snapshot in;
    #    govern stays I/O-free). A PURE restriction — only APPENDS a hard, non-self-approvable problem, never
    #    relaxes a gate. Skipped when the claim already rejects or merely awaits approval (we don't reserve
    #    credits for those). This snapshot check is the clean reject reason; the AUTHORITATIVE atomic debit
    #    happens in do_POST on allow (closing the read-then-debit race).
    cost = None
    if budget_enforce and not problems and not needs_approve:
        price_c = credit_price.credit_price(skill, perk, pricing=cfg.get("pricing"))
        cost = str(price_c.amount)
        b_ok, b_problem = budget.budget_ok(principal, price_c, budget_balance, configured=budget_configured)
        if not b_ok:
            problems.append(b_problem)

    decision = "reject" if problems else ("push_back" if needs_approve else "allow")
    return {"decision": decision, "problems": problems, "destructive": destructive,
            "skill": skill,                              # the CANONICAL ns:name govern() resolved + gated on —
            "approved": [a for a in approve if a in (perk, "destructive")],  # the record persists THIS, so every
            "plan": plan, "plan_sha": psha, "seq": plan["sequence"],         # downstream re-check keys off it too
            "tlc": tlc_msg, "tlc_tla": tlc_tla, "tlc_log": tlc_out,   # the model-check spec + full log
            "cost": cost,                                # the value-free CREDIT price (None when unmetered)
            "needs_approve": needs_approve}


def porter_sources(skill, perk, seq):
    """The blessed porter source for each tool in a run's sequence, read from govd's OWN registry —
    the same public chip code `/catalog` exposes (program text, never values or command output). For the
    monitor's Script tab, so a reviewer reads exactly what the call runs, not just the value-free wrapper."""
    out = {}
    try:
        sd = registry.skill_dir(skill)
    except Exception:
        return out
    srcdir = os.path.join(sd, "perks", perk or "", "src")
    for tool in (seq or []):
        for ext in (".sh", ".py"):
            p = os.path.join(srcdir, str(tool) + ext)
            if os.path.isfile(p):
                try:
                    out[str(tool) + ext] = open(p, encoding="utf-8").read()
                except OSError:
                    pass
    return out


# ───────────────────────── server-side provenance store ─────────────────────────

class Store:
    """The provenance ledger — server-owned, one private session per run. One dir per run under
    record_root; the agent never writes here. In-memory runs are capped (oldest evicted, disk retained)
    so the server stays bounded under high concurrency."""

    def __init__(self, root, max_runs=MAX_RUNS, cfg=None):
        self.root = os.path.abspath(os.path.expanduser(root))
        os.makedirs(self.root, exist_ok=True)
        self.lock = threading.Lock()
        self.runs = {}                                       # insertion-ordered -> oldest is first
        self._inflight = {}                                  # run_id -> {step}: delegated steps mid-execution
        self.max_runs = max_runs
        self.decisions = collections.deque(maxlen=500)       # every /govern verdict (metadata, for the monitor)
        self.decisions_log = os.path.join(self.root, "decisions.jsonl")  # durable, append-only: ALL verdicts
        self._hydrate()                                      # load persisted ledgers (mounted record_root)
        # P5-T01: the chained-JSONL ARTIFACT OF RECORD + a DERIVED StoreBackend index live behind StoreMirror
        # (infra/store/mirror.py), OUT of this enforcement-surface file. The decision path only hands the mirror
        # value-free snapshots; a single async worker writes chain-first then index, off the request thread and
        # exception-isolated. The in-memory runs + ledger.json remain the authoritative hot-path state.
        from infra.store.mirror import StoreMirror
        self.mirror = StoreMirror(self.root, cfg)

    def _path(self, run_id): return os.path.join(self.root, run_id, "ledger.json")

    def _hydrate(self):
        """Load existing per-run ledgers from disk (most recent up to max_runs) so a restarted server with
        a MOUNTED record_root still shows history for review. The decisions feed — which includes
        rejects/push-backs that are NOT persisted as run dirs — is reloaded from the durable, append-only
        decisions.jsonl; for a legacy record_root without that file, it is rebuilt from the (allow-only)
        ledgers so nothing regresses."""
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
        # the decisions feed = allow runs (from their ledgers, incl. legacy record_roots) UNION every verdict
        # (from the durable log, incl. rejects/push-backs), deduped by run_id and chronological — so both the
        # historical allows AND the durable rejects survive a restart.
        by_id = {}
        for rid, rec in self.runs.items():
            by_id[rid] = {"run_id": rid, "ts": rec.get("ts"), "skill": rec.get("skill"), "perk": rec.get("perk"),
                          "decision": rec.get("decision"), "destructive": rec.get("destructive", False),
                          "var_keys": rec.get("var_keys", []), "plan_sha": (rec.get("plan_sha") or "")[:12],
                          "tlc": rec.get("tlc"), "problems": [p.get("id") for p in rec.get("problems", [])],
                          "needs_approve": [], "restored": True}
        if os.path.isfile(self.decisions_log):
            for line in open(self.decisions_log).read().splitlines():
                try:
                    s = json.loads(line); s["restored"] = True
                    by_id[s.get("run_id") or len(by_id)] = s     # the durable log is authoritative for its verdicts
                except ValueError:
                    continue
        for s in sorted(by_id.values(), key=lambda x: x.get("ts") or "")[-self.decisions.maxlen:]:
            self.decisions.append(s)
        # non-allow verdicts (reject/push_back) get NO per-run dir — only the metadata feed. Restore them into
        # the navigable run list too, so the monitor's overview shows them after a restart (their submitted
        # ledger + problems survive; the value-free plan/script is not retained for a non-allow run).
        for s in self.decisions:
            rid = s.get("run_id")
            if rid and rid not in self.runs and s.get("decision") in ("reject", "push_back"):
                self.runs[rid] = {"run_id": rid, "ts": s.get("ts"), "skill": s.get("skill"), "perk": s.get("perk"),
                                  "decision": s.get("decision"), "destructive": s.get("destructive", False),
                                  "var_keys": s.get("var_keys", []), "plan_sha": s.get("plan_sha"),
                                  "problems": [{"id": p} for p in (s.get("problems") or [])],
                                  "seq": [], "events": [], "wrapper": "", "restored": True}
        while len(self.runs) > self.max_runs:                 # keep the in-memory cap after restoring non-allow
            self.runs.pop(next(iter(self.runs)), None)

    def _persist(self, run_id, snapshot):
        # crash-atomic: write to a UNIQUE temp file, fsync, then os.replace (atomic rename) — a crash mid-write
        # never leaves a torn/partial record, and a unique-per-writer tmp name means two concurrent persists of
        # the SAME run_id can't race on a shared tmp (the pattern infra/cwp/ledger.py uses). Clean the tmp on
        # any error path so a failed write never litters the run dir.
        os.makedirs(os.path.join(self.root, run_id), exist_ok=True)
        path = self._path(run_id)
        tmp = f"{path}.tmp.{os.getpid()}.{uuid.uuid4().hex[:8]}"
        try:
            with open(tmp, "w") as f:
                f.write(snapshot)
                f.flush()
                os.fsync(f.fileno())
            os.replace(tmp, path)
        except BaseException:
            try:
                os.remove(tmp)
            except OSError:
                pass
            raise

    def create(self, run_id, record):
        with self.lock:
            self.runs[run_id] = record
            while len(self.runs) > self.max_runs:            # evict the oldest (its ledger stays on disk)
                self.runs.pop(next(iter(self.runs)), None)
            snapshot = json.dumps(record, indent=2)
        self._persist(run_id, snapshot)                      # disk write outside the lock — less contention
        try:                                                 # P5-T01: async value-free mirror; never fails create
            self.mirror.record_run(run_id, record)
        except Exception as e:
            sys.stderr.write(f"[govd] mirror (create {run_id}) skipped: {e}\n")

    def remember(self, run_id, record):
        """Keep a NON-allow verdict (push_back / reject) in memory only — navigable + inspectable in the
        monitor (its submitted ledger, blessed plan, and problems) — but NOT written to disk. Only allow
        runs get a durable per-run ledger dir; the verdict itself still lands in the durable decisions feed."""
        with self.lock:
            self.runs[run_id] = record
            while len(self.runs) > self.max_runs:            # same in-memory cap; oldest evicted
                self.runs.pop(next(iter(self.runs)), None)

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
            plan_sha = rec.get("plan_sha", "")
        self._persist(run_id, snapshot)
        try:
            self.mirror.record_event(run_id, plan_sha, event)
        except Exception as e:
            sys.stderr.write(f"[govd] mirror (event {run_id}) skipped: {e}\n")
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

    def claim_step(self, run_id, step):
        """Atomically reserve (run_id, step) for ONE delegated execution. Returns True for the FIRST caller
        only; False if the step already RAN (a recorded ok/error step_result) OR is already in flight on
        another connection. The reservation spans the whole check->dial-exod->record window (release_step
        clears it), so two concurrent WS sessions bound to the same run cannot both execute the same step —
        the at-most-once / no-double-bill invariant holds under concurrency, not just sequential re-sends."""
        with self.lock:
            rec = self.runs.get(run_id)
            if rec is None:
                return False
            done = {e["step"] for e in rec.get("events", []) if e.get("type") == "step_result"}
            held = self._inflight.setdefault(run_id, set())
            if step in done or step in held:
                return False
            held.add(step)
            return True

    def release_step(self, run_id, step):
        """Drop the in-flight reservation once the result is recorded (or after a non-terminal refusal). A
        completed step stays blocked by its recorded step_result; a refused step (recorded under a distinct
        type, outside `done`) becomes retryable."""
        with self.lock:
            held = self._inflight.get(run_id)
            if held is not None:
                held.discard(step)
                if not held:
                    self._inflight.pop(run_id, None)

    def record_decision(self, summary):
        with self.lock:
            self.decisions.append(summary)
            try:                                             # durable audit: append EVERY verdict (incl. rejects/
                with open(self.decisions_log, "a") as f:     # push-backs) so it survives a restart, even though
                    f.write(json.dumps(summary) + "\n")      # only ALLOW runs get a full per-run ledger dir
            except OSError:
                pass
        try:                                                 # P5-T01: async chain+index mirror, off the decision path
            self.mirror.decision(summary)
        except Exception as e:
            sys.stderr.write(f"[govd] mirror (decision) skipped: {e}\n")

    def run_detail(self, run_id):
        """The full value-free record for one run (events, steps, plan hash, tlc) — for the review panel.
        Strips the session token; never holds values/output anyway."""
        with self.lock:
            rec = self.runs.get(run_id)
            rec = dict(rec) if rec else None
        return {k: v for k, v in rec.items() if k != "token"} if rec else None

    def monitor_snapshot(self, dec_page=1, dec_limit=DECISIONS_PER_PAGE):
        """A value-free snapshot for the dashboard: a PAGE of recent decisions (newest first, P5-T02), the
        recent runs with per-step progress, aggregate tool usage, and totals. Metadata only — no tokens, no
        values, no output. `dec_page`/`dec_limit` page the decisions feed; `decisions_page` carries the
        page/pages/total/limit so the dashboard can navigate without a growing payload."""
        with self.lock:
            decisions = list(self.decisions)
            allruns = [dict(r) for r in self.runs.values()]
        runs = sorted(allruns, key=lambda r: r.get("ts") or "", reverse=True)[:SNAPSHOT_RUNS]
        totals = collections.Counter(d["decision"] for d in decisions)
        tools, run_views, step_feed = {}, [], []
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
                              "failed": any(s["state"] == "error" for s in steps),   # an allowed run whose step erred
                              "progress": f"{done}/{len(seq)}" if seq else "-"})
            for e in ev:
                step_feed.append({"run_id": r["run_id"], "skill": r.get("skill"), "perk": r.get("perk"), **e})
        run_views.sort(key=lambda r: r["ts"] or "", reverse=True)
        step_feed.sort(key=lambda e: e.get("ts") or "", reverse=True)
        dec = feed.paginate(list(reversed(decisions)), dec_page, dec_limit)   # newest-first, one page
        return {"now": now(), "totals": dict(totals), "runs_live": len(allruns),
                "decisions": dec["items"],
                "decisions_page": {k: dec[k] for k in ("page", "pages", "total", "limit")},
                "runs": run_views, "tools": tools, "feed": step_feed[:120]}


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


def step_reauthorize(cfg, rec0, *, now=None):
    """Re-bind authority on an IN-FLIGHT step to the LIVE registry + skill policy — mirroring the two claim-time
    gates so revocation, a tightened scope, a tightened access.json, or a flipped rollout flag binds a running
    multi-step run (not only the claim). Returns (True, None) or (False, '<gate>:<problem id>').

    The two gates have different dependencies: ACCESS-2 (the per-actor ACL) NEEDS the live principals registry;
    ACCESS-1 (the skill-intrinsic gate) is registry-INDEPENDENT and runs even when no registry is configured
    (claim-time runs it unconditionally too) — so it is NOT gated on a non-empty registry."""
    if not rec0:
        return True, None
    reg0 = cfg.get("principals") or {}
    skill, perk = rec0.get("skill"), rec0.get("perk")
    if reg0:                                                  # ACCESS-2: the per-actor ACL on the live principal
        sc = principals.resolve_scope(reg0, rec0.get("principal"))
        strict = bool(cfg.get("acl_strict"))
        if sc is not None or strict:
            okv, pv = principals.acl_allows(sc, skill, perk, delegate.perk_sandbox_tier(skill, perk),
                                            rec0.get("destructive", False), bool(rec0.get("credential_ids")),
                                            parameterized=bool(rec0.get("binds")), now=now, strict=strict)
            if not okv:
                return False, "acl:" + pv["id"]
    ps0 = reg0.get(rec0.get("principal")) or {}              # ACCESS-1: skill-intrinsic — registry-independent
    saok, sap = skillacl.access_allows(skillacl.load_access(skill), mode=(cfg.get("mode") or "local"),
                                       is_local_dev=bool(ps0.get("local_dev")), principal=rec0.get("principal"),
                                       principal_tier=ps0.get("tier"), perk=perk,
                                       enforce_default_closed=bool(cfg.get("skillacl_enforce")))
    if not saok:
        return False, "access:" + sap["id"]
    return True, None


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

def _budget_page(roll):
    """A self-contained server-rendered GAUGE page for the firing govd: per-actor allowance/spent/balance with
    a green->amber->red bar, value-free (credit amounts only). Auto-refreshes; pairs with the pricing-stage
    shutoff (the gate) — this is the gauge half of 'a gauge + shutoff at pricing'."""
    import html as _h
    from decimal import Decimal

    def esc(s):
        return _h.escape(str(s))
    fleet = roll.get("fleet", {})
    body = []
    for a in roll.get("by_actor", []):
        try:
            al, sp = Decimal(a["allowance"]), Decimal(a["spent"])
        except Exception:
            al, sp = Decimal(0), Decimal(0)
        pct = int(sp * 100 / al) if al > 0 else 0
        zone = "ok" if pct < 70 else ("warn" if pct < 100 else "no")
        body.append(f'<tr><td><b>{esc(a["actor"])}</b></td>'
                    f'<td><div class="g"><div class="gb"><div class="gf {zone}" style="width:{min(pct, 100)}%">'
                    f'</div></div><span class="gl">{esc(a["spent"])} / {esc(a["allowance"])}</span></div></td>'
                    f'<td class="{zone}">{esc(a["balance"])}</td><td>{esc(a.get("runs", 0))}</td></tr>')
    rows = "".join(body) or '<tr><td colspan="4" class="muted">no actors with a budget configured</td></tr>'
    return ("<!doctype html><html><head><meta charset=utf-8><meta http-equiv=refresh content=5>"
            "<title>govd · budget</title><style>"
            "body{font:13px ui-monospace,Menlo,monospace;background:#0b0e14;color:#c9d1d9;margin:0;padding:18px}"
            "h1{font-size:15px;color:#58a6ff;margin:0 0 8px} table{width:100%;border-collapse:collapse}"
            "td,th{text-align:left;padding:6px 8px;border-bottom:1px solid #21262d}"
            "th{color:#6e7681;font-size:11px;text-transform:uppercase} .muted{color:#6e7681;text-align:center;padding:18px}"
            ".g{display:flex;align-items:center;gap:8px} .gb{flex:1;min-width:120px;height:11px;background:#21262d;border-radius:6px;overflow:hidden}"
            ".gf{height:100%} .gf.ok{background:#2ea043} .gf.warn{background:#d29922} .gf.no{background:#f85149}"
            ".gl{min-width:130px;color:#8b949e;font-size:11px} .ok{color:#3fb950} .warn{color:#d29922} .no{color:#f85149}"
            "</style></head><body>"
            "<h1>govd · budget — credit gauge + pricing shutoff</h1>"
            f'<p class="muted">fleet: <b>{esc(fleet.get("spent", "0"))}</b> spent / {esc(fleet.get("allowance", "0"))} '
            f'allowed · {esc(fleet.get("balance", "0"))} balance · {esc(fleet.get("actors", 0))} actors · '
            "CREDITS · auto-refresh 5s</p>"
            "<table><thead><tr><th>actor</th><th>spent / allowance</th><th>balance</th><th>runs</th></tr></thead>"
            f"<tbody>{rows}</tbody></table></body></html>")


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
            # P2-T12: surface the execution boundary so an operator/agent sees whether steps run client-side
            # (cooperative) or are CONFINED by exod (delegated) — and, when delegated, whether the limb is
            # actually attached (a delegated govd with no exod refuses every step, fail-closed).
            ex_mode = getattr(self.server, "exec_mode", "cooperative")
            exod_attached = bool(getattr(self.server, "exod_socket", None)
                                 and getattr(self.server, "exod_grant_key", None)
                                 and getattr(self.server, "exod_pub", None))
            return self._json(200, {"status": "ok", "service": "cyberware-govd", "mode": cfg["mode"],
                                    "host": host, "port": port, "registry": registry.SKILLCHIP,
                                    "chip_sha": chip_sha(), "chip": chip_provenance(),
                                    "exec_mode": ex_mode, "exod_attached": exod_attached,
                                    "runs": len(store.runs)})
        path = self.path.split("?", 1)[0]
        if path == "/catalog":
            # value-free discovery (names · perks · var-KEYS · skill_sha · verified) — ungated like /health,
            # so an agent can ask "what do you govern?" before it claims. No values, no run data.
            return self._json(200, catalog_snapshot())
        if path == "/price":
            # value-free USAGE QUOTE for a claim, BEFORE it runs: LLM cost (context + output tokens at the
            # model rate) + the tool's pay-route fee, itemized. Priced from the plan shape — no execution, no
            # generation, no values. The `total` is what a Stripe charge bills (it reconciles to the cent).
            qs = urllib.parse.parse_qs(urllib.parse.urlparse(self.path).query)
            raw = qs.get("skill", [""])[0]
            skill = registry.canonicalize(raw)               # bare back-compat: the same shim as /govern
            perk = qs.get("perk", [""])[0]
            if skill not in set(skill_index.all_skills()):
                return self._json(404, {"error": "unknown skill", "skill": raw})
            mode = "freeform" if qs.get("mode", ["structured"])[0] == "freeform" else "structured"
            try:
                from infra.settle import price
                return self._json(200, price.price_plan(skill, perk, model=qs.get("model", [None])[0], mode=mode))
            except Exception as e:                       # never 500 the thread on a pricing edge case
                return self._json(400, {"error": f"price failed: {type(e).__name__}: {e}"})
        if path.startswith("/flow/run/"):
            # THIS run's task blueprint (the perk's gated sequence, gates bound to concrete contract
            # checks) — rendered value-free from the record. Monitor-gated like /monitor/run.
            if not self._monitor_authed(cfg):
                return self._json(403, {"error": "missing/invalid monitor token"})
            rec = store.get(urllib.parse.unquote(path[len("/flow/run/"):]))
            if rec and rec.get("skill") and rec.get("perk"):
                try:
                    return self._svg(task_flow_svg(rec).encode())
                except Exception as e:
                    return self._json(500, {"error": "task flow render failed", "detail": str(e)})
            return self._json(404, {"error": "unknown run_id"})
        if path.startswith("/flow/"):
            # the skill's generic lifecycle diagram (blueprint.svg) — a value-free registry artifact,
            # ungated like /catalog. Path-safe: only an EXACT known skill name is served, so the path can
            # never escape the registry. (The dashboard's Flow tab uses /flow/run/<id>; this is a fallback.)
            skill = registry.canonicalize(urllib.parse.unquote(path[len("/flow/"):]))   # bare back-compat
            if skill in set(skill_index.all_skills()):
                svgp = os.path.join(registry.skill_dir(skill), "blueprint.svg")
                if os.path.isfile(svgp):
                    return self._svg(open(svgp, "rb").read())
            return self._json(404, {"error": "no flow diagram", "skill": skill})
        if path in ("/", "/dashboard"):
            return self._dashboard()
        if path == "/favicon.png":
            return self._favicon()
        if path == "/monitor/state":
            if not self._monitor_authed(cfg):
                return self._json(403, {"error": "missing/invalid monitor token (?token= or X-Govd-Monitor)"})
            qs = urllib.parse.parse_qs(urllib.parse.urlparse(self.path).query)
            try:                                          # P5-T02: page the decisions feed (clamped in feed.paginate)
                dp, dl = int(qs.get("dec_page", ["1"])[0]), int(qs.get("dec_limit", [str(DECISIONS_PER_PAGE)])[0])
            except ValueError:
                dp, dl = 1, DECISIONS_PER_PAGE
            return self._json(200, store.monitor_snapshot(dec_page=dp, dec_limit=dl))
        if path == "/budget/state":
            # per-actor CREDIT accounting (gauge + accountant data) from the durable budget ledger — the
            # firing govd's view of who's spent what against their allowance. Monitor-gated (value-free).
            if not self._monitor_authed(cfg):
                return self._json(403, {"error": "missing/invalid monitor token (?token= or X-Govd-Monitor)"})
            be = getattr(self.server, "store_backend", None)
            actors = list(cfg.get("principals") or {})
            roll = budget.rollup(be, actors) if be is not None else {"by_actor": [], "fleet": {}}
            return self._json(200, {**roll, "enforced": bool(cfg.get("budget_enforce")), "currency": "CREDITS"})
        if path == "/budget":
            # the GAUGE page for the firing govd (the gauge half of 'a gauge + shutoff at pricing'). Monitor-
            # gated; value-free (credit amounts only). Auto-refreshes alongside the live shutoff (the gate).
            if not self._monitor_authed(cfg):
                return self._json(403, {"error": "missing/invalid monitor token (?token=)"})
            be = getattr(self.server, "store_backend", None)
            roll = (budget.rollup(be, list(cfg.get("principals") or {}))
                    if be is not None else {"by_actor": [], "fleet": {}})
            page = _budget_page(roll).encode()
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(page)))
            self.end_headers()
            self.wfile.write(page)
            return
        if path == "/monitor/stream":
            if not self._monitor_authed(cfg):
                return self._json(403, {"error": "missing/invalid monitor token (?token= or X-Govd-Monitor)"})
            return self._monitor_stream(store)
        if path.startswith("/monitor/run/"):
            if not self._monitor_authed(cfg):
                return self._json(403, {"error": "missing/invalid monitor token"})
            detail = store.run_detail(path.split("/monitor/run/", 1)[1])
            if detail:                                   # attach the porters this run runs (public chip code)
                detail["sources"] = porter_sources(detail.get("skill"), detail.get("perk"), detail.get("seq"))
            return self._json(200 if detail else 404, detail or {"error": "unknown run_id"})
        if path.startswith("/trace/"):
            # P5-T05: the run's cross-plane trace (claim→grant→step spans under one trace id) by run_id —
            # value-free, monitor-gated like /monitor/run.
            if not self._monitor_authed(cfg):
                return self._json(403, {"error": "missing/invalid monitor token"})
            # run_detail strips the session token at the data boundary — the value-free guarantee never rests
            # only on tracing.py's allowlist (defence in depth: a future field add can't launder the token).
            tr = tracing.trace_of(store.run_detail(urllib.parse.unquote(path[len("/trace/"):])) or {})
            return self._json(200 if tr else 404, tr or {"error": "unknown run_id or no trace"})
        if path.startswith("/intoto/"):
            # P5-T05: the run's in-toto cyberware/run@v1 provenance attestation by run_id (value-free).
            if not self._monitor_authed(cfg):
                return self._json(403, {"error": "missing/invalid monitor token"})
            rec = store.run_detail(urllib.parse.unquote(path[len("/intoto/"):]))   # token-stripped copy
            return self._json(200 if rec else 404,
                              tracing.intoto_statement(rec) if rec else {"error": "unknown run_id"})
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

    def _monitor_stream(self, store):
        """P5-T02 — Server-Sent Events push: one long-lived connection replaces the dashboard's 1.5s poll.
        The server re-derives the value-free snapshot every GOVD_SSE_INTERVAL seconds and pushes a `data:`
        event ONLY when the snapshot content (sans the volatile `now` stamp) changes; otherwise it writes an
        SSE keep-alive comment so a broken connection is detected promptly. Metadata only — same value-free
        snapshot as /monitor/state. A write to a disconnected client raises, ending the (daemon) thread.

        Bounded against resource accumulation: the interval is clamped finite to [0.1, 60]s (so a misconfigured
        env value can neither crash the thread via sleep(inf) nor freeze disconnect detection); at most
        SSE_MAX_STREAMS run concurrently (503 past the cap); and a short per-write socket timeout reaps a stuck
        sendall (a non-reading/half-closed client) in seconds rather than the 600s connection ceiling."""
        interval = feed.clamp_interval(os.environ.get("GOVD_SSE_INTERVAL"))   # finite, bounded [0.1, 60]
        with _SSE_LOCK:
            if _SSE_ACTIVE[0] >= SSE_MAX_STREAMS:
                return self._json(503, {"error": f"too many monitor streams (max {SSE_MAX_STREAMS})"})
            _SSE_ACTIVE[0] += 1
        try:
            self.connection.settimeout(min(interval * 5, 15))   # reap a stuck write in seconds, not the 600s ceiling
            self.send_response(200)
            self.send_header("Content-Type", "text/event-stream")
            self.send_header("Cache-Control", "no-cache")
            self.send_header("Connection", "keep-alive")
            self.send_header("X-Accel-Buffering", "no")   # tell any reverse proxy not to buffer the stream
            self.end_headers()
            last = None
            self.wfile.write(b"retry: 2000\n\n")          # client auto-reconnect backoff
            self.wfile.flush()
            while True:
                snap = store.monitor_snapshot()
                d = feed.digest({k: v for k, v in snap.items() if k != "now"})
                self.wfile.write(feed.sse_frame(snap).encode() if d != last else b": keepalive\n\n")
                self.wfile.flush()
                last = d
                time.sleep(interval)
        except (BrokenPipeError, ConnectionResetError, OSError):
            return                                        # client gone / stuck write reaped — daemon thread exits
        finally:
            with _SSE_LOCK:
                _SSE_ACTIVE[0] -= 1

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

    def _favicon(self):
        try:
            body = open(os.path.join(HERE, "favicon.png"), "rb").read()
        except OSError:
            return self._json(404, {"error": "no favicon"})
        self.send_response(200)
        self.send_header("Content-Type", "image/png")
        self.send_header("Cache-Control", "max-age=86400")   # static asset
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
        _bp = self.path.split("?", 1)[0]
        if _bp in ("/budget/topup", "/budget/recharge"):
            return self._budget_admin(_bp)
        if self.path != "/govern":
            return self._json(404, {"error": "not found", "path": self.path})
        cfg, store = self.server.cfg, self.server.store
        # P1-T08: principal auth at the syscall boundary (header-only, before reading the body). A configured
        # principals registry makes Authorization: Bearer mandatory; local dev (no registry) runs as 'local'.
        reg = cfg.get("principals") or {}
        # acl_strict (Phase B): the deny-by-default end-state must not be voidable by simply not configuring a
        # registry — an empty/absent registry under strict is a hard refusal, never an allow-all 'local'.
        if cfg.get("acl_strict") and not reg:
            return self._json(503, {"error": "acl_strict requires a configured principals registry"})
        pid = cfg.get("node_name") or "local"            # unauthenticated local-mode runs attribute to the
        if reg:                                          # node's fleet name (GOVD_NODE_NAME), else generic "local"
            pid = principals.authenticate(principals.bearer_of(self.headers.get("Authorization", "")), reg)
            if pid is None:
                return self._json(401, {"error": "missing/invalid Authorization: Bearer token"})
            spec = reg[pid]
            bucket = self.server.rate_buckets.setdefault(pid, {})
            if not principals.rate_ok(bucket, time.time(), float(spec.get("rate", 1.0)),
                                      float(spec.get("burst", 10))):
                return self._json(429, {"error": "rate limit exceeded", "principal": pid})
        try:
            n = int(self.headers.get("Content-Length", 0))
            if n > MAX_BODY:
                return self._json(413, {"error": f"request body too large ({n} > {MAX_BODY})"})
            ledger = json.loads(_read_exact(self.rfile, n) or b"{}") if n else {}
        except Exception as e:
            return self._json(400, {"error": f"bad request body: {e}"})
        if not isinstance(ledger, dict):
            return self._json(400, {"error": "request body must be a JSON object (task-ledger)"})

        scope = principals.resolve_scope(reg, pid) if reg else None
        pspec = (reg or {}).get(pid) or {}               # ACCESS-1 inputs: the principal's dev-override + trust tier
        # BUDGET: meter only AUTHENTICATED actors (a registry present) under the rollout flag — local dev (no
        # registry) stays unmetered. An authenticated actor must carry a NON-NULL `credits`/`budget` allowance,
        # else budget_unmetered → reject (fail-closed). The gate predicate is the SAME `configured_allowance`
        # the seeder uses, so "configured" ⟺ "seeded" exactly — a key present but null counts as unmetered at
        # BOTH (no metered-but-unseeded lockout). Read the CREDIT balance (snapshot) for govern's pre-check; an
        # unreadable balance → None → budget_ok fails closed (budget_unavailable).
        budget_enforce = bool(cfg.get("budget_enforce")) and bool(reg)
        budget_configured = budget_enforce and budget.configured_allowance(pspec) is not None
        budget_balance = None
        if budget_configured:
            try:
                budget_balance = self.server.store_backend.budget_balance(pid)
            except Exception:
                budget_balance = None
        try:
            v = govern(ledger, cfg, scope=scope, principal=pid,
                       local_dev=bool(pspec.get("local_dev")), principal_tier=pspec.get("tier"),
                       strict=bool(cfg.get("acl_strict")), now=time.time(),
                       budget_enforce=budget_enforce, budget_balance=budget_balance,
                       budget_configured=budget_configured)
        except Exception as e:                           # never leak a stack trace; never 500 the thread
            return self._json(400, {"error": f"govern failed: {type(e).__name__}: {e}"})
        # ACL M1: recompute the actor's acl_sha from the LIVE registry fields (never an operator-supplied field)
        # and stamp it on the record, so delegate can bind it into the grant for exod's join.
        acl_sha = (principals.acl_sha(pid, (reg.get(pid) or {}).get("token_sha"), scope)
                   if scope is not None else None)
        # ACCESS-1 fold (rollout flag): RECORD the skill-access policy sha as part of the run's provenance,
        # ready for exod to re-check off-node in Step 7. It is kept SEPARATE from the grant-bound acl_sha on
        # purpose — folding it INTO acl_sha breaks exod's acl_join (exod re-derives acl_sha from the operator-
        # attested ACTOR ACL, which knows nothing of the skill policy) and fail-closes every delegated run.
        skillacl_sha = (skillacl.access_policy_sha(skillacl.load_access(v.get("skill") or ledger.get("skill")))
                        if cfg.get("skillacl_fold") else None)
        run_id = uuid.uuid4().hex[:16]
        # BUDGET debit — the AUTHORITY (govern's check was against a snapshot). On allow, atomically re-check +
        # debit the actor's balance; if a concurrent claim moved it (lost the race) or the store is unreadable,
        # flip to reject — so two same-actor claims can never both pass when only one fits. Idempotent per RUN
        # (run_id), NOT per plan (two runs of one perk share a plan_sha — each must be charged).
        if v["decision"] == "allow" and budget_enforce and budget_configured and v.get("cost"):
            from infra.settle.money import Money
            try:
                deb = self.server.store_backend.budget_debit_atomic(pid, Money(v["cost"], "CREDITS"), "usage:" + run_id)
            except Exception:
                deb = {"ok": False, "balance": None}
            if not deb.get("ok"):
                v["decision"] = "reject"
                v["problems"] = (v.get("problems") or []) + [{"id": "insufficient_credits",
                                 "detail": {"reason": "raced_or_unavailable", "balance": deb.get("balance")}}]
        # a per-run session token — the run's private credential (like a bank session). Issued once, here,
        # only to the caller; required to open the WS or read the ledger for this run.
        token = secrets.token_urlsafe(32) if v["decision"] == "allow" else None
        # the record is value-free: var KEYS (names), the perk metadata, and the blessed plan + its hash.
        # No values, no file contents, no secrets, no command output ever enter the ledger.
        var_keys = sorted(ledger.get("var_keys") or ledger.get("vars") or [])
        plan = v.get("plan")
        # P5-T05: the run carries ONE W3C traceparent from the agent's claim (or govd mints a sampled root);
        # govd derives a child span per plane hop so the claim→grant→step trace is retrievable by run_id.
        traceparent = (ledger.get("traceparent") if tracing.parse_traceparent(ledger.get("traceparent") or "")
                       else tracing.new_traceparent())
        # persist the CANONICAL id govern() decided on (not the raw bare claim): step-time ACL re-check, the
        # signed exod grant, sandbox materialization, and the in-toto subject ALL re-read record["skill"], so a
        # bare here would re-resolve independently (TOCTOU) and never carry the ':' the ns:* wildcard needs.
        record = {"run_id": run_id, "ts": now(), "skill": v.get("skill") or ledger.get("skill"), "perk": ledger.get("perk"),
                  "principal": pid, "cost": v.get("cost"), "token": token, "var_keys": var_keys, "decision": v["decision"],
                  "traceparent": traceparent,
                  "destructive": v.get("destructive", False), "approved": v.get("approved", []),
                  "acl_sha": acl_sha,                       # ACL M1: bound into the delegated grant (None = unscoped)
                  "skillacl_sha": skillacl_sha,             # ACCESS-1 provenance (skillacl_fold flag); exod-side = Step 7
                  "plan_sha": v.get("plan_sha"), "snippet_shas": (plan or {}).get("snippet_shas", {}),
                  "credential_ids": (plan or {}).get("credential_ids", []),   # server-authorized vault IDs (names only)
                  "seq": v.get("seq", []), "wrapper": (plan or {}).get("wrapper", ""), "tlc": v.get("tlc"),
                  "tlc_tla": v.get("tlc_tla"), "tlc_log": v.get("tlc_log"),   # the model-check spec + full output
                  "problems": v.get("problems", []), "events": []}
        if v["decision"] == "allow":                     # only authorized runs are persisted (bounds growth)
            store.create(run_id, record)
        else:                                            # push_back/reject: in-memory only — navigable + inspectable
            store.remember(run_id, record)               # in the monitor (ledger + plan + problems), not on disk
        # every decision (incl. push_back/reject) is logged for the monitor — metadata only, no token
        store.record_decision({"run_id": run_id, "ts": record["ts"], "skill": record["skill"],
                               "perk": record["perk"], "principal": pid, "cost": v.get("cost"), "decision": v["decision"],
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
        resp["traceparent"] = traceparent               # P5-T05: the agent propagates this to exod/the step plane
        if v["decision"] == "allow":
            resp["plan"] = plan                          # value-free: sequence + wrapper + src-closure hashes
            resp["session_token"] = token                # present this on the WS and to GET /ledger
        code = {"allow": 200, "push_back": 409, "reject": 403}[v["decision"]]
        return self._json(code, resp)

    # --- budget admin: credits IN (operator grant) + Stripe recharge (buy credits) ---
    def _budget_admin(self, path):
        """Monitor-token-gated. Both paths post to the SAME per-actor budget_ledger (idempotent, audited):
          /budget/topup    — an operator GRANT (or a confirmed Stripe credit) -> credit the actor LIVE;
          /budget/recharge — mint a Stripe PaymentIntent to BUY credits (inert until the operator wires a
                             key). The card is Stripe's; the credits are posted when the payment confirms (a
                             webhook re-calls /budget/topup with source='stripe', ref=<payment_intent_id>)."""
        cfg = self.server.cfg
        if not self._monitor_authed(cfg):
            return self._json(403, {"error": "missing/invalid monitor token (X-Govd-Monitor or ?token=)"})
        be = getattr(self.server, "store_backend", None)
        if be is None:
            return self._json(503, {"error": "budget ledger not initialized"})
        try:
            n = int(self.headers.get("Content-Length", 0))
            body = json.loads(_read_exact(self.rfile, n) or b"{}") if n else {}
        except Exception as e:
            return self._json(400, {"error": f"bad request body: {e}"})
        actor = body.get("actor")
        if not actor:
            return self._json(400, {"error": "actor required"})
        from infra.settle.money import Money
        if path == "/budget/topup":
            raw = body.get("credits")
            # a JSON float would slip past str()-coercion (str(1.5)=='1.5') — refuse a non-string/int amount so
            # the float-ban holds at the HTTP boundary too. (bool is an int subclass; exclude it.)
            if isinstance(raw, bool) or not isinstance(raw, (str, int)):
                return self._json(400, {"error": "credits must be an exact-decimal amount STRING (no float)"})
            try:
                amt = Money(str(raw), "CREDITS")
            except (TypeError, ValueError):
                return self._json(400, {"error": "credits must be an exact-decimal amount string"})
            if amt.amount <= 0:                                    # top-ups are credits-IN — reject non-positive
                return self._json(400, {"error": "credits must be a positive amount"})
            source = body.get("source") or "grant"
            ref = str(body.get("ref") or f"{source}-{uuid.uuid4().hex[:12]}")
            res = be.budget_post(actor, amt, memo=f"topup:{source}:{ref}", idem=f"topup:{ref}")
            print(f"  /budget/topup {actor} += {amt.amount} CREDITS (source={source} ref={ref}) -> {res['status']}")
            return self._json(200, {"actor": actor, "added": str(amt.amount), "currency": "CREDITS",
                                    "source": source, "ref": ref, "balance": res["balance"], "status": res["status"]})
        # /budget/recharge — mint the Stripe PaymentIntent (buy credits); crediting happens on confirm.
        from infra.settle import rails
        raw_amt = body.get("amount")
        if raw_amt is not None and (isinstance(raw_amt, bool) or not isinstance(raw_amt, (str, int))):
            return self._json(400, {"error": "amount must be an exact-decimal amount string (no float)"})
        amount = str(raw_amt or "")
        cur = body.get("currency") or "USD"
        if not amount:
            return self._json(400, {"error": "amount (the purchase price, e.g. '10.00') required"})
        charge = {"plan_sha": f"recharge:{actor}:{uuid.uuid4().hex[:12]}", "currency": cur, "total": amount,
                  "breakdown": [{"account": f"recharge:{actor}", "amount": amount}]}
        rail = rails.StripeRail(((cfg.get("pricing") or {}).get("rails", {}) or {}).get("stripe") or {})
        res = rail.collect(charge, charge["plan_sha"])
        return self._json(200, {"actor": actor, "amount": amount, "currency": cur, "recharge": res,
                                "note": "on payment success, POST /budget/topup {actor, credits, source:'stripe', "
                                        "ref:<payment_intent_id>} to credit the bought CREDITS"})

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
                    rec0 = store.get(bound)
                    reg0 = self.server.cfg.get("principals") or {}
                    # M0: re-enforce the actor ACL on the LIVE principal at STEP time, so revocation, TTL
                    # expiry, or a tightened scope bind an IN-FLIGHT multi-step run (not just the claim) and
                    # execution authority re-binds to the live principal rather than mere session-token
                    # possession. Runs before both the delegated and cooperative branches (a deny refuses).
                    if ok:                                   # re-bind authority on the live registry + skill policy
                        _rok, _rreason = step_reauthorize(self.server.cfg, rec0, now=time.time())
                        if not _rok:
                            ok, reason = False, _rreason
                    delegated = ((reg0.get((rec0 or {}).get("principal")) or {}).get("exec_mode")
                                 or getattr(self.server, "exec_mode", "cooperative")) == "delegated"
                    if ok and delegated:
                        # P2-T12: govd NEVER runs the step — it hands a signed grant to exod the limb, which
                        # runs CONFINED + signs the authoritative status. Fail-closed if exod isn't attached.
                        if rec0 is None:                     # the run was evicted between authorize + this read
                            ws_send(self.wfile, json.dumps({"type": "refuse", "step": msg.get("step"),
                                    "reason": "run no longer resident (fail-closed)"}))
                            continue
                        sock = getattr(self.server, "exod_socket", None)
                        gk = getattr(self.server, "exod_grant_key", None)
                        epub = getattr(self.server, "exod_pub", None)
                        if not (sock and gk and epub):
                            ws_send(self.wfile, json.dumps({"type": "refuse", "step": msg.get("step"),
                                    "reason": "delegated mode but exod is not configured (fail-closed)"}))
                            continue
                        # atomically claim the step BEFORE dialing exod — a completed (recorded) OR a
                        # concurrently in-flight step is refused, so two WS sessions on the same run cannot
                        # double-execute / double-bill. Released after the result is recorded (a non-terminal
                        # refusal frees the claim so a transient failure can be retried).
                        if not store.claim_step(bound, step):
                            ws_send(self.wfile, json.dumps({"type": "refuse", "step": msg.get("step"),
                                    "reason": f"step {step} already executed or in flight — delegated runs are at-most-once"}))
                            continue
                        try:
                            # PARAMETERIZED delegated run: caller VALUES ride the per-run WS (never the /govern
                            # claim plane, which stays keys-only). Gate them on the actor's `params` ACL LIVE, and
                            # forward ONLY keys that were DECLARED in the plan AND are non-secret — secret-named
                            # keys (and the reserved CWS_SECRET_* vault namespace) never cross the wire.
                            var_values = msg.get("var_values") or {}
                            if var_values:
                                _acl_strict = bool(self.server.cfg.get("acl_strict"))
                                sc_p = principals.resolve_scope(reg0, (rec0 or {}).get("principal"))
                                if sc_p is not None or _acl_strict:
                                    okp, pp = principals.acl_allows(
                                        sc_p, rec0.get("skill"), rec0.get("perk"),
                                        delegate.perk_sandbox_tier(rec0.get("skill"), rec0.get("perk")),
                                        rec0.get("destructive", False), bool(rec0.get("credential_ids")),
                                        parameterized=True, now=time.time(), strict=_acl_strict)
                                    if not okp:
                                        ws_send(self.wfile, json.dumps({"type": "refuse", "step": msg.get("step"),
                                                "reason": "acl:" + pp["id"]}))
                                        continue
                                declared = set(rec0.get("var_keys") or [])
                                var_values = {k: str(v) for k, v in var_values.items()
                                              if k in declared and not k.startswith("CWS_SECRET_")
                                              and not (SECRET_KEY.search(k) and not k.endswith("_FILE"))}
                            d_reply, d_event = delegate.execute_step(
                                rec0, step, psha, exod_socket=sock, grant_key=gk, exod_pub=epub,
                                base=getattr(self.server, "exec_workspace", os.path.join(store.root, "_work")),
                                attestation=msg.get("attestation"),   # ACL M1: agent-relayed operator attestation
                                token_proof=msg.get("token_proof"),   # ACL M2: agent-relayed token-possession proof
                                var_values=var_values)                # caller NON-secret values (declared subset, ACL-gated)
                            if d_event:
                                store.append(bound, {**d_event, "ts": now(),
                                                     "span": tracing.child_span((rec0 or {}).get("traceparent"))})
                            ws_send(self.wfile, json.dumps({"type": "executed", "step": msg.get("step"), **d_reply}))
                        finally:
                            store.release_step(bound, step)
                        continue
                    reply = {"type": "grant" if ok else "refuse", "step": msg.get("step"), "reason": reason}
                    if ok:                                       # record the grant so a result can bind to it
                        span = tracing.child_span((store.get(bound) or {}).get("traceparent"))   # P5-T05 hop
                        store.append(bound, {"type": "granted", "ts": now(), "step": step,
                                             "plan_sha": psha, "span": span})
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
                    rec1 = store.get(bound)
                    reg1 = self.server.cfg.get("principals") or {}
                    if (((reg1.get((rec1 or {}).get("principal")) or {}).get("exec_mode")
                         or getattr(self.server, "exec_mode", "cooperative")) == "delegated"):
                        # in delegated mode exod's signed result is authoritative + already recorded by govd;
                        # an agent self-report is rejected (the cognition holds no limb — it cannot report status).
                        ws_send(self.wfile, json.dumps({"type": "error", "step": step,
                                "reason": "delegated mode — exod is authoritative; agent self-report rejected"}))
                        continue
                    ok, why = result_acceptable(store, bound, step, msg.get("plan_sha"))
                    if not ok:                                   # a result that did not follow a grant is rejected
                        ws_send(self.wfile, json.dumps({"type": "error", "step": step, "reason": why}))
                        continue
                    ev = {"type": "step_result", "ts": now(), "step": step,
                          "status": msg.get("status"), "exit": msg.get("exit"),
                          "span": tracing.child_span((store.get(bound) or {}).get("traceparent"))}   # P5-T05 hop
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


def require_closed_auth(cfg):
    """Fail CLOSED before exposing a network control plane: a REMOTE (0.0.0.0-bound) govd with NO principals
    registry accepts EVERY request as principal 'local' — an unauthenticated /govern. Refuse to start unless
    the operator explicitly opts into open mode. Local (loopback) is exempt; the agent-mode deployment ALWAYS
    sets GOVD_PRINCIPALS, so this never fires in a correct remote setup."""
    if (cfg.get("mode") == "remote" and not cfg.get("principals")
            and os.environ.get("CYBERWARE_ALLOW_OPEN") != "1"):
        raise SystemExit(
            "govd: REMOTE mode with NO principals registry is auth-fail-OPEN (every request becomes principal "
            "'local'). Set GOVD_PRINCIPALS to a registry, or export CYBERWARE_ALLOW_OPEN=1 to override.")


def _load_exec_mode(cfg, httpd):
    """Configure the execution boundary. 'cooperative' (default): the agent runs each step client-side
    (run_governed) — govd governs the CLAIM + records status. 'delegated': govd hands a signed grant to exod
    the limb, which runs the step CONFINED and signs the authoritative status (containment). Delegated
    REQUIRES exod config (socket + grant key + exod pub) — absent, it fail-closed-refuses every step."""
    from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey, Ed25519PublicKey
    httpd.exec_mode = cfg.get("exec_mode", "cooperative")
    httpd.exec_workspace = cfg.get("exec_workspace") or os.path.join(cfg["record_root"], "_work")
    ex = cfg.get("exod") or {}
    httpd.exod_socket = ex.get("socket")
    httpd.exod_grant_key = (Ed25519PrivateKey.from_private_bytes(open(ex["grant_key"], "rb").read())
                            if ex.get("grant_key") else None)
    httpd.exod_pub = (Ed25519PublicKey.from_public_bytes(open(ex["pub"], "rb").read())
                      if ex.get("pub") else None)


def serve(cfg):
    Handler.timeout = cfg.get("socket_timeout", SOCKET_TIMEOUT)
    ensure_monitor_token(cfg)                            # final mode is known here (after --mode)
    require_closed_auth(cfg)                              # refuse a network-exposed plane with auth off
    store = Store(cfg["record_root"], cfg=cfg)
    if cfg["mode"] == "remote":
        host, ports = cfg["remote"]["host"], [cfg["remote"]["port"]]
    else:
        host, ports = cfg["local"]["host"], cfg["local"]["ports"]
    httpd, port = bind_server(host, ports)
    if httpd is None:
        raise SystemExit(f"govd: no free port among {ports}")
    httpd.daemon_threads = True
    httpd.cfg, httpd.store = cfg, store
    httpd.rate_buckets = {}                               # P1-T08: per-principal token-bucket state (in-memory)
    _load_exec_mode(cfg, httpd)                           # P2-T12: cooperative (client-side) | delegated (exod limb)
    httpd.lease = _lease.maybe_enable_ha(cfg, store)      # P5-T04: active-passive single-writer lease (off unless configured)
    # BUDGET: a dedicated backend for the per-actor CREDIT ledger — shares the store db (so the balance is
    # actor-wide under a shared/HA store) but its own connection (never contends with the index writer). Load
    # the negotiable pricing once, and seed each configured principal's opening CREDIT allowance (idempotent).
    httpd.store_backend = None
    try:
        from infra.store import backend as _sb
        from infra.settle import budget as _budget
        from infra.settle import price as _price
        from infra.settle.money import Money as _Money
        httpd.store_backend = _sb.make_backend(store.root, cfg)
        cfg.setdefault("pricing", _price.load_pricing())
        for _pid, _spec in (cfg.get("principals") or {}).items():
            # seed on `credits` OR `budget` — the govern() gate counts EITHER key as configured (budget_configured),
            # so the seeder must honor both or a `budget:`-keyed actor is metered-but-unseeded (locked out at 0).
            _allow = _budget.configured_allowance(_spec)
            if _allow is not None:
                httpd.store_backend.budget_post(_pid, _Money(str(_allow), "CREDITS"),
                                                memo="seed:" + _pid, idem="seed:" + _pid)
    except Exception as e:                                # budget stays inert if the backend/seed can't init
        print(f"  [budget] ledger init skipped: {type(e).__name__}: {e}", file=sys.stderr)
    dash_host = "127.0.0.1" if host in ("0.0.0.0", "::") else host
    print(f"govd · {cfg['mode']} · http://{host}:{port}  ·  ws://{host}:{port}/oversight")
    prov = chip_provenance()
    src = (f"cloud {prov.get('source')} @ {prov.get('ref')} ({str(prov.get('commit'))[:12]})"
           if (prov or {}).get("mode") == "cloud" else "local (baked)")
    print(f"  skillChip={registry.SKILLCHIP}   chip_sha={(chip_sha() or '?')[:16]}   source={src}")
    print(f"  record_root={store.root}")
    # P5-T01: the continuous reconciler — its OWN backend connection (never shares the writers' cx), READ-ONLY,
    # alarms on chain/index divergence. Daemon thread: dies with the process; never touches Store decision state.
    if store.mirror.enabled():
        try:
            from infra.store import backend as _sb
            from infra.store import reconcile as _rec

            def _alarm(cycle, res):
                if not res["ok"]:
                    sys.stderr.write("[govd][reconcile] cycle %d: %d run(s) diverged: %s\n" % (
                        cycle, len(res["alarms"]),
                        json.dumps([{a["run_id"]: [d["class"] for d in a["divergences"]]} for a in res["alarms"]])))
            _recon_be = _sb.make_backend(store.root, cfg)
            threading.Thread(target=_rec.continuous_reconcile, args=(_recon_be, store.root),
                             kwargs={"interval": float(cfg.get("reconcile_interval", 5.0)), "sink": _alarm},
                             daemon=True).start()
        except Exception as e:
            sys.stderr.write(f"[govd] reconciler not started: {e}\n")
    # P6: fleet discovery plane (:8773) — a SECOND listener on a daemon thread (dies with the process).
    # Default-on + graceful-standalone: with no roster it serves just [self]; a failure here NEVER blocks
    # :5773. Reuses cfg['principals'] in-process as the trust root (no new credential); binds the same
    # interface as govd (the host -p <tailnet-ip>:8773:8773 mapping fences it to the tailnet).
    try:
        from infra.govern import fleetd
        fcfg = cfg.get("fleet") or {}
        if fcfg.get("enabled", True):
            fhost = fcfg.get("host") or host
            fport = int(fcfg.get("port", fleetd.FLEET_PORT))
            if (fhost not in ("127.0.0.1", "::1", "localhost") and not cfg.get("principals")
                    and os.environ.get("CYBERWARE_ALLOW_OPEN") != "1"):
                # require_closed_auth equivalent for the FLEET plane: a non-loopback bind with NO principals
                # registry would serve the aggregate roster unauthenticated. LOG-AND-SKIP — never `raise`, a
                # SystemExit would escape the `except Exception` below and take :5773 down with it.
                sys.stderr.write("[govd] fleet plane NOT started: non-loopback bind with no principals registry "
                                 "(the aggregate roster would be unauthenticated). Set GOVD_PRINCIPALS, or export "
                                 "CYBERWARE_ALLOW_OPEN=1 to override.\n")
            else:
                fsrv = fleetd.start(cfg, fhost, fport)
                threading.Thread(target=fsrv.serve_forever, daemon=True).start()
                print(f"  fleet:      http://{fhost}:{fport}/fleet/nodes   (Bearer-gated · roster={fleetd._roster_source(cfg)} · tailnet-only)")
    except Exception as e:
        sys.stderr.write(f"[govd] fleet plane not started: {e}\n")   # a fleet-plane failure must never block :5773
    _mt = cfg["monitor_token"]
    if _mt == "admin":                                   # the well-known default is not a secret — keep the click-through
        print(f"  dashboard:  http://{dash_host}:{port}/?token=admin   (default local token — set GOVD_MONITOR_TOKEN to change)")
    elif os.environ.get("GOVD_ECHO_TOKEN") == "1":       # explicit opt-in for a trusted local terminal
        print(f"  dashboard:  http://{dash_host}:{port}/?token={_mt}")
    else:                                                # a real monitor token is an admin credential — never to stdout (journald/Docker-log capture)
        print(f"  dashboard:  http://{dash_host}:{port}/?token=<GOVD_MONITOR_TOKEN>   (redacted from logs; GOVD_ECHO_TOKEN=1 to print)")
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
