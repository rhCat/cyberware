# Containment via exod delegation (v1.1 full-close headline)

**Status (2026-06-26): SHIPPED (v1.1 closed).** Delegation is live: govd in `delegated` exec_mode hands a
single-use **signed grant** to **exod**, which runs each step confined (bwrap / gVisor) and **Ed25519-signs**
the authoritative status — govd never executes. The **`cyberware-body`** image unifies govd-delegated + exod
in one non-root Linux container (`ghcr.io/rhcat/cyberware-body`, `Dockerfile.body`). Cooperative
(`run_governed`) stays the default; delegated (`run_delegated`, `--delegated`) is opt-in and Linux-only. The
sections below record the design verdict, what shipped, and the adversarial review that hardened it.

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

## The live wiring (shipped in v1.1)
All eight items below landed and are covered by tests + adversarial review — this is the as-built map.

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
6. **`govd_executor.serve` stays a working reference** for the server-side **cooperative** model (the
   never-root selftest + backward-compat) — it was *not* retired to a stub. Confinement lives in **exod** for
   **delegated** mode only; the two coexist and the operator selects per principal via `exec_mode`.
7. **`GET /health`** exposes `exec_mode` + `exod_attached` (top-level); a delegated govd that can't reach
   exod refuses every step (fail-closed) and `/health` shows it.
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
- **5 (major) — at-most-once lost in delegated mode.** `Store.claim_step` atomically reserves `(run,step)`
  under the store lock spanning the whole check→dial-exod→record window, released by `release_step`. A
  completed (recorded ok/error) OR a concurrently in-flight step is refused *before* dialing exod — so two
  WS sessions racing the same step cannot double-execute / double-bill, not just sequential re-sends. A step
  exod *refused* (never ran) is recorded under a distinct `step_delegation_refused` type, outside the
  done-set, so a transient refusal is retryable rather than wedging the run.
- **8 (nit) — handler TypeError if the run is evicted mid-session.** The delegated branch fails closed on a
  `None` record (`run no longer resident`) instead of crashing the connection thread.

A second adversarial pass on these fixes confirmed 9 findings (3 of them the same concurrency race, now
closed by `claim_step`); the closure prose was narrowed (the gate covers the materialized SNIP closure; the
entry `run.sh` rests on the plan-hash), and the empty-pin discriminator was hardened from a `.sh/.py`
allowlist to a denylist (any staged non-`contracts.json` file is refused).

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

## Follow-ups (post-ship)
- The `/health` `exec_mode` + `exod_attached` surface has shipped; the README ("Two run modes" + the image
  catalog), SKILL.md, cyberware.md, and the homepage now state both modes plainly — the cooperative path
  runs client-side (unconfined by the kernel; the agent's own host), and confinement is delivered via exod
  (delegated mode) on the `cyberware-body` Linux image.
- Open: the `govd.py` module header + boot banner still describe the cooperative path only — keep "never
  executes" but add delegated mode (the authoritative status is exod's signed result) and document
  `exec_mode` + the `exod.*` config keys. (`govd_executor.py`'s docstring is correct as the cooperative
  reference — see item 6 above; no change needed there.)

## Known boundary — delegated mode requires self-contained, flat-src perks
The closure gate verifies a perk's OWN top-level `src` against the grant pin. Two perk shapes are therefore
unsupported under delegated mode and **fail closed** (never run unverified):
- **nested `src`** — a perk pinning a member in a subdir (e.g. `src/lib/helper.py`) is refused
  `closure:missing` (govd materializes flat top-level src). Zero perks do this today; the build gate does not
  yet forbid it.
- **cross-perk sourcing** — a porter that reads a sibling perk's files (today only `codebaseqc/setup`, which
  `cp`s from `../../audit/src`) cp-fails inside bwrap because those files are outside the workspace. The agent
  cannot inject them (they are outside the single writable dir), so it is fail-closed, not a bypass.
Both are cooperative-mode-only perks in practice; making delegated mode support them (recursive materialize +
a plan-build-time self-containment check) is a v1.2 item.

## Deferred to v1.2 (explicitly out of this close)
exod horizontal-scale/liveness (single serving thread); grant-key custody to an HSM/PKCS#11; supervised exod
lifecycle (systemd, distinct uid, orphan reaping); SopsAgeVault as the live backend; workspace output quota;
removing the legacy client-self-report path; recursive/cross-perk closure materialization + a build-time
self-containment gate (see *Known boundary* above).
