---
skill: fs
name: Filesystem operations
perks: [archive, find_large]
---

# fs — Filesystem operations

Filesystem pathways that stay on the safe side: pack a directory into a tarball, find what's eating
the disk. Nothing here deletes — `find_large` *lists*; acting on the list is a separate, human-decided
step.

## What to look out for
Each tool emits one line of structured JSON (the audit + debug log) and writes its artifacts under
`record_store`. LOGS TO CHECK: that line + `archive.tar.gz` / `large_files.txt` + the executor
run-ledger.

## Perks
| perk | tool | nature |
|---|---|---|
| `archive` | `fs_archive` | writes one tar.gz to record_store — source untouched |
| `find_large` | `fs_find_large` | read-only listing (`MIN_SIZE` threshold, default 100M) |

- **`archive`** — set `SOURCE_DIR`; output `archive.tar.gz`. Single dir, no incremental.
- **`find_large`** — set `SEARCH_DIR` (+ optional `MIN_SIZE`); output `large_files.txt`. No deletion —
  the oversight rules (`rm_rf`, `find_delete`) gate destructive follow-ups by design.

## How to use it
Pick a perk, copy `ledger.json` → `task-ledger.json`, fill its vars + `record_store`, then
validate → compose → compile → oversight → executor.
