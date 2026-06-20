#!/usr/bin/env python3
"""govd_client.py — the agent side of the governance server.

Two calls, the whole governed loop:
  * `fetch(base_url, ledger)` — POST the task-ledger, get back the verdict (+ the compiled script on
    `allow`). A `push_back`/`reject` returns the oversight detail and NO script.
  * `run_governed(base_url, ledger)` — fetch, then run the server-issued script step by step while a
    WebSocket to govd authorizes and records each step live. The provenance lands in the SERVER's
    ledger; query it with GET /ledger/<run_id>.

Stdlib only (urllib + a tiny RFC 6455 client), so an agent can drive govd with no dependencies.

  python3 infra/govd_client.py --url http://127.0.0.1:5773 --ledger task-ledger.json [--approve <id>]
"""
from __future__ import annotations
import argparse, base64, collections, hashlib, json, os, socket, subprocess, sys, urllib.error, urllib.parse, urllib.request

from infra import registry as _reg   # the agent's `registry` arg = its skillChip; default = the bundled chip
from infra.govern import compiler
from infra.govern import runlog
from infra.tool import skill_index   # the value-free catalog builder — shared with govd, so the two can't drift


def _post_json(url, obj):
    data = json.dumps(obj).encode()
    req = urllib.request.Request(url, data=data, headers={"Content-Type": "application/json"}, method="POST")
    try:
        with urllib.request.urlopen(req) as r:
            return r.getcode(), json.loads(r.read())
    except urllib.error.HTTPError as e:               # 409 push_back / 403 reject still carry a JSON verdict
        return e.code, json.loads(e.read())


def _get_json(url):
    with urllib.request.urlopen(url) as r:
        return json.loads(r.read())


def discover(base_url, registry=None):
    """Step 2 — discovery. Read what govd governs (GET /catalog), then compare it to the agent's OWN
    registry by skill_sha. Every skill is tagged:
      * 'verified'   — govd governs it AND the agent's copy matches the blessed hash (run it governed);
      * 'drift'      — the agent's copy differs from govd's blessed one (reconcile before claiming);
      * 'unverified' — the agent has it but govd's image does NOT: a NEW skill, not yet governed. Add it to
                       the image (rebuild) before relying on it — claims for it reject as unknown_skill_perk;
      * 'server_drift' — govd's OWN copy fails its index; don't trust its blessing until the image is fixed.
    Only names + hashes cross the wire — never a value or a file body."""
    registry = registry or DEFAULT_REGISTRY
    gov = {s["skill"]: s for s in _get_json(base_url.rstrip("/") + "/catalog").get("skills", [])}
    local = skill_index.catalog(os.path.join(registry))
    out = []
    for s in local["skills"]:
        name, lsha, g = s["skill"], s.get("skill_sha"), gov.get(s["skill"])
        if not g:
            status = "unverified"                       # new — govd's image has never seen this skill
        elif not g.get("verified"):
            status = "server_drift"                     # govd's own copy fails its index — blessing untrustworthy
        elif g.get("skill_sha") == lsha and s.get("verified"):
            status = "verified"                         # governed AND my copy matches the blessed hash
        else:
            status = "drift"                            # my copy differs from the governed one (or my index drifted)
        out.append({"skill": name, "status": status, "skill_sha": lsha,
                    "governed_sha": (g or {}).get("skill_sha"), "perks": s["perks"]})
    summary = collections.Counter(r["status"] for r in out)
    return {"governed_by": base_url.rstrip("/"), "registry": registry, "skills": out,
            "missing_local": sorted(set(gov) - {s["skill"] for s in local["skills"]}), "summary": dict(summary)}


def estimate(base_url, ledger):
    """Ask govd what this claim COSTS before running it — an itemized, value-free usage quote (LLM context +
    output tokens at the model rate, plus the tool's pay-route fee). Only skill/perk/model cross the wire; the
    `total` is what a Stripe charge would bill. No execution, no values."""
    skill = urllib.parse.quote(str(ledger.get("skill") or ""))
    perk = urllib.parse.quote(str(ledger.get("perk") or ""))
    q = f"/price?skill={skill}&perk={perk}"
    if ledger.get("model"):
        q += "&model=" + urllib.parse.quote(str(ledger["model"]))
    if ledger.get("mode") == "freeform":
        q += "&mode=freeform"
    return _get_json(base_url.rstrip("/") + q)


