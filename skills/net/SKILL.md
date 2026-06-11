---
skill: net
name: Network diagnostics
perks: [healthcheck, dns]
---

# net — Network diagnostics

Networking diagnostics through proven pathways — HTTP health probes and DNS resolution.

## What to look out for
Each tool emits one line of structured JSON (the audit + debug log) and writes its
artifacts under `record_store`. LOGS TO CHECK: that line + the named report + the executor run-ledger.

## Perks
| perk | tool | nature |
|---|---|---|
| `healthcheck` | `net_healthcheck` | read-only / safe |
| `dns` | `net_dns` | read-only / safe |

## How to use it
Pick a perk, copy `ledger.json` → `task-ledger.json`, fill its vars + `record_store`, then
validate → compose → compile → oversight → executor.
