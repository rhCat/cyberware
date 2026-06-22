# cyberware v1.1 — project status (2026-06-22)

Generated through govd (dogfood): `cws-pm/run` (DRY_RUN board) + `cws-observe/status` (chain + milestones),
chip `132cd6c9` (lean), done-ledger-v2 head seq 64.

## Headline — the SV ladder is CLOSED; the agent-mode stage (M7) is now tracked
**All 7 SV cones closed (M0 + SV-1…SV-6), 0 open rungs.** `done_ledger_chain: ok` (tamper-checked).
**73 / 91 tasks redeemed (80%).** `validators_missing: []`; `blocked:validator: 0`. The DAG grew **90 → 91**:
a new **M7 — Agent-mode** milestone + one new task **P2-T12 (govd-as-executor)** now track the kernel-for-agents
build-out (see [`../AGENT-MODE.md`](../AGENT-MODE.md)). Recent redemptions (non-cone tail, all perk-bound):
**P6-T06** reward_verify, **P6-T10** markets, **P6-T13** reputation (seq 58-60), **P4-T06** settlement lifecycle
formally proven — TLC + Apalache, money mutants caught (seq 61); **P6-T03** escrow expiry/auto-refund + **P6-T07** code↔blueprint bisimulation (seq 62-63); **P1-T08** govd Bearer-principal auth + token-bucket (seq 64) — agent-mode keystone #1.

| cone | rung | redeemed/closure | state |
|------|------|------------------|-------|
| M0 | — (spine) | 15/15 | ✓ CLOSED |
| M1 | SV-1 reproducibility | 7/7 | ✓ CLOSED |
| M2 | SV-2 ledger integrity | 8/8 | ✓ CLOSED |
| M3 | SV-3 kernel isolation | **10/10** | ✓ CLOSED (P2-T09 microVM bench, 2026-06-22) |
| M4 | SV-4 supply chain | 9/9 | ✓ CLOSED |
| M5 | SV-5 formal proof | 8/8 | ✓ CLOSED |
| M6 | SV-6 money lifecycle | 21/21 | ✓ CLOSED |
| **M7** | **AGENT — kernel runs the agent's intent** | **8/10** | ○ open — gate **P2-T12**; keystone P1-T08 ✓, P2-T05 next |

## Phase board (DRY_RUN) — 70 redeemed · 11 ready · 9 dep-blocked · 0 failed
| phase | redeemed | ready | dep-blocked | note |
|-------|----------|-------|-------------|------|
| P0 governance spine | 18 | — | — | complete |
| P1 ledger | 8 | 2 | — | cone closed; 2 tail tasks |
| P2 exec/isolation | 9 | 2 | — | cone closed; 2 tail tasks |
| P3 supply chain | 14 | 1 | 1 | cone closed; tail |
| P4 formal proof | 8 | 1 | — | cone closed; P4-T06 settlement proof redeemed (P4-T07 emit-mutation left) |
| P5 ops/observability | 0 | 3 | 2 | **unstarted** — no cone gate; not on the SV ladder |
| P6 money | 13 | 2 | 6 | cone closed; tail T06/T10/T13 redeemed (T08/T14 need live LLM / Stripe) |

## The remaining 24 tasks (15 ready + 9 dep-blocked) — NOT ladder-blocking
Every security cone is closed; the tail is non-cone work. Two honest caveats on why it isn't auto-driven:
1. **The playbook steps carry `perk: null`** (both `v11-playbook.json` and the swarm `pm-playbook.json`) — so
   cws-pm can't fire them; govd correctly rejects a perkless claim. Each needs its per-task perk resolved and
   the validator fired directly (as the 66 done tasks were), then `cws-observe/redeem`.
2. **Several need absent subjects/infra** — exod meters, market subjects, P5 ops surfaces — which don't exist
   locally. `next_pullable` (deps met): P1-T06/T08, P2-T04/T05, P3-T16, P4-T06/T07, P5-T01/T02/T05,
   P6-T06/T08/T10/T13/T14.

P5 (ops/observability) is the only entirely-unstarted phase (0/5) — it has no SV-ladder cone, so it doesn't
gate any security guarantee; it's optional hardening.

## Bottom line
v1.1's security thesis is **complete and verified**: every rung of SV-1…SV-6 is closed, chain-verified, and
(for M3) backed by a real measurement on hardware. What's left is an optional non-security tail that needs
per-task perk resolution + a few absent subjects — not a gap in the guarantees.

## The remaining tail, reframed — agent-mode (see [`../AGENT-MODE.md`](../AGENT-MODE.md))
The kernel is built and hardened (SV ladder closed); the remaining tail *is* the **kernel-for-agents**
build-out. Re-read by layer: the **keystone** is the syscall boundary — **P1-T08** (auth: *who* is calling) +
**P2-T05** (double-blind secrets: the limb holds the credential, the cortex its name); the **integration** is
**govd-as-executor** (move `run_governed` server-side so the agent posts intent and the worker executes). Most
of the "host-blocked" set (P2-T04 gVisor, P5-T05 exod-trace, P5-T01/T04 Postgres) is **not blocked** — it just
runs on the detached **Linux node** (the neoclaw target), which is the whole point. Critical path:
**P1-T08 → P2-T05 → govd-as-executor → P5-T03**, with the node-side limb (isolation / provenance / durability)
in parallel.
