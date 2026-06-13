# cyberware swarm — milestone roadmap

**Seven checkpoints, derived from the task DAG.** Each milestone is a ladder rung with a *gate* (the task whose completion closes it), an outward *denominated promise* (a claim the ladder blesses and a receipt redeems), a *demo* a skeptic can verify, and the *evidence* that closes it. Milestones on the **spine** are load-bearing — they must not slip; the one *compounding* milestone (M5) adds assurance but is not on the critical path to the MVP or to settlement.

> **The MVP is M3 (SV-3)** — attested, sandboxed, governed execution. It is the first externally credible demo, reachable on the spine alone, and every promise after it compounds on a real boundary rather than a hopeful one.

> **The governing rule of the whole roadmap:** a milestone is *redeemed*, not *asserted* — its promise is denominated in a verifiable artifact (a receipt, a proof, a public-log inclusion). Promise outward; redeem with evidence.

## At a glance

| Milestone | Rung | Path | Gate task(s) | New tasks | Promise (one line) |
|---|---|---|---|---|---|
| M0 | - | **spine** | `P6-T05` | +15 | Internal only |
| M1 | SV-1 | **spine** | `P0-T18` | +5 | cyberware is a specification, not a codebase |
| M2 | SV-2 | **spine** | `P1-T09, P1-T10` | +6 | Every record of what happened is chained, signed, and independently re |
| M3 ◀ **MVP** | SV-3 | **spine** | `P2-T08, P2-T09` | +7 | Agents execute only attested, sandboxed, hash-pinned pathways; the pri |
| M4 | SV-4 | **spine** | `P3-T09, P3-T15` | +7 | Skills and the engine are signed, publicly logged, and revocable netwo |
| M5 | SV-5 | compounding | `P4-T09` | +8 | Composed workflows |
| M6 | SV-6 | **spine** | `P6-T21` | +21 | Validated work settles; intelligence is priced per contract; value is  |

## M0 — The spine stands — governed execution end to end (internal)

**Rung** - · **spine (load-bearing)** · **gate** `P6-T05` · **15 tasks in this milestone's closure** (cumulative cone 15)

**Promise (outward).** Internal only: a task can be claimed, blessed, executed under attestation, and its outcome recorded — the load-bearing wall is up.

**Demo (what a skeptic verifies).** A single governed run: claim → grant → exod step → chained ledger record, no value, no market.

**Redeemed by.** the spine task set complete

*Gate `P6-T05` — Settlement engine = f(dual-signed receipt, signed split policy):*
```json
{
  "impossible_without_both_sigs_and_validation_pass": "mutant receipts (sig stripped / verdict flipped) rejected"
}
```

**Tasks newly required at this milestone:** `P0-T02`, `P0-T03`, `P0-T11`, `P1-T01`, `P1-T03`, `P1-T05`, `P2-T01`, `P2-T02`, `P2-T07`, `P3-T04`, `P3-T14`, `P6-T01`, `P6-T02`, `P6-T04`, `P6-T05`

## M1 — SV-1 — the protocol is real and portable

**Rung** SV-1 · **spine (load-bearing)** · **gate** `P0-T18` · **5 tasks in this milestone's closure** (cumulative cone 7)

**Promise (outward).** cyberware is a specification, not a codebase: every hash is canonical and reproduced byte-for-byte by an independent implementation.

**Demo (what a skeptic verifies).** The Go verifier reproduces 250+ golden vectors; the chip re-pins its own identity under canonical hashing.

**Redeemed by.** cws-conform governed run + the chip re-pin transition record

*Gate `P0-T18` — Chip re-pin under JCS (the SV-1 self-referential act):*
```json
{
  "skill_index_check": "green",
  "transition_commit": "links old chip_sha \u2192 new chip_sha"
}
```

**Tasks newly required at this milestone:** `P0-T04`, `P0-T07`, `P0-T08`, `P0-T17`, `P0-T18`