def fetch(base_url, ledger, approve=()):
    """Send govd the CLAIM only — skill, perk, var KEYS. Values never leave the agent."""
    body = {"skill": ledger.get("skill"), "perk": ledger.get("perk"),
            "var_keys": sorted((ledger.get("vars") or {}).keys())}
    if approve:
        body["approve"] = list(approve)
    _, verdict = _post_json(base_url.rstrip("/") + "/govern", body)
    return verdict


# ---- tiny RFC 6455 client ----

def _sock_read(sock, n):
    buf = b""
    while len(buf) < n:
        chunk = sock.recv(n - len(buf))
        if not chunk:
            return None
        buf += chunk
    return buf


def _ws_connect(host, port, path="/oversight"):
    s = socket.create_connection((host, port))
    key = base64.b64encode(os.urandom(16)).decode()
    s.sendall((f"GET {path} HTTP/1.1\r\nHost: {host}:{port}\r\nUpgrade: websocket\r\n"
               f"Connection: Upgrade\r\nSec-WebSocket-Key: {key}\r\nSec-WebSocket-Version: 13\r\n\r\n").encode())
    head = b""
    while b"\r\n\r\n" not in head:
        d = s.recv(1024)
        if not d:
            raise IOError("ws: connection closed during handshake")
        head += d
    if b" 101 " not in head.split(b"\r\n", 1)[0]:
        raise IOError("ws: server did not upgrade: " + head.split(b"\r\n", 1)[0].decode(errors="replace"))
    return s


def _ws_send(sock, text, opcode=0x1):
    payload = text.encode() if isinstance(text, str) else text
    ln = len(payload)
    hdr = bytearray([0x80 | opcode])
    if ln < 126:
        hdr.append(0x80 | ln)
    elif ln < 65536:
        hdr.append(0x80 | 126); hdr += ln.to_bytes(2, "big")
    else:
        hdr.append(0x80 | 127); hdr += ln.to_bytes(8, "big")
    mask = os.urandom(4)
    hdr += mask
    sock.sendall(bytes(hdr) + bytes(b ^ mask[i % 4] for i, b in enumerate(payload)))


def _ws_recv(sock):
    h = _sock_read(sock, 2)
    if not h:
        return None
    opcode, ln = h[0] & 0x0F, h[1] & 0x7F
    if ln == 126:
        ln = int.from_bytes(_sock_read(sock, 2), "big")
    elif ln == 127:
        ln = int.from_bytes(_sock_read(sock, 8), "big")
    data = _sock_read(sock, ln) if ln else b""
    if opcode == 0x8:
        return None
    return (data or b"").decode(errors="replace")


DEFAULT_REGISTRY = _reg.SKILLCHIP    # the agent runs skills from its own skillChip (override with --registry)


def _verify_registry(registry, plan):
    """The agent's OWN perk src files must match the blessed hashes — no file bodies cross the wire.
    Returns (src_dir, problem|None)."""
    src = os.path.join(_reg.skill_dir(plan["skill"], registry), "perks", plan["perk"], "src")
    for fname, want in (plan.get("snippet_shas") or {}).items():
        fp = os.path.join(src, fname)
        if not os.path.isfile(fp):
            return src, f"missing {fname}"
        if hashlib.sha256(open(fp, "rb").read()).hexdigest() != want:
            return src, f"{fname} does not match the blessed hash"
    return src, None


def _prepare(plan, ledger, registry):
    """Write the blessed wrapper to the run dir and point SNIP at the agent's OWN registry src (porters +
    cores). Vars (values + *_FILE secret pointers) go via the ENV, never into the script."""
    run = runlog.run_dir(ledger)
    os.makedirs(run, exist_ok=True)
    sh = os.path.join(run, "run.sh")
    open(sh, "w").write(plan["wrapper"])
    os.chmod(sh, 0o755)
    env = dict(os.environ)
    env.update({k: str(v) for k, v in (ledger.get("vars") or {}).items()})
    env["RECORD_STORE"] = run
    env["SNIP"] = os.path.join(_reg.skill_dir(plan["skill"], registry), "perks", plan["perk"], "src")
    return run, sh, env


