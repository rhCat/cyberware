# cyberware — Foundation Plan v1.1

**Substrate for a verifiable work economy: compose hardened services — including our own ancestor — verify everything, let the skeleton validate its own growth, and never mint what was not earned.**

| | |
|---|---|
| Version | 1.1 (supersedes 1.0) |
| Date | 2026-06-12 |
| New in 1.1 | (1) dispositions of the plan-grill findings M1–M14, each folded, reframed, or ruled out-of-scope **on the record** · (2) **composition of the ancestor**: the Magnum Opus / alembic / putrefactio pipeline enters the register and the chip · (3) doctrine additions: principal-key agnosticism, substrate-not-economy, denominated promises, one-axiom-three-faces, no chrysopoeia by decree |

---

## 0. Changelog — the disposition record

v1.0 was itself grilled; v1.1 is the answer, recorded in the project's own decision-log culture. Three disposition classes: **folded** (became build items + criteria), **reframed** (the maintainer's counter-position prevailed and reshaped the item), **out-of-scope by doctrine** (excluded deliberately, with the doctrine sentence that excludes it — exclusion is a decision, not an omission).

| M | Finding (one line) | Disposition | Lands in |
|---|---|---|---|
| M1 | the engine itself was unattested — the verifier missed its own tail | **folded** | P0 reproducible builds (T28); P3 `cws-release/engine` + govd↔exod mutual attestation |
| M2 | no key lifecycle: generation, custody, rotation, compromise, bootstrap | **folded** | P0 `spec/keys.md`; P3 rotation drill; T29 custody seam |
| M3 | all integrity, zero availability; fail-closed with no liveness story | **folded** | new V-LIVE class (§4); feed grace tiers (P3); HA design (P5); escrow expiry (P6) |
| M4 | the money was never model-checked | **folded** | `settlement.blueprint.json`: verified in P4, implemented verbatim in 6a |
| M5 | immutability vs privacy law; metadata is data; `/rep` published PII | **folded** | P0 `spec/privacy.md`; P1 crypto-shredding; 6d `/rep` gating |
| M6 | break-glass paradox: the governed CI gate can't merge the fix for a broken channel | **folded** | ladder meta-rule **M6** (§3.3) |
| M7 | reward ledger: O(history) verification, no TPS budget, no idempotency | **folded** | Ledger-v2 Merkle checkpoints (P1); 6a idempotency + TPS budget |
| M8 | time had no authority: clocks were trusted, timestamps self-asserted | **folded** | P0 `spec/time.md` + T27; P3 TSA countersignatures |
| M9 | in-flight transitions undefined (revocation mid-run, cancel, metered escrow, schema evolution, WS drop) | **folded** | P0 `spec/inflight.md` — five decided sentences (§7) |
| M10 | the schedule was a staffing fantasy; "truth over promise" framing | **reframed** (Rui: promise sells better than truth) | §14: **denominated promises** outward, **the spine** inward; MVP = SV-3 |
| M11 | mutation/chaos testing under-applied | **reframed** (Rui: the foundational analysis tool *predates* cyberware) | V-MUT + V-CHAOS classes (§4); §2 ancestor composition; T24–T26; the `alchemy` skill |
| M12 | legal/disclosure layer absent | **out-of-scope by doctrine** (Rui: with everything auditable, disclosure becomes *willingness rather than possibility*) | §15; residue: one SECURITY.md doorbell; self-bounty as 6d roadmap |
| M13 | money dust, credit policy | **split** (Rui: we are not the Fed/SEC/NYSE — substrate, not economy; conceded that dust is microstructure) | dust account + rounding rule → 6a; credit/price/monetary policy → §15 |
| M14 | the agent's side of the boundary unstated | **out-of-scope by doctrine** (Rui: an agent can be a human, a model, or a dog) | §1 **principal-key agnosticism**; §15 |

The second event this revision records: the disclosure of the **Magnum Opus lineage** (§2). cyberware is not adjacent to a code-analysis program; it is the *descending arc's ascending twin*, and v1.1 composes the ancestor rather than rebuilding its organs.

---

## 1. Doctrine

The v1.0 principles stand — transition not rebuild; the novelty budget; dependencies are cartridges; the stdlib boundary ends exactly at signatures. v1.1 adds five doctrine sentences, each earned in review:

**One axiom, three faces.** The founding conservation law — *per function, acquires must balance releases* — instantiates three times across the program: per **function**, acquires = releases (the alembic walker); per **run**, every grant terminates in a recorded outcome (the governed channel); per **settlement**, every credit balances a debit and every escrow empties (the reward ledger). Resources, authority, value: one law, three faces. Wherever a new subsystem appears, the first design question is which face of the axiom it must wear.

**Principal-key agnosticism.** An agent is whatever holds a principal key — a human, a model, a committee of models, or a dog. The platform authenticates keys, validates work, and makes no claims about the intelligence behind them; it solidifies the substrate, never the mind. One deliberate exception sharpens the doctrine rather than breaking it: **approval is WebAuthn-locked** — species-blind at the claim, species-locked at the consent. Who works is none of the platform's business; who consents to destruction is precisely its business.

**Substrate, not economy.** cyberware is Fedwire's discipline, not the Fed's mandate: it defines tick size, settlement mechanics, and conservation — never value, credit terms, interest, float policy, or where prices settle. The market grows on the substrate; the substrate's sole promise is that it sums to zero and never lies.

**No chrysopoeia by decree.** Value is never minted, only earned by transmutation of validated work. Every credit traces, through a dual-signed receipt, through a blessed plan, to an initiator's funded task. This is the conservation axiom's money face stated as prohibition, and it is also the primary anti-farming defense.

**Denominated promises.** Externally, promise large — but denominate every promise in ladder rungs and dates: *attested sandboxed execution by SV-3 on date D₁; the registry publishing itself by SV-4 on D₂; the system paying for its own completion by SV-6 on D₃.* A promise with a settlement date is more fundable than modesty and more credible than hype — the roadmap is itself a claim the ladder blesses and the receipt redeems. Internally, build the spine (§14). And one doctrine sentence M12 contributed: because every run is already evidence, **disclosure is willingness rather than possibility** — audit becomes a query, and a choice is cheap to exercise.

