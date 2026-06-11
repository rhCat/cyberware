---
skill: release
name: Release tagging
perks: [tag]
---

# release — Release tagging

Release operations through proven pathways — annotated git tags (no push; push stays gated).

## What to look out for
Each tool emits one line of structured JSON (the audit + debug log) and writes its
artifacts under `record_store`. LOGS TO CHECK: that line + the named report + the executor run-ledger.

## Perks
| perk | tool | nature |
|---|---|---|
| `tag` | `release_tag` | read-only / safe |

## How to use it
Pick a perk, copy `ledger.json` → `task-ledger.json`, fill its vars + `record_store`, then
validate → compose → compile → oversight → executor.
