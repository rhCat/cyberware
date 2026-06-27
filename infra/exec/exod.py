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
import dataclasses
import hashlib
import json
import os
import socket
import sys
import time

from infra.cwp import sign
from infra.exec import vault as _vaultmod
from infra.exec.closureverify import closure_decision
from infra.exec.grantverify import _issuer, grant_body, verify_grant
from infra.exec.sandbox import (
    backend_for_tier, core_profile, is_available, run_confined, runsc_available, strongest,
)
from infra.exec.exodverify import (  # noqa: F401  (single source of truth for the verify surface)
    STEP_RESULT_TYPE, NonceCache, _principal, result_body, verify_step_result,
)
from infra.exec.aclverify import attestation_body, attested_acl, verify_acl_attestation  # ACL M1
from infra.govern import principals          # the SAME pure acl_allows govern() uses — exod re-runs it off-node


def _now() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def _sha(text: str) -> str:
    return hashlib.sha256(text.encode()).hexdigest()


class Exod:
    """One exod principal. `signing_key` is its identity; `grant_issuer_pub` is the key it trusts to have
    issued capability grants (govd's grant key). `runner` runs a confined step (injectable so the channel
    logic is testable off-Linux); the default is the real bwrap sandbox."""

    def __init__(self, signing_key, *, grant_issuer_pub, runner=run_confined, profile_factory=core_profile,
                 vault=None, backend_floor="bwrap", acl_issuer_pub=None, acl_strict=False):
        if _principal(grant_issuer_pub) == _principal(signing_key.public_key()):
            raise ValueError("exod identity key must differ from the grant-issuer key (no self-issued grants)")
        # ACL M1 — three-way dual-control: when an operator ACL-issuer key is pinned it must differ from BOTH
        # the grant-issuer and exod's own identity, so no single key can authorize a run AND attest its actor's
        # ceiling. Asserted whenever a pub is set (both rollout phases).
        if acl_issuer_pub is not None:
            if _principal(acl_issuer_pub) == _principal(grant_issuer_pub):
                raise ValueError("acl-issuer key must differ from the grant-issuer key (three-way dual-control)")
            if _principal(acl_issuer_pub) == _principal(signing_key.public_key()):
                raise ValueError("acl-issuer key must differ from exod's identity key (three-way dual-control)")
        self._sk = signing_key
        self._issuer_pub = grant_issuer_pub
        self._acl_issuer_pub = acl_issuer_pub  # ACL M1: the operator ACL-issuer pub exod re-enforces against
        self._acl_strict = bool(acl_strict)    # ACL M1: refuse (vs audit) on an ACL failure / an unscoped grant
        self._runner = runner
        self._profile = profile_factory
        self._vault = vault                 # the limb resolves grant-authorized secrets server-side (P2-T12)
        self._backend_floor = backend_floor # P3-T11: the operator's --backend; a grant tier may only RATCHET it up
        self._grant_nonces = NonceCache()   # fast per-instance guard; the durable one is the ledger (below)

    @property
    def public_key(self):
        return self._sk.public_key()

    def _sign_result(self, *, run_id, plan_sha, step, exit_code, status, output_sha, nonce, meter=None):
        body = {"run_id": run_id, "plan_sha": plan_sha, "step": step, "exit": exit_code,
                "status": status, "output_sha": output_sha, "nonce": nonce, "ts": _now()}
        if meter is not None:
            body["meter"] = meter        # the attested meter (P2-T07): measured BY exod, inside the signature
        return sign.sign(body, self._sk, payload_type=STEP_RESULT_TYPE)

    def run_step(self, req: dict, *, now: int, required_capability: str = "run"):
        """Verify the grant AGAINST THE REQUEST, run the step confined, and return exod's SIGNED step-result.
        The grant authorizes a specific (run_id, plan_sha), a set of capabilities, and (optionally) the
        approved snippet digests — exod refuses the moment the request strays outside what was actually
        granted, so one grant can never be laundered into authority over a different run or command. For a
        `run`, exod itself RE-DERIVES the digest of every file in the materialized SNIP closure and requires
        it to match the grant's pin (it trusts no digest the caller computed), so a post-grant porter/core
        swap is refused at time of use; the entry wrapper (run.sh) rests on govd's plan-hash, not this gate.
        The signed result is bound to the GRANT's single-use nonce (not the
        caller's), so a replayed grant is detectable at the ledger even across a daemon restart. Every refusal
        is itself on exod's channel."""
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
        # 1b. ACL M1 — re-enforce the actor's ceiling OFF-NODE. When the grant carries an acl_sha (an ACL'd
        #     actor) and the operator pinned an acl-issuer pub, exod REQUIRES a valid operator attestation that
        #     JOINS the grant (acl_sha match) and independently re-runs acl_allows on the grant's claim, so a
        #     compromised govd cannot widen the token. Under acl_strict a failure REFUSES; otherwise it AUDITS
        #     (proceeds — the M0 in-process gate stays the live enforcer while attestations roll out).
        acl_deny = self._acl_check(req, gbody, now=now)
        if acl_deny is not None:
            if self._acl_strict:
                return refuse("acl:" + acl_deny)
            sys.stderr.write(f"[exod] acl audit — would refuse under strict: {acl_deny}\n")
        # 2. the grant must actually carry the capability being exercised
        if required_capability not in (gbody.get("capabilities") or []):
            return refuse("capability:" + required_capability)
        # 3. INDEPENDENTLY re-derive the digest of the materialized closure the confined step will source and
        #    require every member to match what govd signed into the grant. exod trusts NO digest the caller
        #    computed, so a post-grant porter/core swap (the snippet TOCTOU) or a smuggled sibling is refused
        #    at time of use; a run grant that pins a closure with no staged code is fail-closed.
        if required_capability == "run":
            snip_dir = (req.get("env") or {}).get("SNIP") or os.path.join(req.get("workspace") or "", "snip")
            refuse_closure, why = closure_decision(gbody.get("snippet_shas") or {}, snip_dir)
            if refuse_closure:
                return refuse(why)
        # 4. spend the grant ONLY now that the request is fully authorized — a refused request never burns a
        #    still-valid grant. This is the fast in-memory guard; the durable one is the ledger (result nonce).
        if gnonce is None or not self._grant_nonces.spend(_issuer(self._issuer_pub), gnonce):
            return refuse("grant:replay")
        # 5. resolve the GRANT-authorized credentials server-side (the limb holds the vault — never the agent,
        #    never govd's HTTP plane) and inject them into the CONFINED step's env: they land via bwrap
        #    --setenv AFTER --clearenv, so the secret reaches the porter yet never the host/agent env. The set
        #    is exactly what govd signed into the grant (credentials=), so it is authorized + run-bound.
        prof = self._profile(req["workspace"])
        env = {**prof.env, **(req.get("env") or {})}   # govd-supplied NON-secret step env (SNIP, RECORD_STORE)
        creds = gbody.get("credentials") or []
        if creds:
            # P2-T04 no-secrets floor, enforced where secrets RESOLVE: the COMMUNITY tier (the default) may
            # never resolve a credential — only an explicit trusted-tier grant may. A community grant carrying
            # credentials is refused HERE, before any secret is touched — the floor is a runtime invariant of
            # the limb, not merely a manifest-build check.
            if gbody.get("tier", "community") != "trusted":
                return refuse("tier:community_no_secrets")
            if self._vault is None:
                return refuse("vault:unavailable")
            try:
                env = _vaultmod.inject_step_env(env, self._vault, creds)   # + the grant-authorized secrets
            except Exception:
                return refuse("vault:resolve_failed")
        prof = dataclasses.replace(prof, env=env)
        # 6. P3-T11: the grant's sandbox TIER selects the confinement backend, as a MONOTONE floor over the
        #    operator's --backend. A community-tier grant (untrusted marketplace code) DEMANDS the gVisor (runsc)
        #    box; the trusted family (core/verified) runs in bwrap; an undeclared grant takes the operator floor.
        #    The tier can only STRENGTHEN the floor, never weaken it. The runner fails closed when the selected
        #    backend cannot enforce on this host (the RuntimeError is caught below → a signed refusal), so an
        #    untrusted perk is never silently downgraded to a weaker sandbox.
        backend = strongest(self._backend_floor, backend_for_tier(gbody.get("sandbox_tier")))
        # 7. run confined + sign the authoritative outcome, bound to the grant nonce, with an ATTESTED meter
        #    (P2-T07): exod itself measures the step's wall time and signs it, so the meter originates from
        #    exod and the agent cannot fabricate it — the proto-receipt a settlement plane will later trust.
        t0 = time.perf_counter()
        try:
            p = self._runner(prof, req["argv"], backend=backend)
        except Exception as e:
            # the confinement backend could not run the step (e.g. the selected runsc/bwrap is absent —
            # run_confined REFUSES rather than running unconfined). Turn ANY runner exception into a signed
            # REFUSED result: fail-closed, never run unconfined, never crash the limb. The signed reason stays
            # value-free ('sandbox:unavailable'); the real cause is logged to the limb's stderr for the operator.
            sys.stderr.write(f"[exod] step refused — sandbox backend could not run it: {type(e).__name__}: {e}\n")
            return refuse("sandbox:unavailable")
        meter = {"wall_ms": round((time.perf_counter() - t0) * 1000, 3), "by": "exod"}
        status = "ok" if p.returncode == 0 else "error"
        return self._sign_result(run_id=run_id, plan_sha=plan_sha, step=step, exit_code=p.returncode,
                                 status=status, output_sha=_sha(p.stdout or ""), nonce=rnonce, meter=meter)

    def _acl_check(self, req, gbody, *, now):
        """ACL M1 — the deny reason (str) if the grant's claim is OUTSIDE the operator-attested ACL, else None.
        Returns None (no enforcement) for a legacy grant carrying no acl_sha when not strict. exod RE-DERIVES the
        acl_sha (inside verify_acl_attestation) and independently re-runs acl_allows: it trusts govd's grant for
        NOTHING about the ceiling. The attestation's own nbf/exp is the freshness bound, checked at verify."""
        acl_sha = gbody.get("acl_sha") if isinstance(gbody, dict) else None
        if acl_sha is None:
            return "unscoped_grant" if self._acl_strict else None
        if self._acl_issuer_pub is None:
            return "no_issuer_pinned"
        att = req.get("attestation")
        if not att:
            return "attestation_missing"
        ok, why = verify_acl_attestation(self._acl_issuer_pub, att, now=now, expect_acl_sha=acl_sha)
        if not ok:
            return why
        acl = attested_acl(attestation_body(att))
        okv, prob = principals.acl_allows(acl, gbody.get("skill"), gbody.get("perk"),
                                          gbody.get("sandbox_tier"), gbody.get("destructive"),
                                          bool(gbody.get("credentials")))
        return None if okv else prob["id"]

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


