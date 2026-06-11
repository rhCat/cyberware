---
skill: search
name: Code search
perks: [grep, loc]
---

# search — Code search

Search and measure a codebase through proven pathways — pattern search and line counts.

## What to look out for
Each tool emits one line of structured JSON (the audit + debug log) and writes its
artifacts under `record_store`. LOGS TO CHECK: that line + the named report + the executor run-ledger.

## Perks
| perk | tool | nature |
|---|---|---|
| `grep` | `search_grep` | read-only / safe |
| `loc` | `search_loc` | read-only / safe |

## How to use it
Pick a perk, copy `ledger.json` → `task-ledger.json`, fill its vars + `record_store`, then
validate → compose → compile → oversight → executor.
