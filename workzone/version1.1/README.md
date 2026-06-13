# workzone / version 1.1 — the living progress record

This folder is the **grounding** for the v1.1 build and a **worked example** of how work is conducted:
not by asserting "done", but by *redeeming* each task — running its validator through the governed
channel and recording the passing run-ledger. The artifacts here are produced by the chip's own
`cws-observe` and `cws-conform` skills, so this is evidence, not narration.

> Governing rule (the plan's): **a task is redeemed, not asserted.** Its promise is denominated in a
> verifiable artifact — a run-ledger, a done-ledger entry — that anyone can re-check.

## The operating loop

```
cws-observe/status  →  author the deliverable  →  cws-conform / -modelcheck / -ledgercheck / -mutate
   (what's next)         (spec / code / skill)       (validate it THROUGH the governed channel)
        ▲                                                          │
        └──────────  cws-observe/redeem  ←───────────────────────┘
                     (passing run-ledger → done-ledger entry)
```
`selfmonitor` gates every change in CI (blueprints deadlock-free · chip authentic · enforcement-surface
mutation ratchet). The graders live inside the chip they grade.

## What's here

### `observe/` — GROUNDING (the current project state)
- **`observe.json`** — `cws-observe/status` over the 90-task DAG: each task's state
  (`redeemed` / `ready` / `blocked:deps` / `blocked:validator`), the next pullable tasks, which
  validators are built vs still infra-blocked, and the M0–M6 milestone closures. **Read this first** to
  know what is done and what to pull next.
- **`done-ledger.json`** — the redemption ledger: one `prev`-hash-chained entry per redeemed task
  (`task_id`, `validator`, `verdict`, `evidence_sha`). This is the authoritative record of *done*; a
  flipped entry breaks the chain and `cws-observe/status` reports it.

### `conform/` — EXAMPLE (one worked redemption, end to end)
The redemption of `spec/inflight.md` (task **P0-T12**), the template every spec redemption follows:
- **`inflight.task-ledger.json`** — the claim that ran: `skill=cws-conform`, `perk=doclint`.
- **`inflight.run-ledger.json`** — the governed run-ledger (the evidence): the validator step recorded
  `ok`, no refusal event. This is the file `cws-observe/redeem` verifies and hashes into `evidence_sha`.
- **`inflight.doclint.json`** — the verdict: `status: ok`, the normative-statement count, no missing
  required topic. *This* is what made the redemption legitimate.

## Snapshot (regenerate any time — see below)

| | |
|---|---|
| Tasks | 90 · **4 redeemed** · 8 ready · 26 blocked-on-deps · 52 blocked-on-unbuilt-validators |
| Redeemed | `P0-T09` keys · `P0-T10` privacy · `P0-T11` time · `P0-T12` inflight (the M2/M5/M8/M9 specs) |
| Validators built | `cws-conform` (repin, doclint) · `cws-ledgercheck` · `cws-modelcheck` · `cws-mutate` · `cws-observe` |
| Built, not yet redeemed | `infra/cwp/canonical.py` (P0-T02 JCS canonicalizer) — needs the full published number corpus + the Go anchor (P0-T08) to meet its 100%-corpus acceptance |
| Still infra-blocked | `cws-redteam`/`-bench` (exod, P2) · `cws-chaos` (Ledger-v2/HA) · `cws-settle-sim` (P6) · `alchemy` (the import + the concordance blocker) |

## How to refresh this folder

```sh
# grounding — current status + the redemption ledger
python3 -m infra.govern.compiler  --ledger <a cws-observe/status ledger pointing SWARM_DIR at docs/v1.1_plan/cyberware-swarm-v1.1>
python3 -m infra.govern.executor  --script <run.sh> --all   # → observe.json
cp docs/v1.1_plan/cyberware-swarm-v1.1/done-ledger.json workzone/version1.1/observe/

# (the canonical done-ledger lives with the DAG; this folder keeps a documented snapshot + the example)
```
The live done-ledger is `docs/v1.1_plan/cyberware-swarm-v1.1/done-ledger.json`; `cws-observe/redeem`
appends to it as tasks are redeemed.

## Pointers
- The plan + DAG: [`docs/v1.1_plan/`](../../docs/v1.1_plan/) · the validators: `skillChip/cws-*` ·
  the engine self-monitor: `infra/tool/selfmonitor.py` · the canonicalizer: `infra/cwp/canonical.py`.
