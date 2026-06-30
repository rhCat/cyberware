---
name: cyberware_dev
description: >-
  LOCAL-DEV convenience for cyberware: the `./govd-client` CLI that wraps the GET /catalog -> POST /govern ->
  per-run WebSocket protocol for a workstation that has the skillChip ON DISK. Drive govd from a
  task-ledger.json instead of hand-rolling the HTTP/WS calls; run cooperative (from your local registry) or
  delegated. The wire protocol itself — what any agent uses by default — is the top-level cyberware SKILL.md.
---

# cyberware_dev — the local-dev `./govd-client` wrapper

This is the **local-dev** path. The universal interface is the **server protocol** in the top-level
[`SKILL.md`](../SKILL.md) — three calls to the node's `:5773` (`GET /catalog` → `POST /govern` → a per-run
WebSocket). **Any agent uses that by default.** `./govd-client` is a **reference client** that implements
exactly those calls and adds conveniences for a workstation that already has the **skillChip on disk**: a
`task-ledger.json` form, automatic registry hash-verification, and cooperative (client-side) execution. Use it
when you are building or testing cyberware locally — an external agent does not need it.

```sh
export GOVD_URL=http://127.0.0.1:5773          # the node; ./govd-client defaults to this
./govd-client --url $GOVD_URL --discover       # = GET /catalog (what govd governs + your copy's status)
```

## Drive it from a task-ledger

Your only authored artifact is a small JSON form naming the skill, the perk, and your var **values** (which
stay on your side — only the KEYS cross the wire):

```json
{
  "skill": "fs",
  "perk": "find_large",
  "record_store": "<abs dir for outputs + the run-ledger>",
  "vars": { "SEARCH_DIR": "/data", "MIN_SIZE": "200M" }
}
```

```sh
./govd-client --url $GOVD_URL --ledger task-ledger.json
# hardened / remote govd: add --token-file <path> (or GOVD_TOKEN_FILE / GOVD_TOKEN) — your principal Bearer
# token, read from the file so the raw value never lands in argv. An open/local govd needs none.
```

**Secrets are never plaintext:** a secret-ish key (`PGPASSWORD`, anything `*_TOKEN`, …) is refused — pass a
**`*_FILE` pointer** (a path to a `chmod 600` file the snippet `cat`s at runtime).

## What `--ledger` does (cooperative — the default)

The client runs the whole protocol for you:

1. `POST /govern` with the var KEYS → the value-free plan (`sequence`, `snippet_shas`, `wrapper`) + a per-run WS.
2. **Verifies your registry matches the blessed hashes** — your `perks/<perk>/src` files must equal
   `plan.snippet_shas` (sha256), AND the whole skill must pass its committed authenticity index
   (`skill_index.verify` — catches a changed / missing / untracked sibling). No file bodies cross the wire.
3. Opens the WS (`hello` → `hello_ack`), then per step: `step_request` → `grant`, runs `bash run.sh --step <st>`
   from **your** registry (`SNIP` = your `perks/<perk>/src`; var **values** + `RECORD_STORE` via the ENV), reports
   `step_result` (status only) → `recorded`. Stops on the first non-ok step.
4. Returns `{decision, plan_sha, results:[{step, exit}], ledger}`. Full provenance:
   `GET $GOVD_URL/ledger/<run_id>?token=…`.

`--registry <dir>` points at where the skill code lives (default: this cyberware install). `--fetch-only` stops
after the verdict (no run). `--approve <perk>` confirms a destructive perk after a `push_back`.

## Delegated (server-side) — `--delegated`

Against a Linux **body** node, hand execution to the node instead of running locally:

```sh
./govd-client --url $GOVD_URL --ledger task-ledger.json --delegated
```

The client POSTs the claim, opens the WS, and per step sends `step_request`; the node's **exod** runs the step
**confined** and answers `executed` with the Ed25519-signed status — **no `grant` / `step_result` round-trip**,
exod is the authority. You run **nothing** and hold no porter. Requires the node in delegated `exec_mode` with
exod attached, else each step is refused (fail-closed). This is the same wire any external agent uses by default
— see [`SKILL.md`](../SKILL.md).

If your principal carries a **per-actor ACL**, a scoped claim on a body also rides an operator-signed
**attestation** (`--attestation <file>`) and a one-time possession **proof** (`--proof-key <file>`) that exod
re-checks off-node. When the operator runs exod in **enforce** mode (an ACL-issuer key pinned, `--acl-strict`),
that re-check means a compromised govd can neither widen your token nor misattribute your run; without it exod
audits rather than refuses. An unscoped (operator-trusted) token needs neither.

## On a body node — no source tree on disk

A **body** node runs cyberware only as a container, so `./govd-client` and `infra/` aren't on the host — the
client lives **inside the container**. Run it there, staging your token + ledger in (ledger path-vars are then
*container* paths, e.g. `/app/...`):

```sh
docker exec -i cyberware sh -c 'cat >/tmp/t'      < ~/agent.token
docker exec -i cyberware sh -c 'cat >/tmp/l.json' < task-ledger.json
docker exec -e GOVD_URL=http://127.0.0.1:5773 cyberware \
  python3 -m infra.govern.govd_client --token-file /tmp/t --ledger /tmp/l.json
```

Targeting the node you're *on*? Use its **in-container `127.0.0.1:5773`** — the node's own tailnet IP would
hairpin (container → host overlay IP → back) and stall the WS.

## More

The wire protocol (what any agent uses) + the discovery/fleet calls are in [`SKILL.md`](../SKILL.md); delegation
+ exod containment in [`docs/containment-delegation.md`](../docs/containment-delegation.md); the govd-less local
pipeline in [`cyberware.md`](../cyberware.md).
