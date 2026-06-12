---
skill: ssh
name: Remote execution (SSH)
perks: [check, run]
---

# ssh — Remote execution (SSH)

Check SSH connectivity (read-only) or run a vetted command on a remote host (destructive).
The private key is always a `*_FILE` pointer passed to `ssh -i` — never an inline secret value.

## What to look out for
Each tool emits one line of structured JSON (the audit + debug log) and writes its artifacts under
`record_store`. LOGS TO CHECK: that line + the named report/output + the executor run-ledger.

## Perks
| perk | tool | nature |
|---|---|---|
| `check` | `ssh_check` | read-only / safe — connectivity probe, always writes `ssh_check.json` |
| `run` | `ssh_run` | destructive — executes `$COMMAND` remotely, captures all output to `ssh_output.log` |

- `check` runs a non-interactive `BatchMode=yes` probe (`ssh ... true`) and records
  `{"host":..,"user":..,"reachable":true|false}` whether or not the host answers.
- `run` executes the supplied `$COMMAND` on the remote host and tees stdout+stderr into the output log.
  Destructiveness is declared (`"destructive": true`); dangerous commands still face oversight.

## How to use it
Pick a perk (`check` or `run`), copy `ledger.json` → `task-ledger.json`, fill its vars + `record_store`
(supply `SSH_KEY_FILE` only when key-auth is needed), then validate → compose → compile → oversight → executor.
