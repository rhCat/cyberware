---
skill: terraform
name: Terraform (IaC)
perks: [plan, apply]
---

# terraform — Terraform (IaC)

Validate and plan a Terraform module (read-only) or apply it (destructive).

## What to look out for
Each tool emits one line of structured JSON (the audit + debug log) and writes its
artifacts under `record_store`. LOGS TO CHECK: that line + the named report + the executor run-ledger.

## Perks
| perk | tool | nature |
|---|---|---|
| `plan` | `tf_plan` | read-only / safe (`init -backend=false`, `validate`, `plan`) |
| `apply` | `tf_apply` | destructive (`apply -auto-approve`) — gated by `destructive: true` |

The `plan` perk never touches real state: it runs `init -backend=false`, then `validate`, then
`plan`, appending everything to `plan.txt`. The `apply` perk mutates real infrastructure and is
therefore declared `destructive: true`; the executor gates it accordingly.

## How to use it
Pick a perk (`plan` or `apply`), copy `ledger.json` → `task-ledger.json`, fill its vars + `record_store`,
then validate → compose → compile → oversight → executor.