def run_governed(base_url, ledger, approve=(), registry=None):
    """Fetch the value-free plan, verify the agent's OWN registry matches the blessed hashes, then run the
    porters+cores FROM that registry while govd monitors the plan hash and records status. No value,
    secret, output, OR code crosses to govd."""
    verdict = fetch(base_url, ledger, approve)
    if verdict.get("decision") != "allow":
        return verdict                                  # push_back (e.g. destructive: approve) / reject

    plan = verdict["plan"]
    psha = compiler.plan_sha(plan)                      # the same hash govd pinned — computed locally
    registry = registry or DEFAULT_REGISTRY
    _, problem = _verify_registry(registry, plan)       # authenticity: my files == govd's blessed hashes
    if problem:
        return {"run_id": verdict["run_id"], "decision": "allow",
                "error": f"registry mismatch ({registry}): {problem}"}
    # Defense-in-depth beyond the per-snippet hashes: the agent's WHOLE skill closure must match its committed
    # authenticity index — skill_index.verify flags changed/missing/UNTRACKED files — so a sha-matching porter
    # can't smuggle an untracked sibling that a blessed porter then `source`s. Same authority govd trusts.
    ok, drift = skill_index.verify(plan["skill"], registry)
    if not ok:
        return {"run_id": verdict["run_id"], "decision": "allow",
                "error": f"registry authenticity failed ({registry}): {drift[:5]}"}
    run, sh, env = _prepare(plan, ledger, registry)

    ws_host, ws_port = verdict["ws"].split("://", 1)[1].split("/", 1)[0].rsplit(":", 1)
    sock = _ws_connect(ws_host, int(ws_port))
    _ws_send(sock, json.dumps({"type": "hello", "run_id": verdict["run_id"], "token": verdict.get("session_token")}))
    hello = _ws_recv(sock)
    if hello is None or not json.loads(hello).get("authorized"):
        sock.close()
        return {"run_id": verdict["run_id"], "decision": "allow", "error": "oversight session not authorized"}

    listing = subprocess.run(["bash", sh, "--list"], capture_output=True, text=True, env=env).stdout
    steps = [ln.split("\t")[0].strip() for ln in listing.strip().splitlines() if ln.strip()]
    results = []
    for st in steps:
        _ws_send(sock, json.dumps({"type": "step_request", "step": st, "plan_sha": psha}))
        raw = _ws_recv(sock)
        if raw is None:                                  # server closed the WS
            results.append({"step": st, "refused": "server closed the oversight channel"}); break
        grant = json.loads(raw)
        if grant.get("type") != "grant":
            results.append({"step": st, "refused": grant.get("reason")}); break
        p = subprocess.run(["bash", sh, "--step", st], capture_output=True, text=True, env=env)
        # report STATUS only — never the command output
        _ws_send(sock, json.dumps({"type": "step_result", "step": st, "plan_sha": psha,
                                   "status": "ok" if p.returncode == 0 else "error", "exit": p.returncode}))
        _ws_recv(sock)
        results.append({"step": st, "exit": p.returncode})
        if p.returncode != 0:
            break
    _ws_send(sock, b"", 0x8)
    sock.close()
    tok = verdict.get("session_token") or ""
    return {"run_id": verdict["run_id"], "decision": "allow", "script": sh, "results": results,
            "plan_sha": psha,
            "ledger": base_url.rstrip("/") + "/ledger/" + verdict["run_id"] + "?token=" + tok}


def main():
    ap = argparse.ArgumentParser(description="drive govd: discover the catalog, then fetch + run a governed script")
    ap.add_argument("--url", default="http://127.0.0.1:5773")
    ap.add_argument("--ledger", help="the task-ledger (required unless --discover)")
    ap.add_argument("--approve", action="append", default=[])
    ap.add_argument("--registry", default=None,
                    help="where the skill code lives (default: this cyberware install); verified vs the blessed hashes")
    ap.add_argument("--discover", action="store_true",
                    help="step 2: list what govd governs + tag each local skill verified/drift/unverified (no claim)")
    ap.add_argument("--fetch-only", action="store_true", help="just get the verdict/plan, do not execute")
    a = ap.parse_args()
    if a.discover:
        out = discover(a.url, registry=a.registry)
        print(json.dumps(out, indent=2))
        sys.exit(0)
    if not a.ledger:
        ap.error("--ledger is required (unless --discover)")
    ledger = json.load(open(a.ledger))
    out = (fetch(a.url, ledger, a.approve) if a.fetch_only
           else run_governed(a.url, ledger, a.approve, registry=a.registry))
    print(json.dumps(out, indent=2))
    # a blocked run (registry mismatch / authenticity drift / unauthorized oversight) returns decision="allow"
    # WITH an `error` and no results — it must NOT report success to a caller keying on the exit code.
    blocked = bool(out.get("error"))
    sys.exit(0 if out.get("decision") in ("allow", None) and not blocked else 2)


if __name__ == "__main__":
    main()
