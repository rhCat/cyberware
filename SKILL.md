---
name: cyberware
description: >-
  Run real operational tasks — filesystem, git, docker, http, postgres, search, code-quality, releases,
  and more — through cyberware's GOVERNED channel instead of ad-hoc shell. You emit only a CLAIM (a skill,
  a perk, and your var KEYS) over three calls to the node — GET /catalog, POST /govern, then a per-run
  WebSocket — and the governance server blesses a value-free plan; you never write, paste, or improvise the
  commands. Two run modes: delegated (the node's exod runs each step confined and signs it — you run nothing;
  the default for any agent) and cooperative (you run the blessed plan from your own on-disk registry). Reach
  for this whenever a task maps to a governed skill.
---

# cyberware — the governed channel for an agent

cyberware is a **verifiable governance runtime**. You do not run commands ad-hoc. You make a **claim**;
**govd** (the governance server) governs it and blesses a **value-free, code-free plan**; the plan runs under
live oversight and you read back a signed verdict. The loop below is the *entire* contract — follow it, do not
improvise around it.

> **The one principle: no data crosses the boundary, and neither does code you wrote.** govd sees only the
> *claim* (names + var KEYS) and *status*. The skill code is the registry's, blessed by hash — never yours to
> author. Your only output is the claim and the calls.

**You talk to the governing node over plain HTTP + one WebSocket on `:5773`** — three calls, no SDK (the loop
below). Set `BASE` to the node, e.g. `http://127.0.0.1:5773`. The repo's `./govd-client` is **only a local-dev
convenience** that wraps these same calls for a machine that has the skillChip on disk — its CLI is documented
separately in [`cyberware_dev/SKILL.md`](cyberware_dev/SKILL.md). By default, go through the protocol.

**In a fleet?** Any node's discovery plane (`:8773`) tells you *which* node to use — then that node's `:5773`
is your `BASE`:

```sh
curl -H "Authorization: Bearer $TOKEN" "$ANY_NODE:8773/fleet/find?skill=<skill>"   # -> one node's :5773 url
curl -H "Authorization: Bearer $TOKEN" "$ANY_NODE:8773/fleet/nodes"                # -> the full roster
```

`/fleet/find` + `/fleet/nodes` are **Bearer-gated** (the roster discloses the fleet — pass your token or get
`401`; only `/fleet/health` is open). A lone/unwired node answers with just itself, so the same call works
fleet or no fleet. The plane only **points** — you still claim + govern on the node's `:5773`. Nodes carry a
**`fleet_tier`** (mothership > edge > subagent > … — a topology hierarchy *orthogonal* to the trust `tier`);
narrow discovery with `&fleet_tier=<edge|subagent|…>`. To give a *subagent* its own scoped, strictly-lower-tier
governed node — its claims bounded to a least-privilege chip + ACL (a content-identity subset of yours) — claim
**`cws-fleet:deploy`**.

## The loop — three calls to the node's `:5773`

**1 · Discover — `GET BASE/catalog`** (no auth — you may ask "what do you govern?" before you hold a token).
Returns every governed **skill** + each perk's var **KEYS**:

```json
{ "skills": [ {
  "skill": "general:fs", "verified": true, "skill_sha": "…", "drift": null,
  "perks": [ { "id": "find_large", "destructive": false,
               "vars": { "required": ["SEARCH_DIR"], "optional": ["MIN_SIZE"] } } ] } ] }
```

