---
skill: docker
name: Docker operations
perks: [build, ps]
---

# docker — Docker operations

Container operations through proven pathways — build images, inspect running containers. Requires a reachable Docker daemon.

## What to look out for
Each tool emits one line of structured JSON (the audit + debug log) and writes its
artifacts under `record_store`. LOGS TO CHECK: that line + the named report + the executor run-ledger.

## Perks
| perk | tool | nature |
|---|---|---|
| `build` | `docker_build` | read-only / safe |
| `ps` | `docker_ps` | read-only / safe |

## How to use it
Pick a perk, copy `ledger.json` → `task-ledger.json`, fill its vars + `record_store`, then
validate → compose → compile → oversight → executor.
