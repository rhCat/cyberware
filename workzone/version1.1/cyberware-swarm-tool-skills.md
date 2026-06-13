# cyberware swarm — tool-skill specifications

**The ten skills the construction swarm needs to validate itself.** Each is an ordinary cyberware skill
(blueprint · perks · contracts · in-skill self-test · pinned in the chip · signed from P3), so the
machinery that proves the platform is *inside* the tamper-evidence perimeter it enforces. Every skill
below is the `validated_by` target for some slice of the 90 tasks; building the skill is itself a task
(the bootstrap-exempt ones, validated by the external anchor per meta-rule M3).

The audit corrected a category error worth restating, because it shapes these specs: a task's **executor**
(how it runs) is distinct from its **validator** (what proves it). These skills are validators. They do
not *build* the deliverables; they *check* them — and from SV-2 onward they run through the governed
channel, so the proof of each construction step is itself a governed, recorded run.

Quick map:

| Skill | Authored by | Validates (criteria families) | Used by | External anchor (M3) |
|---|---|---|---|---|
| `cws-conform` | P0-T17 | F1, F11, P0-V0x | 18 P0 tasks | the Go verifier |
| `cws-ledgercheck` | P1-T09 | F2, F7, P1-V0x | 10 P1 tasks | the Go chain-checker |
| `cws-mutate` | P1-T10 | M11, all V-MUT | enforcement surface (R3) | mutation survival is self-evident |
| `cws-redteam` | P2-T08 | F9, P2-V0x | exod tasks | the Linux kernel |
| `cws-bench` | P2-T09 | P2-V07, P5/P6 perf | perf-bearing tasks | wall-clock on the reference env |
| `cws-chaos` | P2-T10 | M11, V-CHAOS, V-LIVE | partition/crash/failover | the OS scheduler / fault injector |
| `alchemy` | P3-T08 | F9, M11, P3-V15/16 | publish gate | alembic+putrefactio+TLAPS verdicts |
| `cws-release` | P3-T15 | F10, M1, P3-V0x | trust-plane tasks | Sigstore/Rekor public logs |
| `cws-modelcheck` | P4-T08 | F8, M4, P4-V0x | workflow + money | TLC + Apalache + TLAPS |
| `cws-settle-sim` | P6-T18 | M4, M7, P6-V0x | settlement plane | the PSP sandbox + zero-sum law |

---

## 1. `cws-conform` — protocol conformance

**Main functionality.** Proves that the CWP implementation matches the spec, byte-for-byte, across
implementations. It is the skill that makes "cyberware is a protocol, not a codebase" a checkable claim
rather than an aspiration. It replays the golden vector corpus through the local implementation, then
drives the independent Go verifier and diffs the two verdict streams — any divergence in canonical bytes,
digests, or signature outcomes fails the gate. It also re-pins the chip's own identity under canonical
hashing (the SV-1 self-referential act).

**Perks.**
- `vectors` — replay `spec/vectors/` through `infra/cwp`; emit `conformance.json` with per-vector
  `{id, canonical_ok, digest_ok, sig_ok}`. Contract check: `json: {failed: 0, total: ">=250"}`.
- `crosslang` — run the Go verifier over the same corpus; diff verdict streams; emit `crosslang.json`.
  Contract check: empty diff (V-EXT — the external anchor).
- `repin` — regenerate every skill index + chip manifest under JCS; emit the old→new `chip_sha`
  transition record. Contract: `skill_index --check` green; transition mapping stored.

**Inputs/outputs.** Reads the vector corpus + the registry; writes verdict JSONs + the transition map.
Read-only against everything except the regenerated indexes (which `repin` owns).

**Self-test.** A fixture vector set with one deliberately corrupted vector; the skill must flag exactly it.

---

## 2. `cws-ledgercheck` — ledger integrity

**Main functionality.** Proves the audit substrate is tamper-evident under concurrency and crash. This is
the skill that earns SV-2 — the rung where evidence stops being a CI log someone trusts and becomes a
chained, signed, independently re-verifiable record. It verifies chains (structure + signatures +
checkpoint roots), and it manufactures the abuse the ledger must survive: N concurrent governed writers,
crash injection, single-bit mutation.

**Perks.**
- `verify` — walk a target store: chain links, `prev` hashes, writer signatures, Merkle checkpoint roots;
  emit `{chain, records, bad_records, checkpoints_ok}`. Contract: `json: {chain: "ok", bad_records: 0}`.
  The recursive twist (SV-2): it verifies the ledger of its *own* verification run.
- `torture` — spawn N concurrent writers through the governed channel (default 16×5000), then `verify`
  the merged chain; emit loss/tear counts. Contract: zero lost, zero torn, single verified chain.
