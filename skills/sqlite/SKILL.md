---
skill: sqlite
name: Local SQL (SQLite)
perks: [query, exec]
---

# sqlite — Local SQL (SQLite)

Query a local SQLite database (read-only) or apply a migration script to it (destructive),
through **proven, contract-bound pathways** under oversight. You never run SQL directly; you
submit a **task-ledger** and the framework validates → composes → compiles → oversees → executes it.

## What to look out for
Each tool emits one line of structured JSON (the audit + debug log) and writes its artifacts under
`record_store`. LOGS TO CHECK: that line + the named report and the executor run-ledger
(`${record_store}/run-ledger.json`).

## Perks
| perk | tool | nature |
|---|---|---|
| `query` | `sqlite_query` | read-only / safe — `sqlite3 -readonly` → `query_result.txt` |
| `exec` | `sqlite_exec` | destructive — applies a `.sql` script → `exec_applied.log` |

The `query` perk opens the database read-only and always writes a result file (a note if the db is
missing). The `exec` perk is the destructive, file-based variant: it applies a `.sql` migration file
to the database in a single pass; its destructiveness is declared via `"destructive": true` (the SQL
itself comes from the file at runtime).

## How to use it
Pick a perk, copy `ledger.json` → `task-ledger.json`, fill its vars + `record_store`, then
validate → compose → compile → oversight → executor. The blueprint is **perk-agnostic** — it
describes the lifecycle and the guardrails; a perk supplies the concrete, contract-bound *how*.