def meter_of(envelope) -> dict | None:
    """The attested meter exod signed into a step-result (P2-T07), or None. Read it only AFTER
    verify_step_result confirms the envelope is exod's — the meter is trustworthy because it is inside the
    signature, not because the caller reported it."""
    return result_body(envelope).get("meter")


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


def load_vault(spec):
    """Build a vault from a spec: `file:/path.json` -> FileVault, `sops:/path.enc#/age.key` -> SopsAgeVault;
    None/empty -> no vault (exod then REFUSES any credentialed step, fail-closed)."""
    if not spec:
        return None
    kind, _, rest = spec.partition(":")
    if kind == "file":
        return _vaultmod.FileVault(rest)
    if kind == "sops":
        path, _, age = rest.partition("#")
        return _vaultmod.SopsAgeVault(path, age or None)
    raise SystemExit(f"exod: unknown vault spec {spec!r} (use file:/path.json or sops:/path.enc#/age.key)")


def main(argv=None):
    """The exec-image sidecar: load exod's identity key + govd's TRUSTED grant-issuer public key + (optional)
    a vault, then serve the confined-execution channel on the UDS — a separate process/principal from govd."""
    import argparse
    from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey, Ed25519PublicKey
    ap = argparse.ArgumentParser(description="exod — the confined execution limb (a separate signing principal)")
    ap.add_argument("--socket", default=os.environ.get("EXOD_SOCKET", "/run/cyberware/exod.sock"))
    ap.add_argument("--key", default=os.environ.get("EXOD_KEY"),
                    help="exod identity Ed25519 private key (raw 32 bytes)")
    ap.add_argument("--issuer-pub", default=os.environ.get("EXOD_ISSUER_PUB"),
                    help="govd's grant-issuer Ed25519 PUBLIC key (raw 32 bytes) — the ONLY key exod trusts")
    ap.add_argument("--acl-issuer-pub", default=os.environ.get("EXOD_ACL_ISSUER_PUB"),
                    help="ACL M1: operator ACL-issuer Ed25519 PUBLIC key (raw 32 bytes). When set, exod "
                         "re-enforces each ACL'd actor's ceiling under three-way dual-control")
    ap.add_argument("--acl-strict", action="store_true",
                    default=os.environ.get("EXOD_ACL_STRICT", "").lower() in ("1", "true", "yes", "on"),
                    help="ACL M1: REFUSE (not just audit) on an ACL failure or an unscoped grant")
    ap.add_argument("--vault", default=os.environ.get("EXOD_VAULT"),
                    help="vault spec: file:/path.json | sops:/path.enc#/age.key")
    ap.add_argument("--backend", default=os.environ.get("EXOD_SANDBOX_BACKEND", "bwrap"),
                    choices=("bwrap", "runsc"),
                    help="confinement backend: bwrap (default) | runsc (gVisor community tier, P2-T04)")
    a = ap.parse_args(argv)
    if not a.key or not a.issuer_pub:
        raise SystemExit("exod: --key and --issuer-pub are required (identity key + trusted grant issuer)")
    sk = Ed25519PrivateKey.from_private_bytes(open(a.key, "rb").read())
    issuer_pub = Ed25519PublicKey.from_public_bytes(open(a.issuer_pub, "rb").read())
    acl_issuer_pub = (Ed25519PublicKey.from_public_bytes(open(a.acl_issuer_pub, "rb").read())
                      if a.acl_issuer_pub else None)
    if os.path.dirname(a.socket):
        os.makedirs(os.path.dirname(a.socket), exist_ok=True)
    # P2-T04/P3-T11: --backend is the operator's confinement FLOOR. The default runner (run_confined) accepts the
    # per-step backend exod selects from the grant's sandbox tier (a community grant ratchets the floor up to
    # runsc); the floor itself is the minimum every step gets. A floor that cannot enforce on THIS host makes
    # those steps REFUSE (fail-closed, never run unconfined) — warn loudly at startup so the operator sees it.
    if not (runsc_available() if a.backend == "runsc" else is_available()):
        sys.stderr.write(f"[exod] WARNING: sandbox backend '{a.backend}' is NOT enforceable on this host — "
                         f"every step will be REFUSED (fail-closed), never run unconfined.\n")
    exod = Exod(sk, grant_issuer_pub=issuer_pub, vault=load_vault(a.vault), backend_floor=a.backend,
                acl_issuer_pub=acl_issuer_pub, acl_strict=a.acl_strict)
    acl_mode = "enforce" if (acl_issuer_pub and a.acl_strict) else "audit" if acl_issuer_pub else "off"
    print(f"exod · limb · socket={a.socket} · backend={a.backend} · keyid={_principal(sk.public_key())} · "
          f"trusts-issuer {_principal(issuer_pub)} · vault={'yes' if a.vault else 'none'} · acl={acl_mode}")
    exod.serve(a.socket)


if __name__ == "__main__":
    main()