- `crashloop` — inject `kill -9` at random write offsets (default 500×); assert verify passes with at
  most one cleanly-truncated, recorded tail. (V-CHAOS-adjacent; the crash machinery is shared with
  `cws-chaos`.)

**Inputs/outputs.** Reads/writes only test stores under the record root; never touches production ledgers.

**External anchor.** The ~150-line Go chain-checker cold-verifies every fixture and CI-produced ledger.

---

## 3. `cws-mutate` — enforcement-surface mutation testing

**Main functionality.** Proves that every gate actually gates — that deleting or inverting a check makes
CI fail. This is the inherited discipline from the ancestor program (M11), generalized into a class:
V-MUT applies to the *entire* enforcement surface (R3), not the two spots v1.0 named. A gate that
survives its own deletion was never a gate; this skill is what catches the survivors.

**Perks.**
- one perk per R3 entry — `mut-authorize-step`, `mut-result-acceptable`, `mut-tamper`, `mut-oversight`,
  `mut-snippet-verify`, `mut-grant-verify`, `mut-approval`, `mut-revocation`, `mut-settlement`,
  `mut-chain-verify`, `mut-concord`. Each applies a mutation operator set to its target, runs the
  relevant test slice, and asserts CI *fails*; emit `{gate, mutants, killed, survived, score}`.
  Contract: `json: {mutation_score: ">=0.90"}`, survivors listed by mutant id.

**Inputs/outputs.** Reads the target module + its tests; writes a per-gate mutation report. Operates on
copies, never the live tree.

**Why it has no external anchor.** Mutation survival is self-evident: either the test suite caught the
sabotage or it didn't. The proof is internal by nature — which is exactly why it's safe to self-host.

---

## 4. `cws-redteam` — the attack corpus as a skill

**Main functionality.** Proves the privilege boundary is real — kernel-enforced, not advisory. This is
the skill that earns SV-3, and it embodies meta-rule M4: *refusals are evidence*. Each malicious behavior
is a perk whose contract **expects refusal** (nonzero exit + a named refusal class), run inside the
community sandbox profile under exod's own observation. The proof of containment is the recorded failure
of each attack.

**Perks (≥12, one attack class each).**
`read-vault`, `read-shadow` (`/etc/shadow`), `read-pid1-environ` (`/proc/1/environ`), `egress-unlisted`
(a local listener on a non-allowlisted port), `dns-exfil`, `write-outside-store`, `write-registry`,
`fork-bomb` (vs the `pids` limit), `wall-overrun`, `mem-overrun`, `ptrace-attempt`, `device-access`.
Each contract: `expect: {exit: nonzero}` + the specific refusal class asserted in the record.

**The crucial variant (V-EXT).** Every case re-runs with the in-process oversight scan *disabled* — and
must still refuse. That isolates the kernel as the counterparty: the refusal comes from namespaces,
seccomp, and cgroups, not from cyberware's own software. The Linux kernel is the external anchor.

**Inputs/outputs.** Writes only refusal records. The attacks are real attempts against a real sandbox;
the whole point is that they fail at the OS boundary.

---

## 5. `cws-bench` — attested performance

**Main functionality.** Proves the boundary's overhead is within budget, and — as a side effect that
matters enormously — produces the *first attested-meter artifacts* years before money touches them. The
meter pipeline exod will later settle against is dry-run here: `cws-bench` measures through the channel,
exod signs the meters, and the bench receipt is both the performance evidence and the proof that metering
works.

**Perks.**
- `sandbox` — measure per-step overhead of each `SandboxProfile` vs direct execution; emit attested
  `{profile, p95_ms, cold_ms, warm_ms}`. Contract: bwrap ≤100 ms p95/step; microVM ≤1500 ms cold,
  ≤250 ms warm (the §3 reference-env budgets).
- `channel` — measure govd `/govern` latency and throughput under load; emit `{rps, p95_ms, rss_slope}`.
  Contract: p95 ≤150 ms at 50 rps; RSS slope ≤1 MB/h after warmup.
- `settle` (P6) — measure settlement throughput with group commit; emit `{tps, p95_ms,
  checkpoint_resume_ms}`. Contract: ≥200 settlements/s; p95 ≤250 ms; resume-verify ≤2 s at 1M entries.

**Inputs/outputs.** Reads nothing sensitive; writes attested-meter receipts. All budgets are defined *on*
the pinned reference env (V-BENCH), and per-deployment re-bench is the same skill run elsewhere.

**External anchor.** Wall-clock on the reference environment — the numbers are what they are.

---

## 6. `cws-chaos` — fault injection and liveness

**Main functionality.** Proves the system survives partitions, crashes, and failovers without losing or
duplicating work, and that stuck states make progress within a bound. This skill owns the two newest
criterion classes: V-CHAOS (it must recover) and V-LIVE (it must progress). Every recovery invariant
traces to a decided sentence in `spec/inflight.md` — the chaos skill is how those sentences stop being
prose.

