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
import argparse, base64, json, os, socket, subprocess, sys, urllib.error, urllib.request

from infra.govern import compiler
from infra.govern import runlog


def _post_json(url, obj):
    data = json.dumps(obj).encode()
    req = urllib.request.Request(url, data=data, headers={"Content-Type": "application/json"}, method="POST")
    try:
        with urllib.request.urlopen(req) as r:
            return r.getcode(), json.loads(r.read())
    except urllib.error.HTTPError as e:               # 409 push_back / 403 reject still carry a JSON verdict
        return e.code, json.loads(e.read())


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


def _assemble(plan, ledger):
    """Write the value-free plan to disk LOCALLY (wrapper verbatim + snippets) and build the env the
    agent injects at run time — its OWN vars (values + *_FILE secret pointers), which govd never saw.
    run.sh is the blessed wrapper byte-for-byte (its hash matches); no value is ever written into it."""
    run = runlog.run_dir(ledger)
    snipdir = os.path.join(run, "snip")
    os.makedirs(snipdir, exist_ok=True)
    for tool, text in plan["snippets"].items():
        sp = os.path.join(snipdir, f"{tool}.sh")
        open(sp, "w").write(text)
    sh = os.path.join(run, "run.sh")
    open(sh, "w").write(plan["wrapper"])
    os.chmod(sh, 0o755)
    env = dict(os.environ)
    env.update({k: str(v) for k, v in (ledger.get("vars") or {}).items()})   # vars via ENV, not the script
    env["RECORD_STORE"], env["SNIP"] = run, snipdir
    return run, sh, env


def run_governed(base_url, ledger, approve=()):
    """Fetch the value-free plan, assemble it locally, and run it step by step while govd monitors the
    plan hash and records status. No value, secret, or output ever crosses to govd."""
    verdict = fetch(base_url, ledger, approve)
    if verdict.get("decision") != "allow":
        return verdict                                  # push_back (e.g. destructive: approve) / reject

    plan = verdict["plan"]
    psha = compiler.plan_sha(plan)                      # the same hash govd pinned — computed locally
    run, sh, env = _assemble(plan, ledger)

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
    ap = argparse.ArgumentParser(description="drive govd: fetch a governed script and run it under live oversight")
    ap.add_argument("--url", default="http://127.0.0.1:5773")
    ap.add_argument("--ledger", required=True)
    ap.add_argument("--approve", action="append", default=[])
    ap.add_argument("--fetch-only", action="store_true", help="just get the verdict/script, do not execute")
    a = ap.parse_args()
    ledger = json.load(open(a.ledger))
    out = fetch(a.url, ledger, a.approve) if a.fetch_only else run_governed(a.url, ledger, a.approve)
    print(json.dumps(out, indent=2))
    sys.exit(0 if out.get("decision") in ("allow", None) else 2)


if __name__ == "__main__":
    main()
