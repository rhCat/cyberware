---
name: cyberware
description: >-
  Run real operational tasks — filesystem, git, docker, http, postgres, search, code-quality, releases,
  and more — through cyberware's GOVERNED channel instead of ad-hoc shell. You emit only a CLAIM (a skill,
  a perk, and your var KEYS) over three calls to the node — GET /catalog, POST /govern, then a per-run
  WebSocket — and the governance server blesses a value-free plan; you never write, paste, or improvise the
  commands. The node's exod runs each step confined and signs it — you run nothing but the HTTP + WebSocket
  calls, and only KEYS + status ever cross the wire (a step's DATA comes back through the cargo mount). A
  local-dev cooperative mode that runs the plan from an on-disk registry lives in cyberware_dev. Reach for
  this whenever a task maps to a governed skill.
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
to confirm a destructive perk after a push_back; `"cargo":"ro"|"rw"` to bind the node's `/cyberware_cargo` into
the confined step — the data channel, see step 3; `"traceparent":"<w3c-trace>"`.)*

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

Then drive the steps — **intent in, status out.** The node's **exod** runs each step **confined** and
Ed25519-signs the status; there is **no `grant` frame**, and **you run nothing** and send no `step_result`:

```
for st = 1 … N:
→ {"type":"step_request","step":"<st>","plan_sha":"<plan_sha>","var_values":{"<KEY>":"<value>", …}}
← {"type":"executed","step":"<st>","status":"ok","exit":0,"authority":"exod"}   ·or·  {"type":"refuse","reason":"…"} → stop
```

- **`var_values`** is how a delegated run passes VALUES: the `/govern` claim is **KEYS-only**, so the non-secret
  values ride the per-run WS **here** (never the claim plane). The node forwards ONLY plan-declared, non-secret
  keys and re-gates them on your **`params`** ACL axis; secrets never cross — keep them `*_FILE` pointers that
  exod's vault resolves server-side.
- Requires the node in delegated `exec_mode` with **exod attached**, else every step is `refuse`d (fail-closed).

Send a WebSocket **close** frame when the steps finish (or after the first non-ok step).

*(Cooperative mode — running the blessed plan from your OWN on-disk registry, with `grant` / `step_result`
frames instead of `executed` — is the local-dev path in [`cyberware_dev/SKILL.md`](cyberware_dev/SKILL.md). An
external agent never needs it.)*

**Getting DATA back — the cargo channel.** The wire is **status-only**: `:5773` returns exit codes + signed
provenance, never a perk's output, and a confined step's `RECORD_STORE` is a **server-side** workspace you
cannot read. So a step that must return DATA writes it to the **cargo** bind: add **`"cargo":"ro"|"rw"`** to the
`/govern` claim (binds the node's `/cyberware_cargo` into the confined step), set the perk's output var (e.g.
`OUT`) to a path under `/cyberware_cargo/…`, and read the artifact off that shared mount after the run. The
cargo mount is the **only** data channel out of the confined box — the wire itself stays value-free end to end.

**4 · Read the verdict.** The full signed provenance is `GET BASE/ledger/<run_id>?token=<session_token>` (the
run token, **not** the Bearer). Confirm each step ran `ok`, note the `plan_sha`, continue. Done.

**Nothing but KEYS in and status out crosses `:5773`** — no var values on the claim plane, no secrets, no command
output, and no agent-authored code (delegated var VALUES ride the per-run WS; a perk's DATA rides the cargo
mount). You never edit the blessed plan: a tamper snapshot refuses on drift, and the WS gate refuses any step
whose `plan_sha` or upstream order doesn't match the pinned plan.

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

The **local-dev `./govd-client` wrapper** (the `task-ledger.json` form, the cooperative `grant`/`step_result`
run from an on-disk registry, the in-container exec, the ACL attestation/proof flags) is in
[`cyberware_dev/SKILL.md`](cyberware_dev/SKILL.md) — the local method an external agent never needs.
The govd-less local pipeline (validator → composer → compiler → oversight → executor) is in
[`cyberware.md`](cyberware.md); the service internals (HTTP, WebSocket, authenticity, dashboard) are in
[`docs/governance-service.md`](docs/governance-service.md); the live [dashboard](https://cyberware.systems/)
shows every blueprint, perk flow, and contract.
