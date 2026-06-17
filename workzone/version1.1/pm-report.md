# cyberware v1.1 — pm report

*Snapshot: 2026-06-16.* Tracking pass (`DRY_RUN`): the plan classified, nothing fired. Progress is redeemed, not asserted — see §7.

## 1. Roll-up

**Status: ok** (tracking pass)

**Playbook:** 52 of 90 steps redeemed — `████████████░░░░░░░░` 58%

**Program:** 52 of 90 DAG tasks redeemed — `████████████░░░░░░░░` 58%

`52 redeemed · 5 blocked:deps · 22 blocked:validator · 11 dry`

Done-ledger: 52 pass entries (chain not re-verified here — see §7).

## 2. Milestones

| milestone | rung | closure | gate | status |
|---|---|---|---|---|
| **M0** — The spine stands — governed execution end to end (internal) | - | 11/15 | `P6-T05` | open |
| **M1** — SV-1 — the protocol is real and portable | SV-1 | 7/7 | `P0-T18` | **closed** |
| **M2** — SV-2 — evidence becomes tamper-evident | SV-2 | 8/8 | `P1-T09, P1-T10` | **closed** |
| **M3** — SV-3 — execution becomes a kernel-enforced boundary  ◀ MVP | SV-3 | 9/10 | `P2-T08, P2-T09` | open |
| **M4** — SV-4 — the registry and the engine publish and revoke themselves | SV-4 | 7/9 | `P3-T09, P3-T15` | open |
| **M5** — SV-5 — workflows and the money's lifecycle are model-checked | SV-5 | 8/8 | `P4-T09` | **closed** |
| **M6** — SV-6 — the work pays for the work  (the ladder closes) | SV-6 | 11/21 | `P6-T21` | open |

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

## 4. Blocked

**Blocked on dependencies**

| task | validator | waiting on |
|---|---|---|
| `P3-T09` | `cws-release` | `P3-T08` |
| `P3-T11` | `cws-release` | `P2-T04` |
| `P5-T03` | `cws-bench` | `P1-T08` |
| `P6-T07` | `cws-modelcheck` | `P6-T05`, `P4-T06`, `P3-T08` |
| `P6-T16` | `cws-bench` | `P6-T02`, `P6-T03` |

**Blocked on validator**

- **`alchemy`** — not built · blocks: `P3-T08`, `P6-T09`, `P6-T19`
- **`cws-chaos`** — not built · blocks: `P2-T10`, `P5-T04`, `P6-T17`
- **`cws-settle-sim`** — not built · blocks: `P6-T01`, `P6-T02`, `P6-T03`, `P6-T04`, `P6-T05`, `P6-T06`, `P6-T08`, `P6-T10`, `P6-T11`, `P6-T12`, `P6-T13`, `P6-T14`, `P6-T15`, `P6-T18`, `P6-T20`, `P6-T21`

## 5. What this run drove

_Tracking pass — nothing was driven. Re-run without `DRY_RUN` to drive the ready set in §3._

## 6. Honest status — what is not yet redeemed

- **22 steps blocked on unbuilt validators** — the validator skill must be authored before its tasks can be driven (§4).
- **5 steps blocked on dependencies** — upstream tasks must redeem first (§4).
- **Open milestones:** M0, M3, M4, M6 — the spine still ahead (§2 has the closure ratios).
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
