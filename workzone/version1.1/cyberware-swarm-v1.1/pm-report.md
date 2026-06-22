# v1.1 board — full cws-pm run + chain verification (2026-06-21)

Both driven THROUGH govd (local node :4773, chip_sha 8bfdab05) with persistent run-ledgers — no temp dirs.

## 1. Full cws-pm run (no DRY_RUN) — `runs/pm-fullrun/pm.json`
Roll-up: `total 90 | redeemed_total 65 | already_redeemed 65 | redeemed 0 | ran 0 | blocked_deps 9 | failed 16`.

The 16 "ready" (next_pullable) tasks **all returned `decision=reject` when actually fired** — NOT infra
failures. Root cause: the playbook steps carry **`perk: null`** (both `v11-playbook.json` and the swarm's
`pm-playbook.json` — only 1 of 90 steps names a perk). govd **correctly refuses a perkless claim** — you cannot
bless "nothing". So cws-pm cannot auto-drive the tail as the playbook stands. DRY_RUN didn't surface this
because it validates existence without firing. **This is a playbook data gap, not a cyberware bug, and not (here)
an infra wall** — though the underlying subjects are still absent (see below).

→ To drive any remaining task: resolve its per-task perk and fire the validator skill directly (as the 65
already-redeemed tasks were), then `cws-observe/redeem` to append to the done-ledger.

## 2. Chain verification — `runs/observe-chainverify-2026-06-21/observe.json`
cws-observe/status through govd (`decision=allow`, step exit 0). Passed the **v1** `done-ledger.json`
(auto-discovers sibling `done-ledger-v2.json` — passing v2 directly mis-reads its genesis as a broken link).

- **`done_ledger_chain: ok`** — v1+v2 prev-hash chain + cross-reference intact (tamper-checked).
- **65/90 redeemed** · ready 16 · blocked:deps 9 · blocked:validator 0.
- **validators_missing: [] (empty)** — all 11 validator skills present (alchemy, cws-bench, cws-chaos,
  cws-conform, cws-ledgercheck, cws-modelcheck, cws-mutate, cws-redteam, cws-release, cws-settle-sim,
  harden-pyenv). What gates the tail is absent **subjects/infra** (/dev/kvm, exod meters, market subjects) +
  the unresolved per-task perks above — not missing validators.

### Milestone cones — 7 / 7 CLOSED (full SV-1…SV-6 ladder)
| cone | rung | redeemed/closure | gate | state |
|------|------|------------------|------|-------|
| M0 | — | 15/15 | P6-T05 | ✓ CLOSED |
| M1 | SV-1 | 7/7 | P0-T18 | ✓ CLOSED |
| M2 | SV-2 | 8/8 | P1-T09,P1-T10 | ✓ CLOSED |
| M3 | SV-3 | **10/10** | P2-T08,P2-T09 | ✓ CLOSED |
| M4 | SV-4 | 9/9 | P3-T09,P3-T15 | ✓ CLOSED |
| M5 | SV-5 | 8/8 | P4-T09 | ✓ CLOSED |
| M6 | SV-6 | 21/21 | P6-T21 | ✓ CLOSED |

**UPDATE 2026-06-22 — M3 / SV-3 closed (10/10).** P2-T09 (microVM budgets) was the lone open rung. It is now
redeemed (done-ledger-v2 seq 57) from a REAL Firecracker measurement on a GitHub-hosted KVM runner via
`.github/workflows/bench-microvm.yml`: **cold boot 696 ms** (≤1500) + **warm snapshot-resume 31 ms** (≤250),
driven through govd as cws-bench/microvm-overhead (decision=allow, perk-bound). The whole SV-1…SV-6 ladder is
now closed and chain-verified (66/90 tasks redeemed; the remaining 24 are unrelated infra/subject-gated tail).