---

## 2. The lineage — composing the ancestor

**What exists.** The Magnum Opus program (Cyberware Alchemistry) is a five-phase, six-language analysis pipeline built on the conservation axiom: **alembic** (nigredo+albedo+citrinitas) extracts source → AtomTree → **L++ blueprints** — *states, transitions, gates, actions, safety_invariants*, the exact schema cyberware's skills declare by hand — plus per-function contracts (`acquires · releases · transfers_in · escapes`), then mechanically preprocesses: TLA+ generation, **TLC** (EMPIRICAL certificates, ~250k verdicts at locked baseline), **TLAPS** via a patched arm64 tlapm (AXIOMATIC certificates / honest `Unproved`), the **conservation walker**, and feature-path traversal. **putrefactio** is the only place interpretation happens, and even there it is rule-based: Decision 16, *give shape a name, not find name a shape* — a closed-enum classifier emitting `{shape_id, kind ∈ known | unnamed}`. **cibatio** (synthesis) is paused at the **P5 wall**: 12/12 shape-match, 0/12 semantic relevance — synthesis without semantic ground. The discipline this plan calls a "self-validation ladder" has run there for months as **ouroboros rounds** with locked baselines held through 38 rounds (R16→R53).

**What this means for the plan.** Three corrections and one bridge.

*Correction 1 — M11 inverted.* The testing rigor I prescribed is the family method; cyberware doesn't adopt mutation/chaos discipline, it **inherits** it. V-MUT and V-CHAOS enter the taxonomy as repatriation, not new scope.

*Correction 2 — composition over construction.* Two organs budgeted as builds become imports: Phase 3's publish-time analysis gate (was: heuristic lint) becomes **alembic extract + conservation walk + TLC on the snippet itself**; Phase 4's prover gains **TLAPS** as the AXIOMATIC certificate class. The plan's own first principle — never rebuild a hardened service — now applies to the one dependency whose 53-round validation history the maintainer personally holds.

*Correction 3 — F9 finally dies properly.* Deny-list regex (enumerate badness) is replaced by Decision 16 inverted into security: putrefactio names the shapes in every snippet; **known shapes admit per tier policy, `unnamed` shapes route to review or community-tier containment** — allowlist semantics. And the review act *is* the doctrine: reviewing a skill means naming its shapes, growing the closed enum. Regex is formally demoted to a lint.

*The bridge — rubedo (ROADMAP).* The P5 wall asked for semantic ground; putrefactio supplies what a shape **is**. The settlement plane supplies what a shape is **for**: initiators paying, validations passing, disputes failing to materialize, FMV forming — *revealed preference*, the one semantic signal no static analysis can fake long-term. When rubedo wakes, its synthesized perks enter the chip through the governed channel, are classified by putrefactio, priced by the market, and the clearing data flows back as grounding. cyberware is rubedo's distribution, monetization, **and feedback** layer. This bridge is ROADMAP — named, not scheduled.

