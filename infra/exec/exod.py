#!/usr/bin/env python3
"""infra/exec/exod.py — the execution daemon (P2-T02): a SEPARATE PRINCIPAL that is the only thing which
runs a step and the only thing whose status the ledger trusts.

The executor used to run a compiled step AND write its own "ok"/"error" into the run-ledger — a self-report
the agent could forge by editing the record. exod replaces that self-report. It runs as its own OS principal
(a daemon on a Unix-domain socket, ideally under a distinct uid) holding its own Ed25519 identity. A caller
hands it a step plus a signed capability grant (P2-T01); exod verifies the grant, runs the step inside the
bwrap SandboxProfile (P2-T03), and returns a step-result SIGNED with exod's key. The ledger accepts a status
ONLY when exod's signature verifies — a step-result that did not come over exod's channel (a forged
self-report) is refused and recorded. The crypto + UDS here are platform-agnostic; the sandboxed run itself
needs Linux + bwrap (run_confined refuses elsewhere), so the end-to-end path is exercised in the exec image.

The verification surface lives in exodverify.py (prose-clean, the R3 mutation target); this module runs the
daemon, signs results, records authoritative status, and re-exports the verifier so callers keep one import.
"""
from __future__ import annotations
import hashlib
import json
import os
import socket
import time

from infra.cwp import sign
from infra.exec.grantverify import _issuer, grant_body, verify_grant
from infra.exec.sandbox import core_profile, run_confined
from infra.exec.exodverify import (  # noqa: F401  (single source of truth for the verify surface)
    STEP_RESULT_TYPE, NonceCache, _principal, result_body, verify_step_result,
)


def _now() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def _sha(text: str) -> str:
    return hashlib.sha256(text.encode()).hexdigest()


class Exod:
    """One exod principal. `signing_key` is its identity; `grant_issuer_pub` is the key it trusts to have
    issued capability grants (govd's grant key). `runner` runs a confined step (injectable so the channel
    logic is testable off-Linux); the default is the real bwrap sandbox."""

    def __init__(self, signing_key, *, grant_issuer_pub, runner=run_confined, profile_factory=core_profile):
        if _principal(grant_issuer_pub) == _principal(signing_key.public_key()):
            raise ValueError("exod identity key must differ from the grant-issuer key (no self-issued grants)")
        self._sk = signing_key
        self._issuer_pub = grant_issuer_pub
        self._runner = runner
        self._profile = profile_factory
        self._grant_nonces = NonceCache()   # fast per-instance guard; the durable one is the ledger (below)

    @property
    def public_key(self):
        return self._sk.public_key()

    def _sign_result(self, *, run_id, plan_sha, step, exit_code, status, output_sha, nonce):
        body = {"run_id": run_id, "plan_sha": plan_sha, "step": step, "exit": exit_code,
                "status": status, "output_sha": output_sha, "nonce": nonce, "ts": _now()}
        return sign.sign(body, self._sk, payload_type=STEP_RESULT_TYPE)

    def run_step(self, req: dict, *, now: int, required_capability: str = "run"):
        """Verify the grant AGAINST THE REQUEST, run the step confined, and return exod's SIGNED step-result.
        The grant authorizes a specific (run_id, plan_sha), a set of capabilities, and (optionally) the
        approved snippet digests — exod refuses the moment the request strays outside what was actually
        granted, so one grant can never be laundered into authority over a different run or command. The
        signed result is bound to the GRANT's single-use nonce (not the caller's), so a replayed grant is
        detectable at the ledger even across a daemon restart. Every refusal is itself on exod's channel."""
        run_id, plan_sha, step = req.get("run_id"), req.get("plan_sha"), req.get("step")
        try:
            gbody = grant_body(req["grant"])
        except Exception:
            gbody = {}
        gnonce = gbody.get("nonce") if isinstance(gbody, dict) else None
        rnonce = gnonce or req.get("nonce") or "ungranted"   # the result's identity IS the grant's nonce

        def refuse(tag):
            return self._sign_result(run_id=run_id, plan_sha=plan_sha, step=step, exit_code=None,
                                     status="refused", output_sha=_sha(tag), nonce=rnonce)

        # 1. authentic + in-window + minted FOR THIS run/plan
        ok, reason = verify_grant(self._issuer_pub, req["grant"], now=now,
                                  expect_run_id=run_id, expect_plan_sha=plan_sha)
        if not ok:
            return refuse("grant:" + reason)
        # 2. the grant must actually carry the capability being exercised
        if required_capability not in (gbody.get("capabilities") or []):
            return refuse("capability:" + required_capability)
        # 3. if the grant pins approved snippet digests, the step's snippet must be one of them
        granted = set((gbody.get("snippet_shas") or {}).values())
        if granted and req.get("snippet_sha") not in granted:
            return refuse("snippet:not_granted")
        # 4. spend the grant ONLY now that the request is fully authorized — a refused request never burns a
        #    still-valid grant. This is the fast in-memory guard; the durable one is the ledger (result nonce).
        if gnonce is None or not self._grant_nonces.spend(_issuer(self._issuer_pub), gnonce):
            return refuse("grant:replay")
        # 5. run confined + sign the authoritative outcome, bound to the grant nonce
        p = self._runner(self._profile(req["workspace"]), req["argv"])
        status = "ok" if p.returncode == 0 else "error"
        return self._sign_result(run_id=run_id, plan_sha=plan_sha, step=step, exit_code=p.returncode,
                                 status=status, output_sha=_sha(p.stdout or ""), nonce=rnonce)

    # ── the Unix-domain-socket channel — exod as a separate listening principal ──────────────────────
    def serve(self, socket_path: str, *, now_fn=lambda: int(time.time()), max_requests=None,
              recv_timeout=30.0):
        """Listen on `socket_path`; answer each newline-delimited JSON `run` request with a signed result.
        Blocks; intended to run as its own process/principal. `max_requests` bounds the loop (a finite count
        lets a supervisor or a test reap the listener cleanly); None serves forever. Each connection has a
        recv deadline (`recv_timeout`), so a client that opens a socket and withholds its newline cannot
        wedge the single serving thread (a slowloris) — it times out and the loop continues. A malformed or
        slow request is answered, never fatal."""
        if os.path.exists(socket_path):
            os.unlink(socket_path)
        srv = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        srv.bind(socket_path)
        os.chmod(socket_path, 0o660)
        srv.listen(16)
        served = 0
        try:
            while max_requests is None or served < max_requests:
                conn, _ = srv.accept()
                conn.settimeout(recv_timeout)
                with conn:
                    try:
                        env = self.run_step(json.loads(_recv_line(conn) or "{}"), now=now_fn())
                        conn.sendall((json.dumps(env) + "\n").encode())
                    except Exception as e:                       # a bad / slow request is answered, not fatal
                        try:
                            conn.sendall((json.dumps({"error": str(e)}) + "\n").encode())
                        except OSError:
                            pass
                served += 1
        finally:
            srv.close()
            if os.path.exists(socket_path):
                os.unlink(socket_path)