**Perks.**
- `partition` — sever govd↔exod mid-step; assert the running step completes, the next `step_request`
  fails closed, WS resume replays the last grant idempotently, zero duplicate ledger records.
- `crash-exod` — kill exod mid-sandbox; assert the orphan sandbox is cgroup-reaped, the step records
  `error`, the run is resumable from recorded state.
- `crash-settle` (P6) — kill the settle engine mid-posting-set; assert all-or-nothing (group write +
  single fsync), exactly-once replay, conservation holds through the crash.
- `failover` (P5) — kill active govd mid-stream; assert the standby acquires the advisory-lock lease,
  WS sessions resume, zero duplicate grants, zero lost `step_result`s, no orphaned run beyond lease
  TTL + 30 s.
- `skew` — inject ±5 min clock skew; assert grants and nonce caches behave exactly per `spec/time.md`
  (monotonic TTLs unaffected; wall-clock checks fail closed).

**Inputs/outputs.** Operates on disposable test deployments; asserts invariants, records refusals as
evidence (M4 again — a correct refusal under fault is a pass).

**External anchor.** The OS scheduler and the fault injector — the system either reconverges or it
doesn't, observably.

---

## 7. `alchemy` — the ancestor, repatriated

**Main functionality.** This is the lineage made load-bearing: the Magnum Opus analysis pipeline
(alembic + putrefactio, with TLAPS reachable through `cws-modelcheck`) wrapped as a governed skill, in
**file-mode** — no Postgres warehouse dependency on the chip path, so the chip stays self-contained. It
is the publish gate's engine: it extracts a snippet's *actual* L++, walks its conservation law, names its
shapes, and checks the extracted control-flow against the *declared* blueprint. It turns "trust the
publisher's blueprint" into "verify the code agrees with its claim" (blueprint concordance — the gap
nothing in v1.0 covered). From P6 it also *earns*: published as priced analysis perks, the parent
toolchain takes royalties validating the descendant's marketplace.

**Perks.**
- `extract` — source core → AtomTree → L++ blueprint JSON, per snippet. Contract: L++ emitted per core.
- `conserve` — the conservation walker: per-function `acquires` vs `releases`; emit defects. Contract:
  `json: {unexplained_defects: 0}` for verified tier, or a recorded approval-waiver reference.
- `classify` — putrefactio's closed-enum classifier: every shape gets `{shape_id, kind}`. Contract:
  `json: {unnamed: 0}` for verified tier; an `unnamed` shape routes to review (where naming it grows the
  enum — Decision 16 performed as a marketplace act) or to community-tier containment.
- `concord` — diff the extracted CFG against the declared `blueprint.json`; the code must be structurally
  contained in its claim. Contract: empty containment diff; the diff artifact stored with the release.

**Inputs/outputs.** Reads snippet sources + declared blueprints; writes L++ / defect / shape / concord
artifacts. Pinned: alembic + putrefactio + `laws/` commits in `deps.lock.json` (T24/T25) — the parent
submits to the child's authenticity discipline.

**External anchor.** alembic's and putrefactio's own verdicts (and, for the proof class, TLAPS) — three
independently-built analyzers, not cyberware's opinion.

---

## 8. `cws-release` — the registry (and engine) publishes itself

**Main functionality.** Proves provenance: that every chip release — and, the v1.1 addition, every
*engine* release — is signed, transparency-logged, and revocable, and that the verifier is itself
verified. This is the skill that earns SV-4, and its self-referential act is literal: the registry
publishes itself *through this perk chain*, and the release that introduces engine attestation is the
first attested engine release. It composes the proven trust rails (Sigstore, Rekor, the revocation feed)
rather than reinventing them (F10).

**Perks.**
- `index` — regenerate the skill/chip authenticity indexes (canonical). 
- `sign` — cosign sign-blob over `skill_sha` / chip manifest (Fulcio keyless or BYO); verify hook.
- `log` — append the release to Rekor; store the inclusion proof. Contract: proof verifies offline
  against the pinned root (V-EXT).
- `manifest` — update the chip manifest; assert post-release consistency.
- `engine` — the M1 fix: reproducible engine build → SLSA provenance → sign → Rekor; `/health` attests
  the engine digest; govd↔exod exchange release attestations at handshake. Contract: a 1-byte-tampered
  engine on either side fails the handshake with `engine_unattested`.

**Inputs/outputs.** Reads the registry/engine build; writes signatures, inclusion proofs, the updated
manifest. The whole release is itself a dual-signed receipt (SV-4 evidence).

**External anchor.** Sigstore's and Rekor's public logs — non-equivocation enforced by infrastructure
outside cyberware's control.

---

## 9. `cws-modelcheck` — three certificate classes