## M2 — SV-2 — evidence becomes tamper-evident

**Rung** SV-2 · **spine (load-bearing)** · **gate** `P1-T09, P1-T10` · **6 tasks in this milestone's closure** (cumulative cone 8)

**Promise (outward).** Every record of what happened is chained, signed, and independently re-verifiable — history cannot be rewritten.

**Demo (what a skeptic verifies).** 16 concurrent writers + 500 crash injections survive with a single verified chain; a one-byte flip is caught and named.

**Redeemed by.** cws-ledgercheck torture+verify receipts; the Go chain-checker cold-verify

*Gate `P1-T09` — Author cws-ledgercheck skill (verify, torture perks):*
```json
{
  "governed": "torture + verify run through the channel; verify checks the ledger of its own verification run"
}
```
*Gate `P1-T10` — Author cws-mutate skill + wire R3 enforcement surface:*
```json
{
  "json": {
    "mutation_score": ">=0.90"
  },
  "covers": [
    "chain_verifier",
    "per_step_snippet_check"
  ]
}
```

**Tasks newly required at this milestone:** `P1-T01`, `P1-T02`, `P1-T04`, `P1-T05`, `P1-T09`, `P1-T10`

## M3 — SV-3 — execution becomes a kernel-enforced boundary  ◀ MVP

**Rung** SV-3 · **spine (load-bearing)** · **gate** `P2-T08, P2-T09` · **7 tasks in this milestone's closure** (cumulative cone 10)

**Promise (outward).** Agents execute only attested, sandboxed, hash-pinned pathways; the privilege boundary is enforced by the OS, not by software trust.

**Demo (what a skeptic verifies).** A 12-attack corpus refuses every case WITH the software scan disabled — the kernel is the counterparty; meters are attested.

**Redeemed by.** cws-redteam expected-refusal receipts + cws-bench attested-meter receipts

*Gate `P2-T08` — Author cws-redteam skill (≥12 attack perks, expect refusal):*
```json
{
  "corpus": ">=12 behaviors",
  "each_expect": {
    "exit": "nonzero"
  },
  "governed": "run under exod's own observation"
}
```
*Gate `P2-T09` — Author cws-bench skill (sandbox, channel overhead perks):*
```json
{
  "budgets": {
    "bwrap_p95_per_step_ms": "<=100",
    "microvm_cold_ms": "<=1500",
    "microvm_warm_ms": "<=250"
  }
}
```

**Tasks newly required at this milestone:** `P0-T11`, `P2-T01`, `P2-T02`, `P2-T03`, `P2-T07`, `P2-T08`, `P2-T09`

## M4 — SV-4 — the registry and the engine publish and revoke themselves

**Rung** SV-4 · **spine (load-bearing)** · **gate** `P3-T09, P3-T15` · **7 tasks in this milestone's closure** (cumulative cone 9)

**Promise (outward).** Skills and the engine are signed, publicly logged, and revocable network-wide in minutes; approval to destroy is cryptographically human; the code agrees with its declared blueprint.

**Demo (what a skeptic verifies).** The registry publishes itself through a perk; a revocation drill measures kill-switch latency; alchemy/concord proves CFG-vs-blueprint on the whole chip.

**Redeemed by.** dual-signed release receipts + Rekor inclusion proofs + the revocation drill receipt

*Gate `P3-T09` — Citrinitas publish gate wired into cws-release (verified tier):*
```json
{
  "seeded_triple_blocks": "a seeded conservation defect, an unnamed shape, and a blueprint/CFG mismatch each block verified publish with the named reason",
  "chip_wide_concord": "100% of core+verified skills pass alchemy/concord"
}
```
*Gate `P3-T15` — Author cws-release skill (index, sign, log, manifest, engine perks):*
```json
{
  "governed_release": "chip + engine release are dual-signed receipts via the channel",
  "rekor_proof_stored": true
}
```

