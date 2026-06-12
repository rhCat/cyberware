---
skill: sec
name: Security scanning
perks: [secrets, audit]
---

# sec — Security scanning

Scan a tree for leaked secrets and audit dependencies for known vulnerabilities — read-only.

## What to look out for
Each tool emits one line of structured JSON (the audit + debug log) and writes its
artifacts under `record_store`. LOGS TO CHECK: that line + the named report + the executor run-ledger.

## Perks
| perk | tool | nature |
|---|---|---|
| `secrets` | `sec_secrets` | read-only / safe |
| `audit` | `sec_audit` | read-only / safe |

- `secrets` — `grep -rEn` over `SEARCH_DIR` for likely secrets (AWS access keys, private-key headers,
  `api/secret/access key`/`password`/`token` assignments). Always writes `secrets_report.json`
  (empty `findings` array when nothing matched).
- `audit` — best-effort dependency vuln audit: runs `pip-audit` when it is on PATH and a
  `requirements*.txt` exists, and/or `npm audit` when `npm` is on PATH and a `package.json` exists.
  The auditors are optional; `audit_report.json` is always written, carrying a clear note when no
  auditor or manifest was found (the common case).

## How to use it
Pick a perk, copy `ledger.json` → `task-ledger.json`, fill its vars + `record_store`, then
validate → compose → compile → oversight → executor.