Pick a perk on a skill whose **`verified`** is `true` (`drift` ≠ `null` → its copy fails its authenticity index;
don't run it). Its `vars.required` / `vars.optional` **KEYS** are the entire claim contract — you never open a
skill file to claim. Skill ids are **namespaced** `<ns>:<name>` (`general:fs`, `cws:cws-create`); `/catalog`
returns the canonical `ns:name`. A **bare** name works when exactly one namespace owns it, but a name two own is
rejected `ambiguous_skill_id` — namespace it.

**2 · Claim — `POST BASE/govern`** (`Content-Type: application/json`). **This call** carries
`Authorization: Bearer <token>` on a hardened node — the token is a **principal credential the operator
provisions out-of-band** (govd matches its sha256 in a principals registry; there is **no self-service
issuance**). Send **names + KEYS only — never the values:**

```json
{ "skill": "general:fs", "perk": "find_large", "var_keys": ["SEARCH_DIR", "MIN_SIZE"] }
```

**Secrets are never a value, and never a plain key:** a secret-ish key (`PGPASSWORD`, anything `*_TOKEN`, …) is
**refused** (`plaintext_secret_key`). Pass it as a **`*_FILE` pointer** instead — a key ending `_FILE` whose
value is a path to a `chmod 600` file the snippet `cat`s at runtime. *(Optional body fields: `"approve":["<perk>"]`
to confirm a destructive perk after a push_back; `"traceparent":"<w3c-trace>"`.)*

The verdict returns:

```json
{ "decision": "allow", "run_id": "…", "plan_sha": "…",
  "plan": { "skill": "general:fs", "perk": "find_large",
            "sequence": ["find_large_tool"], "snippet_shas": { "find_large.sh": "<sha256>" },
            "wrapper": "<the run.sh text>" },
  "ws": "ws://<host>:5773/oversight", "session_token": "…" }
```

- **`reject`** → a `problems[]` array names why: **VALIDATE** (registry `drift`), **ACCESS-1**
  (`skill_remote_closed` — the skill's own `access.json` closes it to you), **ACCESS-2** (per-actor ACL — a
  skill/tier/perk your token isn't granted), the **budget** shutoff (`insufficient_credits` / `budget_unmetered`),
  or a structural reject (bad var key · missing input · `plaintext_secret_key` · `ambiguous_skill_id` · deadlock).
  **Fix the claim — none is `approve`-able; never route around a refusal.**
- **`push_back`** → a destructive perk needs approval; re-POST the same body with `"approve":["<perk>"]`.

**3 · Run — open the per-run WebSocket** at the verdict's `ws` field (a raw RFC-6455 upgrade on the **same**
`:5773`). It is gated by the per-run **`session_token`** in the hello frame — **not** the Bearer. The step ids
are just `"1" … "N"` for `N = plan.sequence.length` — **the plan is the only source of step truth.** Begin:

```
→ {"type":"hello","run_id":"<run_id>","token":"<session_token>"}   ← {"type":"hello_ack","authorized":true}
```

Then drive the steps — **the exchange differs by execution mode:**

- **Delegated — *intent in, status out* (the default for any agent that doesn't carry the skill code):** the
  node runs each step; `step_request` is answered **directly** with the signed result — there is **no `grant`
  frame**:
  ```
  for st = 1 … N:
  → {"type":"step_request","step":"<st>","plan_sha":"<plan_sha>"}
  ← {"type":"executed","step":"<st>","status":"ok","exit":0,"authority":"exod"}   ·or·  {"type":"refuse","reason":"…"} → stop
  ```
  **exod** ran the step **confined** and Ed25519-signed the status; **you run nothing and send no `step_result`.**
  (Requires the node in delegated `exec_mode` with exod attached, else every step is `refuse`d — fail-closed.)
- **Cooperative — you run it from your OWN registry** (you have the skillChip on disk; this is the `./govd-client`
  path): `step_request` is answered with `grant`; you run the blessed step locally, then report **status only**:
  ```
  for st = 1 … N:
  → {"type":"step_request","step":"<st>","plan_sha":"<plan_sha>"}   ← {"type":"grant"}   ·or·  {"type":"refuse","reason":"…"} → stop
        run  bash run.sh --step <st>   (run.sh = plan.wrapper) with your var VALUES in the ENV
        (+ RECORD_STORE=<out dir>, SNIP=<your perks/<perk>/src dir>)
  → {"type":"step_result","step":"<st>","plan_sha":"<plan_sha>","status":"ok"|"error","exit":<code>}   ← {"type":"recorded"}
  stop on the first non-ok step
  ```
  First verify your perk's src files match `plan.snippet_shas` (sha256) — file bodies never cross the wire; you
  prove authenticity locally. [`cyberware_dev/SKILL.md`](cyberware_dev/SKILL.md) automates all of this.

Send a WebSocket **close** frame when the steps finish (or after the first non-ok step).

**4 · Read the verdict.** The full signed provenance is `GET BASE/ledger/<run_id>?token=<session_token>` (the
run token, **not** the Bearer). Confirm each step ran `ok`, note the `plan_sha`, continue. Done.

**Nothing but KEYS in and status out crosses `:5773`** — no var values, no secrets, no command output, and no
agent-authored code. You never edit the blessed plan: a tamper snapshot refuses on drift, and the WS gate
refuses any step whose `plan_sha` or upstream order doesn't match the pinned plan.

## Never

- Run a snippet (`skillChip/.../src/<tool>.sh`) directly, or hand-write the commands a perk would run.
- Put a secret **value** anywhere — claim, config, or var. Use a `*_FILE` pointer.
- Edit a blessed plan to skip a step, force order, or slip past a contract.
- Rely on a `drift` / unverified skill. *Governed* means blessed by hash from the image — nothing less.

## No matching skill?

If discovery shows no `verified` skill for the task, it is **new** work, not a governed run. Use
**`cws-create/evaluate`** (is it a deterministic execution pathway worth governing?) →
**`cws-create/scaffold`**, or **`cws-addperk`** for a new perk on an existing skill — each opens a PR you
review. Once merged and govd's image is rebuilt (the build re-checks every index), it becomes `verified`.

## More

The **local-dev `./govd-client` wrapper** (the `task-ledger.json` form, cooperative-from-registry, the
in-container exec, the ACL attestation/proof flags) is in [`cyberware_dev/SKILL.md`](cyberware_dev/SKILL.md).
The govd-less local pipeline (validator → composer → compiler → oversight → executor) is in
[`cyberware.md`](cyberware.md); the service internals (HTTP, WebSocket, authenticity, dashboard) are in
[`docs/governance-service.md`](docs/governance-service.md); the live [dashboard](https://cyberware.systems/)
shows every blueprint, perk flow, and contract.
