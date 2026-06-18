# cyberware v1.1 — pm report

*Snapshot: 2026-06-18.* Tracking pass (`DRY_RUN`) regenerated through `govd` (the cws-pm porter ran governed). Progress is redeemed, not asserted — and this round `cws-observe/status` re-verified the prev-hash chain **ok** (65 redeemed), so the counts below are chain-trusted, not just raw `pass` entries. See §7.

## 1. Roll-up

**Status: ok** (tracking pass)

**Playbook:** 65 of 90 steps redeemed — `██████████████░░░░░░` 72%

**Program:** 65 of 90 DAG tasks redeemed — `██████████████░░░░░░` 72%

`65 redeemed · 9 blocked:deps · 16 dry`

Done-ledger: 65 pass entries (chain not re-verified here — see §7).

## 2. Milestones

| milestone | rung | closure | gate | status |
|---|---|---|---|---|
| **M0** — The spine stands — governed execution end to end (internal) | - | 15/15 | `P6-T05` | **closed** |
| **M1** — SV-1 — the protocol is real and portable | SV-1 | 7/7 | `P0-T18` | **closed** |
| **M2** — SV-2 — evidence becomes tamper-evident | SV-2 | 8/8 | `P1-T09, P1-T10` | **closed** |
| **M3** — SV-3 — execution becomes a kernel-enforced boundary  ◀ MVP | SV-3 | 9/10 | `P2-T08, P2-T09` | open |
| **M4** — SV-4 — the registry and the engine publish and revoke themselves | SV-4 | 9/9 | `P3-T09, P3-T15` | **closed** |
| **M5** — SV-5 — workflows and the money's lifecycle are model-checked | SV-5 | 8/8 | `P4-T09` | **closed** |
| **M6** — SV-6 — the work pays for the work  (the ladder closes) | SV-6 | 21/21 | `P6-T21` | **closed** |

_Closure is the transitive dependency cone of each milestone's gate task(s), redeemed against the done-ledger — the same roll-up `cws-observe/status` computes._

## 3. Ready to pull

| task | validator | title |
|---|---|---|
| `P1-T06` | `cws-ledgercheck` | Plan as sole source of step truth (delete --list execution) |
| `P1-T08` | `cws-ledgercheck` | Transport tourniquet: bearer auth + TLS edge + rate limit (F5 partial) |
| `P2-T04` | `cws-redteam` | SandboxProfile community tier: gVisor/Firecracker (seam proof, R2) |
| `P2-T05` | `cws-redteam` | Vault adapter: sops/age + env-stub (T12, R2) |
| `P2-T09` | `cws-bench` | Author cws-bench skill (sandbox, channel overhead perks) |
| `P3-T16` | `cws-release` | SECURITY.md doorbell (M12 residue) |
| `P4-T06` | `cws-modelcheck` | settlement.blueprint.json + model-check the money (M4) |
| `P4-T07` | `cws-mutate` | Emitter mutation testing (V-MUT on emit_tla) |
| `P5-T01` | `cws-bench` | Store interface: sqlite-WAL → Postgres adapter (R2) + JSONL reconciler |
| `P5-T02` | `cws-bench` | SSE push + pagination (replace 1.5s polling) |
| `P5-T05` | `cws-bench` | OpenTelemetry traceparent across planes + in-toto provenance (T19) |
| `P6-T06` | `cws-settle-sim` | reward verify (chain + per-record zero + global zero + receipt cross-check) |
| `P6-T08` | `cws-settle-sim` | Attested meters become settleable + provider-receipt capture (6b) |
| `P6-T10` | `cws-settle-sim` | Market modes: bounty + reverse auction (6c) |
| `P6-T13` | `cws-settle-sim` | Derived reputation scores (signed, third-party reproducible) (6d) |
| `P6-T14` | `cws-settle-sim` | Stripe SettlementAdapter + internal-credits adapter (T21, R2 seam) |

## 4. Blocked

**Blocked on dependencies**

| task | validator | waiting on |
|---|---|---|
| `P3-T11` | `cws-release` | `P2-T04` |
| `P5-T03` | `cws-bench` | `P1-T08` |
| `P5-T04` | `cws-chaos` | `P5-T01` |
| `P6-T03` | `cws-settle-sim` | `P4-T06` |
| `P6-T07` | `cws-modelcheck` | `P4-T06` |
| `P6-T09` | `alchemy` | `P6-T08` |
| `P6-T15` | `cws-settle-sim` | `P6-T14` |
| `P6-T16` | `cws-bench` | `P6-T03` |
| `P6-T20` | `cws-settle-sim` | `P3-T16` |

**Blocked on validator**

_None._

## 5. What this run drove

_Tracking pass — nothing was driven. Re-run without `DRY_RUN` to drive the ready set in §3._

## 6. Honest status — what is not yet redeemed

- **9 steps blocked on dependencies** — upstream tasks must redeem first (§4).
- **Open milestones:** M3 — the spine still ahead (§2 has the closure ratios).
- **Chain:** `cws-pm` itself reads done-ledger `pass` entries without re-verifying the prev-hash chain, but this round `cws-observe/status` was run alongside it and re-verified the v1+v2 chain **ok** (65 redeemed, milestone cones intact) — so this snapshot is chain-trusted. (Invocation note: pass `cws-observe` the **v1** `done-ledger.json` path; it auto-discovers the sibling `done-ledger-v2.json` and verifies the cross-reference. Passing the v2 file directly mis-reads its genesis record as a broken link.)

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