def request_step(socket_path: str, req: dict, *, retries: int = 150) -> dict:
    """Client side: send exod a `run` request over its socket and return the signed step-result envelope.
    Retries the connect briefly — the socket file appears at bind() but only accepts after listen()."""
    c = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
    for attempt in range(retries):
        try:
            c.connect(socket_path)
            break
        except (ConnectionRefusedError, FileNotFoundError):
            if attempt == retries - 1:
                raise
            time.sleep(0.02)
    try:
        c.sendall((json.dumps(req) + "\n").encode())
        return json.loads(_recv_line(c))
    finally:
        c.close()


def _recv_line(conn) -> str:
    buf = b""
    while not buf.endswith(b"\n"):
        chunk = conn.recv(4096)
        if not chunk:
            break
        buf += chunk
    return buf.decode().strip()


def record_step_result(ledger_path: str, exod_public_key, envelope, *, expect_run_id=None,
                       expect_plan_sha=None, nonce_cache=None):
    """The authoritative recorder — the replacement for the executor's self-report. A step-result is written
    to the run-ledger ONLY if exod's signature verifies AND it is bound to this ledger's run; otherwise a
    `forged_status_refused` event is recorded (the forged status is refused AND left as evidence).

    Replay and run-binding are INTRINSIC here, not opt-in: the ledger file is the durable replay guard (a
    result nonce — which is the grant's single-use nonce — already present is a replay, even across a daemon
    restart or a second replica), and a fresh ledger is stamped with its run so every later record binds to
    it. Passing an in-memory `nonce_cache` is an extra fast guard. Returns (accepted, record)."""
    ledger = json.load(open(ledger_path)) if os.path.isfile(ledger_path) else {"runs": []}
    run_id = expect_run_id if expect_run_id is not None else ledger.get("run_id")
    plan_sha = expect_plan_sha if expect_plan_sha is not None else ledger.get("plan_sha")
    seen = {r.get("result_nonce") for r in ledger["runs"] if r.get("result_nonce")}
    ok, reason = verify_step_result(exod_public_key, envelope, expect_run_id=run_id,
                                    expect_plan_sha=plan_sha, nonce_cache=nonce_cache)
    body = result_body(envelope) if ok else {}
    if ok and body.get("nonce") in seen:
        ok, reason = False, "replay"
    if not ok:
        rec = {"ts": _now(), "event": "forged_status_refused", "reason": reason,
               "presented_keyids": [s.get("keyid") for s in envelope.get("signatures", [])]}
        ledger["runs"].append(rec)
        json.dump(ledger, open(ledger_path, "w"), indent=2)
        return False, rec
    ledger.setdefault("run_id", body.get("run_id"))             # a fresh ledger adopts the run it records
    ledger.setdefault("plan_sha", body.get("plan_sha"))
    rec = {"ts": _now(), "step": body.get("step"), "status": body.get("status"), "exit": body.get("exit"),
           "authority": "exod", "exod_keyid": _principal(exod_public_key),
           "stdout_sha": body.get("output_sha"), "result_nonce": body.get("nonce")}
    ledger["runs"].append(rec)
    json.dump(ledger, open(ledger_path, "w"), indent=2)
    return True, rec
