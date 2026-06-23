# cyberware v1.1 — pm report

*Snapshot: 2026-06-23.* Tracking pass (`DRY_RUN`): the plan classified, nothing fired. Progress is redeemed, not asserted — see §7.

## 1. Roll-up

**Status: ok** (tracking pass)

**Playbook:** 84 of 91 steps redeemed — `██████████████████░░` 92%

**Program:** 84 of 91 DAG tasks redeemed — `██████████████████░░` 92%

`84 redeemed · 3 blocked:deps · 4 dry`

Done-ledger: 84 pass entries (chain not re-verified here — see §7).

## 2. Milestones

| milestone | rung | closure | gate | status |
|---|---|---|---|---|
| **M0** — The spine stands — governed execution end to end (internal) | - | 15/15 | `P6-T05` | **closed** |
| **M1** — SV-1 — the protocol is real and portable | SV-1 | 7/7 | `P0-T18` | **closed** |
| **M2** — SV-2 — evidence becomes tamper-evident | SV-2 | 8/8 | `P1-T09, P1-T10` | **closed** |
| **M3** — SV-3 — execution becomes a kernel-enforced boundary  ◀ MVP | SV-3 | 10/10 | `P2-T08, P2-T09` | **closed** |
| **M4** — SV-4 — the registry and the engine publish and revoke themselves | SV-4 | 9/9 | `P3-T09, P3-T15` | **closed** |
| **M5** — SV-5 — workflows and the money's lifecycle are model-checked | SV-5 | 8/8 | `P4-T09` | **closed** |
| **M6** — SV-6 — the work pays for the work  (the ladder closes) | SV-6 | 21/21 | `P6-T21` | **closed** |
| **M7** — Agent-mode — the kernel runs the agent's intent  (cognition holds no limb) | AGENT | 10/10 | `P2-T12` | **closed** |

_Closure is the transitive dependency cone of each milestone's gate task(s), redeemed against the done-ledger — the same roll-up `cws-observe/status` computes._

## 3. Ready to pull

| task | validator | title |
|---|---|---|
| `P2-T04` | `cws-redteam` | SandboxProfile community tier: gVisor/Firecracker (seam proof, R2) |
| `P5-T01` | `cws-bench` | Store interface: sqlite-WAL → Postgres adapter (R2) + JSONL reconciler |
| `P6-T09` | `alchemy` | llm/* intelligence perk class (schema-validation payment gate) |
| `P6-T14` | `cws-settle-sim` | Stripe SettlementAdapter + internal-credits adapter (T21, R2 seam) |

## 4. Blocked

**Blocked on dependencies**

| task | validator | waiting on |
|---|---|---|
| `P3-T11` | `cws-release` | `P2-T04` |
| `P5-T04` | `cws-chaos` | `P5-T01` |
| `P6-T15` | `cws-settle-sim` | `P6-T14` |

**Blocked on validator**

_None._

## 5. What this run drove

_Tracking pass — nothing was driven. Re-run without `DRY_RUN` to drive the ready set in §3._

## 6. Honest status — what is not yet redeemed

- **3 steps blocked on dependencies** — upstream tasks must redeem first (§4).
- **Chain caveat:** this report reads done-ledger `pass` entries without re-verifying the prev-hash chain; `cws-observe/status` re-verifies the chain — run it for the chain-trusted picture.

## 7. Verify it yourself

```sh
# the chain-verified milestone picture (re-verifies the done-ledger prev-hash chain)
python3 -m infra.tool.skilltest --skill cws-observe --perk status
# the cws-pm self-test (asserts pm.json)
python3 -m infra.tool.skilltest --skill cws-pm --perk run
# re-render this board without firing
PLAYBOOK=<playbook> SWARM_DIR=<swarm> DRY_RUN=1 RECORD_STORE=<dir> python3 cws_pm.py
```

`pm.json` is the machine-readable twin of this report — same data, asserted by the self-test.
