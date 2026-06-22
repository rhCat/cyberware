# Containment via exod delegation (v1.1 full-close headline)

**Status (2026-06-22):** the foundation is merged AND the live wiring is **built + adversarially reviewed**;
all 8 confirmed review findings are folded in (see *Review findings folded in* below). Remaining: push +
PR + CI + merge, then the exec-image (Linux+bwrap) validation pass on the action-runner node.

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
2. **Workspace materialization + closure integrity** (THE load-bearing security item — get this wrong = a
   snippet TOCTOU hole, the P1-T06 class). **RESOLVED:** govd materializes a per-run workspace
   (`delegate.materialize_workspace`) — the blessed wrapper + a copy of the perk src closure — and exod
   **itself** re-derives the digest of every staged file *at time of use* (`infra/exec/closureverify.py`,
   its own prose-clean 1.0 mutation gate) and refuses any member that does not match the grant's signed
   `snippet_shas` pin, plus any unpinned sibling. So the integrity check is **exod's**, against the signed
   pin — NOT govd attesting to its own freshly-copied bytes, and NOT a digest the caller computed. This
   closes the post-grant porter/core swap (the review's findings 1/2/4) and the empty-pin fail-open
   (finding 6); it is cooperative-parity with `_verify_registry` + `skill_index.verify`.
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

## Review findings folded in (commit on `feat/v11-govd-delegation`)
The mandatory adversarial review (3 attack lenses → per-finding verify) confirmed **8 findings, all
net-new to the delegated path**; every one is addressed:
- **1/2/4 (major) — self-referential snippet pin / swapped-core / no time-of-use re-hash.** exod trusted
  `req['snippet_sha']` (a digest govd computed) and checked only the porter. Fix: `closureverify.closure_decision`
  — exod re-hashes the **whole** materialized closure at time of use vs the grant pin; `req['snippet_sha']`
  and `delegate._porter_sha` are deleted. New first-class mutation gate (12/12 killed, floor 1.0).
- **6 (minor) — empty `snippet_shas` failed open.** Now: staged code under an empty pin is refused
  (`closure:unpinned`); a raw-argv run with no staged closure stays runnable (keeps the SV-3 red-team oracle).
- **3/7 (major+minor) — `credential_ids` never populated → vault injection was dead.** `compiler.build_plan`
  now sources the perk manifesto's declared `credentials` (names only, server-authoritative); govd binds them
  onto the run record; `test_delegate` proves a granted secret reaches the confined step (and the masking
  `_rec()` fixture no longer hardcodes `[]`).
- **5 (major) — at-most-once lost in delegated mode.** The delegated WS branch now refuses a re-sent
  `step_request` for an already-recorded step *before* dialing exod (no double-execution / double-bill).
- **8 (nit) — handler TypeError if the run is evicted mid-session.** The delegated branch fails closed on a
  `None` record (`run no longer resident`) instead of crashing the connection thread.

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
