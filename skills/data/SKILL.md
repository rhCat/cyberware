---
skill: data
name: Data wrangling
perks: [csv2json, jq]
---

# data — Data wrangling

Data transforms through proven pathways — CSV→JSON and jq queries.

## What to look out for
Each tool emits one line of structured JSON (the audit + debug log) and writes its
artifacts under `record_store`. LOGS TO CHECK: that line + the named report + the executor run-ledger.

## Perks
| perk | tool | nature |
|---|---|---|
| `csv2json` | `data_csv2json` | read-only / safe |
| `jq` | `data_jq` | read-only / safe |

## How to use it
Pick a perk, copy `ledger.json` → `task-ledger.json`, fill its vars + `record_store`, then
validate → compose → compile → oversight → executor.
