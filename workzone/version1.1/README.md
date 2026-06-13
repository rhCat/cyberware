# workzone / version 1.1 — the v1.1 workspace + living progress record

This is the single home for the cyberware v1.1 effort: the **plan**, the **task DAG**, the live
**done-ledger**, and the **grounding/example** artifacts produced by the chip's own `cws-observe` and
`cws-conform` skills. Work is conducted by *redeeming* each task — running its validator through the
governed channel and recording the passing run-ledger — never by asserting "done".

> Governing rule (the plan's): **a task is redeemed, not asserted.** Its promise is denominated in a
> verifiable artifact — a run-ledger, a done-ledger entry — that anyone can re-check.

## Layout

```
workzone/version1.1/
  cyberware-foundation-plan-v1.1.md     the plan
  cyberware-swarm-milestones.md         the M0–M6 roadmap (derived from the DAG)
  cyberware-swarm-tool-skills.md        the 10 validator-skill specs
  cyberware-swarm-v1.1/                 the task DAG — 90 task JSONs + _swarm_manifest.json + generate_swarm.py
      done-ledger.json                  ← the LIVE redemption ledger (prev-hash chained); redeem appends here
  observe/observe.json                  ← GROUNDING: cws-observe status over the DAG (regenerated)
  conform/                              ← EXAMPLE: the worked redemption of spec/inflight.md
  README.md
```

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

## How to read the artifacts

- **`observe/observe.json`** — each task's state (`redeemed` / `ready` / `blocked:deps` /
  `blocked:validator`), the next pullable tasks, which validators are built vs infra-blocked, and the
  M0–M6 milestone closures. **Read first** to know what's done and what to pull next.
- **`cyberware-swarm-v1.1/done-ledger.json`** — the authoritative *done* record: one chained entry per
  redeemed task (`task_id`, `validator`, `verdict`, `evidence_sha`). A flipped entry breaks the chain and
  `cws-observe/status` reports `done_ledger_chain: broken`.
- **`conform/`** — the template every spec redemption follows: `inflight.task-ledger.json` (the claim that
  ran) · `inflight.run-ledger.json` (the governed evidence — the file `redeem` verifies and hashes into
  `evidence_sha`) · `inflight.doclint.json` (the verdict that made it legitimate).

## Snapshot (regenerate any time — see below)

| | |
|---|---|
| Tasks | 90 · **6 redeemed** · 10 ready · 22 blocked-on-deps · 52 blocked-on-unbuilt-validators |
| Redeemed | the P0 spec set: `P0-T01` cwp-core · `P0-T06` lpp-semantics · `P0-T09` keys · `P0-T10` privacy · `P0-T11` time · `P0-T12` inflight |
| Validators built | `cws-conform` (repin, doclint) · `cws-ledgercheck` · `cws-modelcheck` · `cws-mutate` · `cws-observe` |
| Built, not yet redeemed | `infra/cwp/canonical.py` (P0-T02 JCS canonicalizer) — needs the full published number corpus + the Go anchor (P0-T08) to meet its 100%-corpus acceptance |
| Still infra-blocked | `cws-redteam`/`-bench` (exod, P2) · `cws-chaos` (Ledger-v2/HA) · `cws-settle-sim` (P6) · `alchemy` (the import + the concordance blocker) |

## How to refresh `observe/observe.json`

```sh
SWARM=workzone/version1.1/cyberware-swarm-v1.1
# author a cws-observe/status ledger with vars {SWARM_DIR=<abs $SWARM>, DONE_LEDGER=<abs $SWARM/done-ledger.json>}
python3 -m infra.govern.compiler --ledger <ledger.json>
python3 -m infra.govern.executor --script <run.sh> --all      # → observe.json
cp <run-dir>/observe.json workzone/version1.1/observe/observe.json
```
`cws-observe/redeem` appends to `cyberware-swarm-v1.1/done-ledger.json` as tasks are redeemed.

## Pointers
The validators: `skillChip/cws-*` · the engine self-monitor: `infra/tool/selfmonitor.py` · the
canonicalizer: `infra/cwp/canonical.py` · the spec deliverables: `spec/*.md`.
