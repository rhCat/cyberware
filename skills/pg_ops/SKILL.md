---
skill: pg_ops
name: Governed PostgreSQL operations
perks: [select, migrate]
---

# pg_ops — governed PostgreSQL operations

Run PostgreSQL work through **proven, contract-bound pathways** under oversight. You never run SQL
directly; you submit a **task-ledger** and the framework validates → composes → compiles → oversees →
executes it. Destructive SQL is refused unless explicitly approved.

## What to look out for (for the intelligence)
- The **blueprint** (`blueprint.json`) is the general lifecycle: `ready → connected → operated →
  verified → recorded`. Its `safety_invariants` are the things you must respect — chiefly
  **governed_execution_only** (tools run *only* through `executor.py`) and **no_destructive_without_approval**.
- Each tool emits **deterministic structured JSON** on stdout — that line *is* the audit + debug log.
  After a run, check `${record_store}/run-ledger.json` (the executor's record) and each step's JSON.

## How to use it — fill the form, submit it
1. Pick a **perk** (a proven pathway): `select` (read-only query) or `migrate` (apply a SQL file).
2. Copy `ledger.json` → your `task-ledger.json` and fill the `${...}` fields, bounded by the perk's
   `manifesto.json` (the variables it accepts) and `src/contracts.json` (the I/O + checks).
3. Hand it to the infrastructure:
   ```sh
   python3 -m infra.govern.validator --ledger task-ledger.json     # are the claims real?
   python3 -m infra.govern.composer  --ledger task-ledger.json     # L++ → TLC, no deadlock
   python3 -m infra.govern.compiler  --ledger task-ledger.json -o run.sh
   python3 -m infra.govern.oversight --script run.sh               # OVERSIGHT_RULE (drops refused)
   python3 -m infra.govern.executor  --script run.sh --step 1      # the ONLY way to run
   ```

## Perks
| perk | pathway | destructive? |
|---|---|---|
| `select` | read-only `SELECT … LIMIT` → CSV | no |
| `migrate` | apply a `.sql` migration file in a transaction | yes (DROP/TRUNCATE refused by oversight unless `--approve`) |

The blueprint is **perk-agnostic** — it describes the lifecycle and the guardrails; a perk supplies the
concrete, contract-bound *how*.
