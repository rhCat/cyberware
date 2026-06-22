# Containment via exod delegation (v1.1 full-close headline)

**Status (2026-06-22):** the *foundation* is merged; the *live wiring* is the remaining focused effort.

## The decision (design-panel verdict)
govd **delegates to exod the limb** over the UDS — it does **not** execute itself. Decisive reasons,
grounded in the merged code:
- the settlement plane (`infra/settle/metered.py:57`) refuses any meter whose `by != "exod"`, so a
  govd-executes path is structurally un-settleable and re-introduces the self-report exod replaced;
- it keeps govd's **"never executes"** invariant literally true (`govd.py` header + boot banner);
- it preserves **dual-control** — the grant-issuer key (govd) ≠ the executor identity key (exod),
  enforced at `Exod.__init__` (`infra/exec/exod.py:46`).

So: `govd_executor.serve` (the govd-executes approach, P2-T12's first cut) is **retired to a refusing
stub**; execution lives only in exod.

## Done
- **#134** — crash-atomic `Store._persist` (unique-tmp, fsync, os.replace) + `require_closed_auth` (remote
  fail-closed) + `deploy/setup-lightsail-node.sh`.
- **#135** — `Exod(vault=...)`: the limb resolves the **grant-authorized** credential names
  (`grant.credentials`, signed) via its own vault and injects them into the confined step's profile env
  (`--setenv` after `--clearenv`); fail-closed without a vault. Tests in `tests/test_exod.py`.

## Remaining build plan (the live wiring — the next PR)
1. **exod sidecar `__main__`** (`infra/exec/exod.py`): a CLI that loads exod's identity key + the trusted
   grant-issuer pub (`keystore.FileKeyStore`) + a `FileVault`/`SopsAgeVault`, then `Exod(...).serve(socket)`.
   This is what the exec-image sidecar/systemd unit runs.
2. **Workspace materialization** (THE load-bearing security item — get this wrong = a snippet TOCTOU hole,
   the P1-T06 class). Before the runner runs, the workspace must hold the blessed wrapper + the
   **hash-verified** perk src so the grant's `snippet_shas` pin guards real code. Lift `govd_client._prepare`
   (`govd_client.py:169-180`) server-side. OPEN QUESTION to settle first: does **govd** materialize a shared
   workspace (exec-image shared volume) and pass the path, or does **exod** materialize from its own
   registry keyed by `snippet_shas`? And where does the per-step porter re-hash happen (exod must re-hash at
   time-of-use, mirroring `executor.snippet_decision`, so a post-grant mutation is refused) — do NOT trust
   the grant's `snippet_shas` alone.
3. **ExodClient seam in `serve(cfg)`** (`govd.py`): read `exod.socket` (default `/run/cyberware/exod.sock`),
   `exod.grant_key` (govd's Ed25519 grant-issuer PRIVATE key via keystore), `exod.pub` (exod identity PUBLIC
   key); stash on `httpd`. The vault is constructed **nowhere in govd** — it lives beside exod.
4. **Delegate in the WS step path** (`_ws_oversight`), guarded by a per-principal `exec_mode` (operator-set
   in the principals registry, stamped per-run, NOT agent-negotiable). After `authorize_step` (keep it as
   govd's pre-spend plan-hash/order gate): mint a single-use grant (`grants.mint_grant`, tight TTL, nonce,
   `snippet_shas=rec['snippet_shas']`, `capabilities=['run']`, `credentials=<authorized>`), `request_step`
   over the UDS, `exodverify.verify_step_result` + a **durable nonce-replay** check against the run's
   recorded result nonces; on ok append the SIGNED status + `meter_of(env)` + `exod_keyid`; on fail append
   `forged_status_refused`. Client mode unchanged.
5. **Reject agent self-report in delegated mode**: govd already recorded exod's authoritative result, so an
   agent-sent `step_result` is a no-op refusal via `result_acceptable`'s already-recorded path.
6. **Retire `govd_executor.serve`** to a refusing stub (`{status:'refused', reason:'execution_moved_to_exod'}`),
   keeping the never-root selftest semantics. Execution lives ONLY in exod.
7. **`GET /health`** exposes `exod:{reachable, keyid}`; a delegated govd that can't reach exod refuses every
   step (fail-closed) and `/health` shows it.
8. **`govd_client.run_delegated()`** — a thin variant that sends `step_request` and loops on acks, spawning
   NOTHING. `run_governed` stays the legacy cooperative local-dev mode (untouched).

## Validation
- **macOS (now):** the channel logic via the `runner=` stub + a real AF_UNIX loopback (`serve(max_requests=N)`):
  authority is exod's signed status not the agent's; unreachable socket → refuse-every-step; forged envelope
  → `forged_status_refused`; grant-nonce replay across a simulated restart caught; agent self-report rejected;
  `vault.secret_bytes_in(govd process env)==0` during a delegated run; the `--setenv`-after-`--clearenv`
  string assertion in `test_sandbox.py`; chaos partition/crash-exod drills stay green.
- **Exec image (Linux + bwrap, `docker run --privileged`):** the `redteam.py` sandbox family (fs-escape,
  net-egress, mount, sysrq, proc-sys, device-raw, write-rofs/outside) THROUGH the govd→UDS→exod path each
  exits nonzero → exod signs error, benign oracle signs ok; server-side vault reaches the confined step
  while no-net/ro-system/nobody hold; `bench_bwrap` p95 ≤ 100 ms through the new hop; `metered.py` settles
  the real exod meter.
- **Full multi-agent adversarial review before merge** (enforcement-surface + a security-critical rewire).

## Docs/claims to fix when it lands
- `govd.py` header + boot banner: keep "never executes", ADD delegated mode (authoritative status is exod's
  signed result); document `exec_mode` + the `exod.*` config keys.
- `govd_executor.py` docstring: record execution moved to exod (module retired to a stub); update the
  `exec-never-root` memory.
- The gh-pages homepage / status report: stop describing the DEFAULT path as containment until delegated
  mode ships; state plainly that the cooperative path runs client-side unconfined and confinement is
  delivered via exod (delegated mode) on the exec image.

## Deferred to v1.2 (explicitly out of this close)
exod horizontal-scale/liveness (single serving thread); grant-key custody to an HSM/PKCS#11; supervised exod
lifecycle (systemd, distinct uid, orphan reaping); SopsAgeVault as the live backend; workspace output quota;
removing the legacy client-self-report path.