**Tasks newly required at this milestone:** `P0-T13`, `P3-T01`, `P3-T02`, `P3-T05`, `P3-T08`, `P3-T09`, `P3-T15`

## M5 — SV-5 — workflows and the money's lifecycle are model-checked

**Rung** SV-5 · **compounding (off critical path)** · **gate** `P4-T09` · **8 tasks in this milestone's closure** (cumulative cone 8)

**Promise (outward).** Composed workflows — and the settlement lifecycle itself — are proven free of deadlock and conservation violation BEFORE they run, across three independent checkers.

**Demo (what a skeptic verifies).** The remaining plan, encoded as a workflow, verifies deadlock-free; settlement.blueprint.json passes EMPIRICAL+SYMBOLIC with seeded money-mutants caught.

**Redeemed by.** cws-modelcheck certificates (EMPIRICAL / SYMBOLIC / AXIOMATIC)

*Gate `P4-T09` — Encode plan.workflow.json — the plan verifies the plan (SV-5 act):*
```json
{
  "governed_run": "cws-modelcheck verdict",
  "plan_as_workflow": "deadlock-free"
}
```

**Tasks newly required at this milestone:** `P0-T06`, `P4-T01`, `P4-T02`, `P4-T03`, `P4-T04`, `P4-T05`, `P4-T08`, `P4-T09`

## M6 — SV-6 — the work pays for the work  (the ladder closes)

**Rung** SV-6 · **spine (load-bearing)** · **gate** `P6-T21` · **21 tasks in this milestone's closure** (cumulative cone 21)

**Promise (outward).** Validated work settles; intelligence is priced per contract; value is never minted, only earned — and the system paid for its own completion.

**Demo (what a skeptic verifies).** 10+ development milestones settle as internal-credit bounties; the first FMV index prices cyberware's own tasks; the plan's completion is a settled, TSA-anchored receipt reconciled against the PSP sandbox.

**Redeemed by.** the birth-certificate receipt — verified offline end to end

*Gate `P6-T21` — SV-6 capstone: development enters its own economy:*
```json
{
  "settled_milestones": ">=10",
  "plan_completion_receipt": "verifies offline end-to-end \u2014 THE LADDER CLOSES"
}
```

**Tasks newly required at this milestone:** `P0-T02`, `P0-T03`, `P0-T11`, `P1-T01`, `P1-T03`, `P1-T05`, `P2-T01`, `P2-T02`, `P2-T07`, `P3-T04`, `P3-T08`, `P3-T14`, `P6-T01`, `P6-T02`, `P6-T04`, `P6-T05`, `P6-T11`, `P6-T12`, `P6-T18`, `P6-T19`, `P6-T21`

## How to drive the swarm against these milestones

1. **Start at the roots.** Fifteen tasks have no dependencies (`_swarm_manifest.json` → `roots`); the largest cluster is P0's spec-writing group. Pull `P0-T12` (`spec/inflight.md`) first — its five decided sentences unblock P2/P3/P5/P6 design.
2. **Build each phase's validator early.** `validation_available_after` on every task names the validator-authoring task that must complete before the task's acceptance can be *checked*. A phase whose validator lands last cannot grade its own siblings.
3. **Hold the spine; defer the rest.** 24 tasks are on the spine (the wall to M6); everything else is real but slippable. The MVP (M3) needs only the spine through P2.
4. **Redeem, don't assert.** A milestone closes when its `redeemed_by` artifact exists and verifies — a receipt, a proof certificate, a Rekor inclusion. Promise the rung and the date; show the receipt.
5. **From M2 onward, building is running.** Every construction task's executor becomes the governed channel (meta-rule M5); its proof is one of the ten validation skills; by M6 its completion settles as a bounty. The swarm is the platform's first workload.

*Generated from `_swarm_manifest.json` — the milestones are derived from the DAG, not hand-maintained.*