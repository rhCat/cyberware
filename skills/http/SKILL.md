---
skill: http
name: HTTP requests
perks: [get, post]
---

# http — HTTP requests

Governed curl pathways: GET a URL, POST a JSON body. The response is *captured*, never piped onward —
pipe-to-interpreter is a non-approvable oversight rule, so "fetch and execute" cannot compile into a
governed run.

## What to look out for
Each tool emits one line of structured JSON with the HTTP status + size (the audit + debug log) and
captures the response under `record_store`. LOGS TO CHECK: that line + `response.body` + the executor
run-ledger. A non-2xx status is visible in the JSON line — check it before trusting the body.

## Perks
| perk | tool | nature |
|---|---|---|
| `get` | `http_get` | read-only fetch (optional `HEADER`) |
| `post` | `http_post` | sends `BODY` (a JSON string) — mutates the remote, not the host |

- **`get`** — set `URL` (+ optional `HEADER`); output `response.body`. No retries/auth helpers in
  this pathway.
- **`post`** — set `URL` + `BODY`; JSON bodies only. Treat as write-capable: the remote side changes.

## How to use it
Pick a perk, copy `ledger.json` → `task-ledger.json`, fill its vars + `record_store`, then
validate → compose → compile → oversight → executor.