**Main functionality.** Proves the formalism checks what matters: invariants, failure topology,
composition — and, the M4 centerpiece, that **the money's own lifecycle is sound before a single credit
exists**. It runs the blueprint/workflow through three independent checkers and records a certificate
per class: **EMPIRICAL** (TLC), **SYMBOLIC** (Apalache), **AXIOMATIC** (TLAPS), with honest `Unproved`
where proofs don't close. It is the skill that earns SV-5, whose self-referential act is encoding *the
remaining plan* as a workflow and verifying it deadlock-free.

**Perks.**
- `check` — run TLC + Apalache + TLAPS on a blueprint or `workflow.json`; emit certificates
  `{empirical, symbolic, axiomatic, unproved_modes}`. Contract: TLC `no_error`; Apalache agreement (diffs
  block + triage); AXIOMATIC stamp or classified `Unproved`.
- `corpus` — run the ≥6-defect known-bad set (compensation cycle, retry livelock, par mutual-wait,
  unreachable compensation, lost terminal, invariant violation); assert all caught. Contract:
  `caught: 6/6` by TLC, ≥5/6 by Apalache.
- `money` (P6) — check `settlement.blueprint.json`: safety (escrow empties, no settle-before-validate, no
  double-settle) + liveness (◇terminal under fairness, the expiry timer as progress guarantee). Contract:
  EMPIRICAL+SYMBOLIC pass; seeded money-mutants each fail.

**Inputs/outputs.** Reads blueprints/workflows; writes certificates + TLA specs + full checker logs into
the run record (M4's persistence — not /tmp). Carries the P4-W1 work item: the Mode-3 THEOREM-emission fix
in `hyper_tla::generate_tla`.

**External anchor.** Three independently-built checkers; AXIOMATIC verdicts reproduce cross-arch from the
pinned tlapm build.

---

## 10. `cws-settle-sim` — the economy's torture chamber

**Main functionality.** Proves the settlement plane conserves value under storms, refunds, clawbacks, and
manipulation — and that its price oracle resists gaming. This is the skill that earns SV-6, the rung where
the system pays for its own completion. It runs randomized settlement storms through the governed channel,
exercises every refund/dispute path, and simulates an adversary trying to move the FMV index. The
governing law it enforces is the conservation axiom's money face: *no chrysopoeia by decree* — every
credit traces to a funded task, and the books sum to zero including dust.

**Perks.**
- `storm` — 10k randomized settlements (mixed pricing models, refunds, clawbacks, holdbacks); assert
  per-record and global per-currency zero-sum, escrow/hold accounts zero at every terminal. Contract:
  `zero_sum: exact`.
- `manipulate` — an adversary controlling X% of admitted volume tries to move the index; assert <2% drift
  at 20% adversarial volume; sub-admission indices marked `provisional`. Contract: `index_drift: "<2%"`.
- `dispute` — full lifecycle: bond posting, m-of-n resolution via the approval artifact, clawback from
  holdback, reputation delta — all ledgered. Contract: lifecycle complete + balanced.
- `idempotency` (6d) — replay every adapter event 2–10×; assert final balances identical to
  single-delivery; zero idempotency violations across 10k events.

**Inputs/outputs.** Operates on a test economy in internal credits; the live PSP path is reconciled
separately against the Stripe sandbox.

**External anchor.** The PSP sandbox reconciliation (exact to 0.0001 CWC) and the zero-sum law itself —
a violated conservation invariant is mechanically detectable, no judgment required.

---

## Cross-cutting notes

**Authoring order within a phase.** Build each phase's validator *first*, even though its task id sorts
late — the swarm's `validation_available_after` field encodes this, and the manifest's `ordering_rule`
states it. A phase whose validator lands last cannot validate its own siblings as they're built, which
defeats the ladder.

**The bootstrap exemption (M3).** Ten of these skills cannot be validated by themselves at birth —
cws-conform can't prove cws-conform. Their authoring tasks are `bootstrap_exempt: true` and validated by
the external anchor in the table above. This is not a gap in rigor; it is the rigor — self-validation that
refused an external anchor would prove only internal consistency, never correctness.

**Why these are skills, not scripts.** Pinned in the chip, signed from P3, carrying their own self-tests,
the validators live inside the tamper-evidence perimeter they enforce. Corrupting a validator changes the
`chip_sha` and refuses at boot. The guardians are governed by the thing they guard — *quis custodiet
ipsos custodes*, answered by making the same discipline apply all the way down, anchored to the world.

**The recursion that gives the chill.** From SV-2 onward, building the platform *is* running the platform:
each construction task's CI gate is a governed run (meta-rule M5), validated by one of these skills,
recorded in a chained ledger, and — by SV-6 — settled as a bounty. The swarm is not a plan executed
against the system; it is the system's first workload, and these ten skills are how it grades itself.