**One new criterion class falls out of the lineage** and closes a gap nothing in v1.0 covered: **blueprint concordance.** A skill's declared blueprint was, until now, an assertion. With alembic on the chip, the snippet's *actual* L++ is extracted and checked against the declaration — initially as structural containment (every extracted transition maps into a declared action's contract), with full refinement proof as ROADMAP. The code must agree with its claim; the chip stops taking anyone's word, including the publisher's.

**Staffing, restated honestly under the lineage.** This is now visibly two foundation-scale programs and one Rui — but the composition is *subtraction*: the analysis organ and the prover were budgeted as builds and just became imports. And the staffing model itself converges with the product: one human plus governed agents, where each ladder rung transfers more of the construction into the channel — SV-2 makes CI a governed run, SV-6 makes development a settled bounty. The workforce multiplier is the thing being built.

---

## 3. The self-validation ladder (unchanged levels, one new meta-rule)

### 3.1 Levels — carried from v1.0 with certificate vocabulary adopted

| Level | Unlocked by | Evidence class | The self-referential act | Skills |
|---|---|---|---|---|
| SV-0 | today | CI logs, in-skill self-tests, codebaseqc self-audit | every perk already proves itself through the real executor | existing suite |
| SV-1 | P0 | governed conformance runs | the chip re-pins its own identity under canonical hashing | `cws-conform` |
| SV-2 | P1 | chained, signed ledger records | the ledger checker verifies the ledger of its own verification run | `cws-ledgercheck` |
| SV-3 | P2 | exod-attested runs, attested meters | the boundary proves itself by failing on purpose under its own observation | `cws-redteam`, `cws-bench` |
| SV-4 | P3 | dual-signed receipts; public transparency inclusion | the registry — **and now the engine** — publishes itself through a perk; the first approval approves the approval policy | `cws-release` |
| SV-5 | P4 | model-checked workflows, EMPIRICAL/SYMBOLIC/AXIOMATIC certificates | the remaining plan verifies as a workflow; **the money's lifecycle verifies before the money exists** | `cws-modelcheck` |
| SV-6 | P6 | settled, ledgered work | development enters its own economy; the plan's completion is a receipt the system issues to itself | `cws-settle-sim`, live bounties |

### 3.2 Meta-rules M1–M5 — carried verbatim from v1.0

Evidence escalation; retro-validation; external anchors (the circularity guard — Go verifiers, the kernel, Rekor, TLC/Apalache/TLAPS, the PSP); refusals are evidence; the gate is governed.

### 3.3 Meta-rule M6 — break-glass (new)

A self-hosting gate needs a repair path that does not depend on the thing being repaired. When the governed channel itself is the regression, a **signed override** is permitted: an `override` record, signed by the **offline deployment root key** (never an online service key), naming the incident id, the gates being bypassed, and the human invoking it. Constraints: exactly one override per incident id; the override is loudly flagged in every ledger view; and the **next healthy pipeline run must retro-verify the override** — re-running every gate it skipped — or the chain is marked `unhealed` and stays so until it does. Two-human rule the day there are two humans. The ouroboros gets an emergency exit from its own mouth, and even the exit leaves a chained, signed, retro-verified trail.

---

## 4. Validation-criteria taxonomy (three new classes)

| Class | Meaning | Verdict source |
|---|---|---|
| V-AUTO | deterministic automated check, CI-gated | exit code |
| V-PROP | property-based / randomized, stated trial counts | Hypothesis / fuzz harness |
| V-RED | adversarial exercise against a maintained corpus | expected-refusal contracts |
| V-BENCH | performance threshold on the pinned reference env (2 vCPU / 4 GB, Ubuntu 24.04, kernel ≥6.8) | metrics vs budget |
| V-EXT | verified by an external anchor (meta-rule M3) | cross-impl / public log / kernel / PSP |
| V-GOV | must execute through the governed channel; evidence is the record or receipt | the ladder |
| **V-MUT** | mutation-tested enforcement: delete/invert the check → CI must fail | mutation harness over the enforcement surface |
| **V-CHAOS** | fault injection: partition, crash, kill mid-write; recovery invariants asserted | chaos harness |
| **V-LIVE** | liveness: the system, or a stuck state, must make progress within a bound | timers + model-checked ◇-properties |

**R3 — the enforcement surface (V-MUT applies to all of it, ≥90% mutation score each):** `authorize_step`, `result_acceptable`, the tamper check, the in-channel oversight gate, per-step snippet verification, grant verification (sig/nbf/exp/nonce), the approval check, the revocation check, the settlement gate, the chain verifier, the concordance check. A gate that survives its own deletion was never a gate.

---

## 5. Technology composition register (T01–T23 carried; T24–T29 new)

v1.0 rows T01–T23 carry unchanged: JCS (T01) · Ed25519/pyca (T02) · DSSE (T03) · Go second impl (T04) · JSON Schema (T05) · POSIX ledger primitives (T06) · Hypothesis (T07) · Caddy/nginx TLS edge (T08) · bubblewrap+seccomp+cgroup2+Landlock (T09) · gVisor/Firecracker (T10) · mTLS+SPIFFE SANs (T11) · age/sops vault (T12) · Sigstore/cosign (T13) · Rekor (T14) · revocation feed→TUF (T15) · WebAuthn (T16) · TLC+Apalache (T17) · sqlite→Postgres (T18) · OpenTelemetry (T19) · stdlib decimal (T20) · Stripe (T21) · Circle ROADMAP (T22) · supply-chain gates (T23). Rules R1 (everything pinned in `deps.lock.json`) and R2 (every adapter ships a second implementation) carry; R3 added above.

| ID | Domain | Composed technology | Role | Swap interface | Phase |
|---|---|---|---|---|---|
| **T24** | Substrate analysis (the ancestor) | **alembic** (pinned commit): 6-language extractors → AtomTree → L++; conservation walker; per-function contracts | publish-gate extraction + conservation + **blueprint concordance** | the `alchemy` skill (perks `extract` / `conserve` / `concord`); file-mode adapter — **no warehouse dependency on the chip path** | P3 |
| **T25** | Shape naming | **putrefactio** (pinned commit + pinned `laws/` rules): closed-enum classifier, `{shape_id, kind ∈ known\|unnamed}` | allowlist oversight (Decision 16 inverted into security) | `alchemy/classify` perk | P3 |
| **T26** | Axiomatic proof | **tlapm / TLAPS** ≥1.6.0-pre (the patched arm64 build; patches tracked upstream) | AXIOMATIC certificate class beside TLC (EMPIRICAL) and Apalache (SYMBOLIC) | `composer` emits; checker is a process; Mode-3 THEOREM-emission fix = named work item P4-W1 | P4 |
| **T27** | Time authority | chrony + **NTS**-secured NTP (ops requirement); **RFC 3161 TSA** countersignatures (pluggable TSA; Roughtime ROADMAP) | secured wall-clock; third-party time anchors on high-value receipts and dispute windows | `Timestamper` adapter | P0 ops, P3 |
| **T28** | Engine attestation | reproducible builds: `FROM@sha256` digests, `SOURCE_DATE_EPOCH`, `pip --require-hashes`, diffoscope CI; **SLSA provenance** as in-toto/DSSE; StageX/Nix ROADMAP | the verifier verified: signed engine releases; govd↔exod mutual attestation | `cws-release/engine` perk; pinned release policy | P0, P3 |
| **T29** | Key custody | file keys 0400 baseline; **PKCS#11 seam** for service keys (TPM2/HSM later); offline root on hardware token | M2's custody answer behind one interface | `KeyStore` adapter (file + PKCS#11 stub per R2) | P0, P3 |

---

## 6. Findings recap (delta only)

F1–F8, F10–F12 dispositions carry from v1.0. **F9 is re-dispositioned**: closed not by containment alone (P2) but by the lineage — shape-allowlist oversight (T25) replaces enumerate-badness with name-the-known; regex formally demoted to lint. The grill's own findings M1–M14 are dispositioned in §0 and folded below.

---

## 7. Phase 0 — Protocol extraction (weeks 0–4) · exits at SV-1

**Objective.** "cyberware" becomes a spec the repo implements — and v1.1 widens the spec set: keys, privacy, time, and in-flight semantics are protocol, not afterthought. **Composes:** T01–T05, T23, T27–T29.

**Build (v1.0 items carried):** `spec/cwp-core.md`; JSON Schemas; `infra/cwp/canonical.py` + `sign.py`; the one-commit digest cutover; `spec/lpp-semantics.md`; ≥250 golden vectors; the Go verifier; truth-in-labeling pass; `deps.lock.json` + SBOM + osv gates.

**Build (new in v1.1):**
`spec/keys.md` — the key hierarchy: offline **deployment root** (hardware token; signs overrides, key rotations, release policy) → online service keys (`govd-grant`, `exod-receipt`, `settle-ledger`, `feed-sign`) → per-store HMAC keys; every DSSE header carries a key-id; **rotation** with overlap windows and cross-signed `key_rotation` ledger records; **compromise runbook**: feed-revoke the key with `compromised_at`, everything signed after that instant is invalid, re-attestation procedure; **bootstrap**: agents learn govd's key by deployment-config pinning (distributed like SSH known_hosts); TOFU explicitly rejected for priced/destructive operations, permitted with a warning for read-only discovery.
`spec/privacy.md` — data classes (task content: never crosses, unchanged; identity metadata; value metadata — *metadata is data*); **crypto-shredding**: subject-scoped DEKs encrypt personal fields inside ledger records, the chain hashes ciphertext, erasure = DEK destruction with the chain intact; hash-only references for bulky payloads; retention tiers; `/rep` gated to counterparties, public views aggregate-only; FMV publication keeps its k-floor (≥8 distinct initiators) as a privacy property, not just an anti-gaming rule.
`spec/time.md` — NTS-secured NTP as an operational requirement; monotonic clocks mandatory for nonce caches and TTLs; ledger timestamps are claims unless TSA-countersigned; TSA anchors required above a value threshold and on dispute-window boundaries.
`spec/inflight.md` — **the five decided sentences** (M9): (1) revocation mid-run halts at the next step boundary — the running step completes atomically, subsequent `step_request`s refuse `revoked`; `severity: critical` instead kills the sandbox immediately. (2) Initiator cancel is a lifecycle transition, legal until DELIVERED: completed steps' metered + pass-through costs and the govd fee settle; the remainder refunds. (3) Metered escrow funds the **cap**; surplus auto-releases at settlement; estimate-plus-top-up is ROADMAP. (4) A chain verifies under its genesis schema major; verifiers support N and N−1; migration is a new chain with a cross-reference record — never an in-place rewrite. (5) WS sessions resume by `(run_id, token)`; grants replay idempotently; `step_result` is idempotent by `(run_id, step)`.
Reproducible-build baseline (T28): digest-pinned base image, `SOURCE_DATE_EPOCH`, hash-pinned pip; diffoscope job proving two independent builders produce one digest.

**Self-validation (SV-1).** Carried: `cws-conform` governed runs; the chip re-pins its own identity under JCS, the transition itself recorded.

**Validation criteria.** P0-V01…V09 carried verbatim from v1.0 (cross-language vectors; JCS corpus; single-digest-path lint; schema validation; DSSE↔cosign interop; governed conformance; chip re-pin; truth-labeling lint; supply-chain gates). New:

| ID | Class | Criterion | Method / threshold |
|---|---|---|---|
| P0-V10 | V-AUTO | the four new specs exist, render standalone, and every normative MUST in them maps to a criterion ID somewhere in this plan | doc-lint (same engine as truth-labeling) |
| P0-V11 | V-EXT | reproducible engine build: CI and an independent builder produce byte-identical image digests; diffoscope empty | dual-builder job |
| P0-V12 | V-AUTO | `KeyStore` seam real per R2: file backend and PKCS#11 stub pass one contract suite | adapter matrix |
| P0-V13 | V-AUTO | every DSSE in the vector corpus carries a resolvable key-id; an unknown key-id fails closed | vector additions |

---

## 8. Phase 1 — Integrity hardening (weeks 2–8) · exits at SV-2

**Build (carried):** Ledger v2 — append-only JSONL, `seq` + full-sha256 `prev`, genesis binds `{run_id, plan_sha}`, HMAC locally / Ed25519-DSSE for govd, `O_APPEND`+`fsync`+`flock`, atomic snapshot replace, torn-tail truncation recorded; `cyberware ledger verify` + the Go chain-checker; per-step snippet verification at the instant of execution; plan as the sole source of step truth (`--list` deleted); bearer-token principals, TLS 1.3 edge, rate limits.

**Build (new):** **Merkle checkpoints** in Ledger v2 generically (M7, but run ledgers benefit too): every N entries or T minutes, a `checkpoint` record commits the chain head and a Merkle root over derived state (for reward ledgers: account balances), signed by the writer key — verifiers start from the last checkpoint, auditors can still walk the whole chain. **Crypto-shredding fields** per `spec/privacy.md`: personal fields stored as subject-DEK ciphertext; the chain hashes ciphertext, so erasure never breaks verification.

**Validation criteria.** P1-V01…V10 carried verbatim (16×5,000 concurrency; 500 kill-9 crash loop; single-bit tamper detection; Go cold re-verification; post-bless snippet mutation; no out-of-grant execution; 401/429 behavior; full digests; governed evidence; genesis non-transplant). New:

| ID | Class | Criterion | Method / threshold |
|---|---|---|---|
| P1-V11 | V-AUTO | checkpoint verification: cold-verify a 1M-entry chain from the last checkpoint in ≤2 s on the reference env; full-walk audit still reproduces the same head | checkpoint harness |
| P1-V12 | V-AUTO | a forged checkpoint (balance root off by one entry) is detected by the next full audit and by any verifier holding the prior checkpoint | negative test |
| P1-V13 | V-AUTO | **erasure drill**: destroy a subject DEK → chain still verifies end-to-end; subject fields unrecoverable; non-subject queries unaffected | drill in CI |
| P1-V14 | V-MUT | the chain verifier and the per-step snippet check survive the R3 mutation harness at ≥90% | mutation gate |

---

## 9. Phase 2 — exod, the privilege boundary (weeks 6–16) · exits at SV-3

**Build (carried in full from v1.0):** signed grants (±60 s skew, nonce cache on monotonic clock per `spec/time.md`, reserved `quote_sha`); exod as a separate principal — UDS/`SO_PEERCRED` locally, mTLS/SPIFFE remotely; per-step grant + digest verification; `SandboxProfile` driver over bwrap (core/verified) and gVisor/Firecracker (community); capability manifests materialized (binds, egress-allowlist netns, seccomp, cgroup-v2, Landlock); `Vault.get()` over sops/age with env-stub seam; secrets injected step-side only, `*_FILE` deprecated; exod-attested status and proto-receipts with attested meters; `[UNGOVERNED-BOUNDARY]` banner on the legacy path.

**The spine note (M10).** The minimal P2 for the critical path is: grants + exod + the bwrap core profile + the file vault. The community tier (microVM), warm pools, and the second sandbox backend are full-P2 items that the spine defers without blocking SV-3 — the MVP demo is *attested, sandboxed, governed execution with proto-receipts*, and the core profile delivers it.

**Validation criteria.** P2-V01…V10 carried verbatim (the ≥12-behavior corpus across tiers; kernel-enforced refusal with the software scan disabled; zero secret bytes agent-side; replay/expiry/skew; mid-run digest swap; forged-status rejection; overhead budgets; community no-secrets; governed red-team/bench receipts; dual-backend matrix). New:

| ID | Class | Criterion | Method / threshold |
|---|---|---|---|
| P2-V11 | V-CHAOS | partition govd↔exod mid-step: the running step completes, the next `step_request` fails closed, WS resume per `spec/inflight.md` replays the last grant idempotently, zero duplicate ledger records | partition harness |
| P2-V12 | V-CHAOS | kill exod mid-sandbox: the orphaned sandbox is reaped (cgroup kill), the step records `error`, the run is resumable from the recorded state | crash harness |
| P2-V13 | V-MUT | grant verification (sig, nbf/exp, nonce) and `authorize_step`/`result_acceptable` survive the R3 harness at ≥90% | mutation gate |
| P2-V14 | V-AUTO | clock-skew injection ±5 min: grants and nonce caches behave exactly per `spec/time.md` (monotonic TTLs unaffected; wall-clock checks fail closed) | skew harness |

---

## 10. Phase 3 — Marketplace trust on proven rails (weeks 12–24) · exits at SV-4

**Build (carried):** cosign signing over `skill_sha` + chip manifest, Sigstore TUF root pinned; Rekor inclusion proofs per release; the Ed25519 revocation feed (`seq` monotonic, `expires` freshness, max-age 15 min); tier wiring; publish-time lint; WebAuthn approval (challenge = sha256(JCS(approval doc))), `--approve` removed; dual-signed receipts with in-toto export.

**Build (new in v1.1):**
**Engine attestation lands (M1, T28).** `cws-release` gains the `engine` perk: the reproducible engine build is signed and Rekor-logged with SLSA provenance exactly like a chip release; `/health` attests the running engine digest beside `chip_sha`; **govd↔exod handshake exchanges release attestations** and refuses `engine_unattested` on mismatch with pinned release policy. The verifier is now inside its own verification perimeter.
**Key lifecycle drills (M2, T29).** Service keys live behind the `KeyStore` seam; the **rotation drill** runs as a governed workflow: rotate `govd-grant` with an overlap window, cross-signed `key_rotation` record, in-flight grants honored to `exp`, old key feed-revoked after the window. The compromise runbook is rehearsed, not just written.
**Time anchors (M8, T27).** Receipts above the value threshold, and every dispute-window boundary, are TSA-countersigned; the `Timestamper` adapter ships with two backends per R2.
**The citrinitas publish gate (T24/T25) — the ancestor at work.** Verified-tier admission now requires, per snippet core: `alchemy/extract` (the snippet's actual L++), `alchemy/conserve` (zero unexplained conservation defects; waivers only via an approval artifact, on the record), `alchemy/classify` (**all shapes `kind: known`** — an `unnamed` shape routes to review, where naming it grows the closed enum, or to community-tier containment), and **`alchemy/concord`** — the extracted CFG structurally contained in the declared blueprint. A passing skill carries the **citrinitas-clean badge** in its catalog entry. Community tier may carry `unnamed` shapes and conservation waivers — containment compensates — but never skips concordance.
**Availability tiers for the feed (M3).** Grace policy per operation class: read-only verified skills may run on a stale-but-valid feed to grace-2 (default 24 h); destructive and priced operations fail closed at max-age. Signed feed mirrors documented.
**Revocation in flight (M9).** The decided sentence from `spec/inflight.md` is implemented and drilled: boundary-halt by default, `severity: critical` kills the sandbox.
**The doorbell (M12 residue).** `SECURITY.md`: a contact, a PGP/age key, an acknowledgment SLA. Nothing more — willingness has an address.

**Self-validation (SV-4).** Carried: the registry publishes itself via `cws-release`; the revocation drill's receipt records kill-switch latency; the first approval approves the approval policy. New: **the engine publishes itself** through the same perk — the release that introduces engine attestation is itself the first attested engine release.

**Validation criteria.** P3-V01…V10 carried verbatim (tri-layer unsigned refusal; offline Rekor proofs; revocation ≤ interval+5 s; stale-feed refusal; rollback refusal; approval mutation gate; offline approval verification; seeded lint corpus; governed release+drill receipts; in-toto consumability). New:

| ID | Class | Criterion | Method / threshold |
|---|---|---|---|
| P3-V11 | V-AUTO | mutual attestation: a 1-byte-tampered engine binary on either side fails the govd↔exod handshake with `engine_unattested`; `/health` digest matches the signed release | tamper test |
| P3-V12 | V-GOV | the engine release is produced by `cws-release/engine` through the channel; SLSA provenance verifies offline | SV-4 extension |
| P3-V13 | V-GOV | key-rotation drill completes as a governed workflow: overlap honored, cross-signed record present, a grant signed by the old key **after** its revocation refuses | rotation drill receipt |
| P3-V14 | V-AUTO | TSA countersignature verifies offline against the TSA's chain for every above-threshold receipt; absence blocks settlement eligibility later | timestamp check |
| P3-V15 | V-AUTO | citrinitas gate: a seeded conservation defect, a seeded `unnamed` shape, and a seeded blueprint/CFG mismatch each block verified-tier publish with the correct named reason | seeded-defect triple |
| P3-V16 | V-AUTO | **concordance**: 100% of core+verified chip skills pass `alchemy/concord`; the diff artifact is stored with the release | chip-wide run |
| P3-V17 | V-LIVE | feed-outage drill: read-only verified runs proceed to grace-2; a destructive claim refuses; recovery re-converges with no manual ledger surgery | outage harness |
| P3-V18 | V-MUT | the revocation check and the concordance check survive the R3 harness at ≥90% | mutation gate |

---

## 11. Phase 4 — L++, the workflow algebra, and three certificate classes (weeks 16–28) · exits at SV-5

**Build (carried):** week-one invariants-to-TLC commit (auxiliary flags + `INVARIANT` clauses); `on_fail: {to | retry(n) | compensate(action)}` as modeled transitions; the `seq/par/choice/saga` workflow algebra over the Phase 0 semantics; bounded-counter product automata (finite abstraction / enforced refinement); `workflow_sha`; the ≥6-defect known-bad corpus; emitter mutation testing.

**Build (new):**
**Three certificate classes, the ancestor's vocabulary adopted (T17+T26):** **EMPIRICAL** (TLC), **SYMBOLIC** (Apalache), **AXIOMATIC** (TLAPS), with honest `Unproved` recorded where proofs don't close. Named work item **P4-W1**: the Mode-3 fix — the known single fix point in `hyper_tla::generate_tla` THEOREM emission (all 77 unproved obligations at the lineage's first smoke classified as non-inductive proof skeleton) — so safety invariants earn AXIOMATIC stamps where provable.
**The money is model-checked before it exists (M4).** `infra/document/settlement.blueprint.json` encodes the full §-11.5 lifecycle of v1.0 *plus* the v1.1 transitions (CANCELLED; escrow-expiry auto-refund): safety invariants — escrow empties at every terminal, no settlement without the dual-signature flag, no double-settle; liveness — ◇terminal under fairness, with the expiry timer as the progress guarantee. Checked EMPIRICAL + SYMBOLIC now, AXIOMATIC where P4-W1 allows. Phase 6a then implements this blueprint *verbatim*, and `cws-modelcheck` gates any change to settlement code paths whose blueprint changed.

**Self-validation (SV-5).** Carried: `plan.workflow.json` — the remainder of this plan — verifies deadlock-free through `cws-modelcheck`. Extended: the settlement blueprint's verification receipt is SV-5 evidence that SV-6's substrate is sound.

**Validation criteria.** P4-V01…V07 carried verbatim (mutant invariants caught; 6/6 corpus by TLC, ≥5/6 Apalache; dual-checker agreement protocol; emitter mutation ≥90%; state/wall budgets; saga compensation in model *and* execution; the plan-as-workflow gate). New:

| ID | Class | Criterion | Method / threshold |
|---|---|---|---|
| P4-V08 | V-AUTO | the settlement blueprint passes EMPIRICAL + SYMBOLIC: conservation safety holds; ◇terminal liveness holds under fairness including the expiry timer | dual-checker gate |
| P4-V09 | V-AUTO | seeded money-mutants (remove the expiry timer; allow settle-before-validate; permit double-settle) each fail the checker | mutant triple |
| P4-V10 | V-AUTO | P4-W1 verified: post-fix, the pipeline and settlement blueprints' safety invariants carry AXIOMATIC stamps or an honest `Unproved` classification with mode recorded | TLAPS run record |
| P4-V11 | V-EXT | TLAPS verdicts reproduce on a second machine/arch from the pinned tlapm build | cross-arch anchor |

---

## 12. Phase 5 — Service-grade govd (weeks 16–28, parallel) · sustains SV-4

**Build (carried):** `Store` behind an interface (sqlite-WAL → psycopg/Postgres-15), JSONL as the artifact of record with a continuous reconciler; SSE; org → principals → policy → quotas tenancy; SPIFFE identities; OTel `traceparent` across planes; in-toto provenance export.

**Build (new — M3's availability answer):** **HA design point**: active-passive govd over shared Postgres, single-writer guaranteed by a Postgres advisory-lock lease (split-brain prevented by construction); WS re-establishment per `spec/inflight.md` (resume by `(run_id, token)`, idempotent grant replay); planned-maintenance mode pre-issues short-TTL grants so in-flight work survives a failover window; signed feed mirrors served from the standby.

**Validation criteria.** P5-V01…V06 carried verbatim (soak RSS/latency budgets; reconciler zero-divergence + injected-fault alarm; org isolation matrix; full cross-plane trace; dual Store adapters; governed soak receipt). New:

| ID | Class | Criterion | Method / threshold |
|---|---|---|---|
| P5-V07 | V-CHAOS | failover drill: kill the active govd mid-run-stream; the standby acquires the lease, WS sessions resume, zero duplicate grants, zero lost `step_result`s | failover harness |
| P5-V08 | V-LIVE | no orphaned run: every run interrupted by failover reaches a terminal or resumable state within the lease TTL + 30 s | drill assertion |
| P5-V09 | V-AUTO | split-brain negative test: a second writer cannot append while the lease is held; the attempt is itself recorded | lease test |

---

## 13. Phase 6 — Projection: the settlement plane (weeks 20–36) · exits at SV-6

*The alchemical sequence supplies the name: projection — the stage where the stone touches base material. The governing rule was stated in §1 and is repeated here because this is the section it governs: no chrysopoeia by decree. Gold only by transmutation of validated work — never minted, only earned, and always, to the last grain, accounted.*

**Design carried in full** from v1.0 §11 / v1.0-doc §12: actors and accounts; the priced contract (`fixed | metered | bounty | auction`); per-contract intelligence (`llm/*` perks, attested token meters, schema-validated output as the payment gate — *the meter measures effort; the contract decides whether effort was work*); the quote → escrow → grant → deliver → validate → settle lifecycle; the chained double-entry reward ledger; the versioned signed split policy; FMV as trimmed volume-weighted medians with admission rules; derived reputation; the gaming threat table; CWC as a claim on adapters, never a token; Stripe Connect as the licensed-PSP strategy; sub-phases 6a–6d; the dogfood-economy cold start.

**Build (new in v1.1):**
**The lifecycle is now the verified blueprint (M4).** 6a implements `settlement.blueprint.json` *verbatim* — including the two v1.1 transitions: **CANCELLED** (initiator cancel until DELIVERED, per `spec/inflight.md`: completed steps' metered + pass-through costs and the govd fee settle, remainder refunds) and **escrow expiry** (every escrow carries `expires_at`; expiry without settlement auto-refunds — the V-LIVE guarantee that money cannot get stuck, model-checked in P4 before a single credit exists).
**Microstructure, the conceded half of M13.** Adapter-boundary **rounding rule** (banker's rounding at currency-scale conversion, CWC scale-4 ↔ integer cents) and the **dust account**: residue posts to `dust:adapter:<id>` inside the same balanced entry, swept to treasury by a signed monthly record. Conservation includes dust — the axiom's money face does not leak pennies at the FX boundary. *And nothing more*: tick size is substrate; everything above it is §15's territory.
**Scale and exactness (M7).** Reward-ledger checkpoints (P1 machinery) every 10k entries or 5 min, committing chain head + Merkle balance root; single-writer-per-currency with **group-commit batching**; **idempotency keys** on every adapter event (Stripe event-id; duplicate webhook delivery is a first-class test, because a double-applied settlement is a conservation violation wearing a race's clothes). TPS budget on the reference env: ≥200 settlements/s sustained, p95 settle latency ≤250 ms — initial numbers, revisable on the record.
**Privacy at the value layer (M5).** `/rep/<principal>` gated to authenticated counterparties; public reputation views aggregate-only; FMV's k-floor (≥8 distinct initiators) holds as a privacy property; subject-DEK fields in reward records inherit P1 crypto-shredding, so erasure rights coexist with an intact chain.
**The ancestor earns (M11's closing move).** `alchemy/extract`, `/conserve`, `/classify`, `/concord` are published as **priced analysis perks** — the parent toolchain earns royalties validating the descendant's marketplace. Every verified-tier publish pays the lineage.
**The first external program (M12's roadmap residue).** cyberware's security bounty runs *through its own settlement plane*: vulnerabilities are bounty tasks, disclosure is the validated deliverable, payment flows through the reward ledger — adversarial dogfooding, the economy's first outside users being the people paid to break it.

**Self-validation (SV-6).** Carried and now sharpened: `cws-settle-sim` storms; development milestones close as internal-credit bounties; the first FMV index ever published prices cyberware's own remaining tasks; the plan's completion is a settled, dual-signed, TSA-anchored workflow receipt, reconciled against the PSP sandbox — the birth certificate, externally time-stamped.

**Validation criteria.** P6-V01…V11 carried verbatim from v1.0 (10k-settlement zero-sum storms; dual-signature/validation mutation gate; float ban; provider-receipt meter exactness; schema-fail refund split; ≤2% index drift at 20% adversarial volume; bounty/auction clearing; dispute E2E with clawback; PSP reconciliation to 0.0001 CWC; third-party reproducibility of FMV and reputation; ≥10 settled development milestones). New:

| ID | Class | Criterion | Method / threshold |
|---|---|---|---|
| P6-V12 | V-LIVE | escrow expiry: a funded escrow whose run stalls auto-refunds at `expires_at` ± one sweep interval; zero escrow older than the bound exists at any audit | expiry sweep audit |
| P6-V13 | V-AUTO | the implemented lifecycle is bisimilar to `settlement.blueprint.json`: every state transition in 6a code maps to a blueprint transition; a seeded extra transition fails the concordance check | blueprint↔code concordance (the ancestor's trick, applied to the money) |
| P6-V14 | V-AUTO | CANCELLED semantics exact per `spec/inflight.md`: completed-step costs + govd fee settle, remainder refunds, postings balance | cancel matrix |
| P6-V15 | V-PROP | duplicate-delivery storm: every adapter event replayed 2–10×; final balances identical to single-delivery; idempotency violations = 0 across 10k events | webhook chaos |
| P6-V16 | V-AUTO | dust conservation: across 100k randomized FX-boundary settlements, global zero-sum holds *including* `dust:` accounts; monthly sweep is a balanced signed record | dust audit |
| P6-V17 | V-BENCH | ≥200 settlements/s sustained for 10 min on the reference env with group commit; p95 ≤250 ms; checkpoint-resume verification ≤2 s at 1M entries | settle bench receipt |
| P6-V18 | V-CHAOS | kill the settle engine mid-posting-set: the set is all-or-nothing (group write + single fsync); recovery replays exactly once; conservation holds | crash harness |
| P6-V19 | V-AUTO | `/rep` privacy: unauthenticated and non-counterparty requests receive aggregates only; per-principal detail requires a counterparty relationship on the ledger | access matrix |
| P6-V20 | V-GOV | the ancestor's perks settle: ≥1 real verified-tier publish pays `alchemy/*` royalties through the reward ledger | lineage receipt |
| P6-V21 | V-MUT | the settlement gate and the idempotency check survive the R3 harness at ≥90% | mutation gate |

---

## 14. The spine, denominated promises, and the timeline

**Staffing model, stated (M10's honest half).** One human plus governed agents — and the model converges with the product: SV-2 makes CI a governed run, SV-3 makes validation attested, SV-6 makes development itself a settled bounty. The workforce multiplier is the thing being built, and each rung transfers more construction into the channel.

**The spine (internal load-bearing wall).** The critical path that must never slip: **P0 → P1 → P2-minimal (grants + exod + bwrap core profile + file vault) → P3-minimal (signing + revocation feed + engine attestation) → 6a-internal (accounting core on internal credits).** Everything else — microVM tier, warm pools, market modes, HA, payout rails — is real but deferrable. **MVP = SV-3**: attested, sandboxed, governed execution with proto-receipts; the first externally credible demo, reachable on the spine alone.

**Denominated promises (external layer).** Every public claim is denominated in a rung and a date and redeemed by a receipt:

| Promise (outward) | Rung | Redeemed by |
|---|---|---|
| "Agents execute only attested, sandboxed, hash-pinned pathways" | SV-3 | red-team + bench receipts |
| "The registry — and the engine — publish and revoke themselves, on a public log" | SV-4 | release + drill receipts, Rekor proofs |
| "Workflows and the money's own lifecycle are model-checked before they run" | SV-5 | checker certificates (EMPIRICAL/SYMBOLIC/AXIOMATIC) |
| "Validated work settles; intelligence is priced per contract; the system paid for its own completion" | SV-6 | the birth-certificate receipt |

**Timeline (bars carried from v1.0; spine marked ▸):**

```
wk:    0    4    8    12   16   20   24   28   32   36
P0   ▸ ████████                                          → SV-1
P1   ▸     ████████████                                  → SV-2
P2   ▸             ████████████████   (spine = minimal)  → SV-3  ← MVP
P3   ▸                     ████████████████████ (spine = min) → SV-4
P4                                 ████████████████      → SV-5
P5                                 ████████████████      sustains SV-4
P6   ▸                                 ██████████████████ (spine = 6a-internal) → SV-6
```

Dependency laws carried: P6 ⇐ P1+P2+P3 (money rides on nothing rewritable, self-reported, or anonymous); assurance is monotone across phases.

---

## 15. The out-of-scope register (exclusion as decision)

| Excluded | Doctrine that excludes it | What remains in scope |
|---|---|---|
| Legal programs, marketplace terms, liability allocation, tax structuring | **willingness rather than possibility** — every run is already evidence; disclosure and compliance become choices the operator exercises, cheaply, when jurisdiction and counsel require | one `SECURITY.md` doorbell; receipts and ledgers as the raw material any future program queries; the 6d self-bounty as the first willing act |
| Credit terms, interest, float policy, listing standards, price formation, monetary policy | **substrate, not economy** — we are not the Fed, the SEC, NYSE, or the Shanghai Exchange; the market settles these lines on top of us | tick size, rounding, dust, conservation, settlement finality, idempotency — the microstructure that must sum to zero |
| The intelligence itself: agent architecture, alignment, at-rest hygiene of the agent's own machine | **principal-key agnosticism** — human, model, committee, or dog; the platform authenticates keys and validates work | one non-normative sentence in the spec: agents SHOULD encrypt task-ledgers at rest; the WebAuthn exception: consent to destruction is always human |

---

## 16. Risk register (delta from v1.0)

| Risk | L | I | Mitigation | Where |
|---|---|---|---|---|
| Service-key compromise | M | C | key hierarchy + rotation drills + feed revocation of keys + offline root | P0 spec, P3 drill |
| Engine supply-chain tamper | M | C | reproducible builds + mutual attestation + SLSA provenance | T28, P3-V11/12 |
| Stuck value (liveness failure) | M | H | escrow expiry, model-checked ◇terminal, failover drills | P4-V08, P6-V12, P5-V07 |
| Erasure demand vs immutable chain | M | H | crypto-shredding by design; chain hashes ciphertext | P0 spec, P1-V13 |
| Time-authority failure / skew attack | M | M | NTS ops requirement; monotonic TTLs; TSA anchors on value | T27, P2-V14, P3-V14 |
| Ancestor pinning drift (alembic/putrefactio/tlapm evolve) | M | M | T24–T26 pinned commits + `laws/` pinned; cartridge seams; quarterly pin review | §5, T23 |
| Break-glass abuse | L | H | offline-root-only signing, one per incident, mandatory retro-verification, `unhealed` flag | §3.3 |
| Two-program scope on one maintainer | H | H | composition-as-subtraction (organs become imports); the spine; the converging workforce model | §2, §14 |
| (carried) regulatory, cold-start, oracle gaming, FX adapter risk | — | — | unchanged from v1.0: PSP custody, dogfood economy, admission rules, adapter seams | v1.0 §14 |

---

## Appendix A — The validation skill set (v1.1 roster)

Carried: `cws-conform` · `cws-ledgercheck` · `cws-redteam` · `cws-bench` · `cws-release` (now + `engine` perk) · `cws-modelcheck` (now emits EMPIRICAL/SYMBOLIC/AXIOMATIC certificates) · `cws-settle-sim`. New:

| Skill | Perks | Core contract checks | First used |
|---|---|---|---|
| **`alchemy`** (the repatriated ancestor; wraps pinned alembic + putrefactio in file-mode) | `extract` · `conserve` · `classify` · `concord` | extract: L++ JSON emitted per snippet core; conserve: `json: {unexplained_defects: 0}` or waiver ref; classify: `json: {unnamed: 0}` for verified tier; concord: empty containment diff, artifact stored | P3 (SV-4) |
| **`cws-mutate`** | one perk per R3 enforcement-surface entry | `json: {mutation_score: ≥0.90}` per gate; survivors listed by mutant id | P1 onward |
| **`cws-chaos`** | `partition` · `crash-exod` · `crash-settle` · `failover` · `skew` | each scenario's recovery invariant asserted per its `spec/inflight.md` sentence; refusals recorded as evidence (meta-rule M4) | P2 onward |

All three are ordinary chip skills — pinned in the manifest, signed from P3, inside the tamper-evidence perimeter they enforce. The `alchemy` skill is the lineage made load-bearing: the parent submits to the child's authenticity discipline, then earns inside its economy (P6-V20).

## Appendix B — Worked example: a publish through the citrinitas gate

A publisher submits `pg_ops` v2 to the verified tier. `cws-release` runs the gauntlet through the channel: `alchemy/extract` lifts each snippet core to L++; `alchemy/conserve` walks acquires/releases — one defect surfaces (an unreleased file handle on an error path), the publisher fixes it, re-extract is clean; `alchemy/classify` names every shape `known` except one novel retry idiom — review names it, the closed enum grows by one (Decision 16, performed as a marketplace act); `alchemy/concord` confirms the extracted CFG is contained in the declared blueprint — the code agrees with its claim; then index → cosign → Rekor → manifest, each step contract-checked, the whole release one dual-signed receipt carrying the **citrinitas-clean badge**. From 6b onward, the same gauntlet posts `alchemy/*` royalties to the lineage's account. What admitted the skill was never anyone's word — not even the publisher's blueprint — but the agreement of the code with its claim, the balance of its acquires with its releases, and the namedness of its every shape.

---

*Closing note.* v1.0 ended with three clauses: wherever the system trusts, give it a verifier; wherever value flows, give it a receipt; wherever the system grows, let the grown part prove the growth. v1.1 adds the two that review and lineage earned: **wherever the system excludes, record the doctrine that excludes** — and **wherever a wheel exists, compose it, beginning with your own ancestor's.** One axiom, three faces; one program, two arcs — descending into code, ascending into action and value; and at projection, the standing rule: nothing gold by decree, everything gold by work, and every grain accounted.
