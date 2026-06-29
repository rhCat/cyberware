---
name: cyberware
description: >-
  Run real operational tasks — filesystem, git, docker, http, postgres, search, code-quality, releases,
  and more — through cyberware's GOVERNED channel instead of ad-hoc shell. You emit only a CLAIM (a skill,
  a perk, and your var KEYS) and run the value-free plan the governance server blesses; you never write,
  paste, or improvise the commands. Two execution modes: cooperative (default — you run the blessed plan
  from your own registry, any OS) and delegated (`--delegated`, a Linux body whose exod runs each step
  confined and signs it; you run nothing). Reach for this whenever a task maps to a governed skill.
---

# cyberware — the governed channel for an agent

cyberware is a **verifiable governance runtime**. You do not run commands ad-hoc. You make a **claim**;
**govd** (the governance server) governs it and blesses a **value-free, code-free plan**; you run that
plan from your **own** registry under live oversight and read back a verdict. The loop below is the
*entire* contract — follow it, do not improvise around it.

> **The one principle: no data crosses the boundary, and neither does code you wrote.** govd sees only the
> *claim* (names + var KEYS) and *status*. The skill code is the registry's, blessed by hash — never
> yours to author. Your only output is the claim and the call.

Set `GOVD_URL` to the server (e.g. `export GOVD_URL=http://127.0.0.1:5773`). The repo ships `./govd-client`.

**In a fleet?** Any node's discovery plane (`:8773`) tells you *which* node to use — then point `GOVD_URL` there:

```sh
curl -H "Authorization: Bearer $GOVD_TOKEN" "$ANY_NODE:8773/fleet/find?skill=<skill>"
# -> {"url": "http://<node>:5773", ...}   then: export GOVD_URL=<that url>
```

A lone node answers with itself, so the same call works whether or not there's a fleet. The fleet plane only
points; you still claim + govern on the node's `:5773`.

## The loop — five steps

**1 · Load this skill.** Done. It is the only cyberware doc you need to start.

**2 · Discover, then read the sub-skill.** Ask govd what it governs:

```sh
./govd-client --url $GOVD_URL --discover          # or just: GET $GOVD_URL/catalog
```

You get every governed **skill**, its **perks**, each perk's **var KEYS** (required/optional), and a
status for *your* copy of each:

| status | meaning | runnable? |
|---|---|---|
| `verified` | govd governs it **and** your registry matches the blessed hash | **yes** |
| `drift` | your copy differs from the governed one | no — reconcile first |
| `unverified` | a **new** skill govd's image has never seen | no — add it, rebuild the image |
| `server_drift` | govd's **own** copy of the skill fails its authenticity index — its blessing is untrustworthy | no — wait for a govd image rebuild |

Skill ids are **namespaced** — `<namespace>:<name>` (e.g. `general:fs`, `cws:cws-create`), the namespace
being the source group a skill ships under (one chip can be **composed** from several sources, so
`general:search` and `magnumopus:search` coexist). `/catalog` returns the canonical `ns:name`. A **bare**
name still works when exactly one namespace owns it — govd canonicalizes it — but a name two namespaces own
is **rejected** (`ambiguous_skill_id`); namespace the claim to disambiguate.

Pick a **`verified`** skill + perk, then read its `skillChip/<ns>/<skill>/SKILL.md` and the perk's
`perks/<perk>/metadata.json` (rules · usage · limitation · example) for the inputs. **Discovery + the
sub-skill is the only reading you do.**

**3 · Emit the claim — that is your only output.** Your entire contribution is a small JSON form (the
task-ledger) naming the skill, the perk, and your var **values** (which stay on your side), plus one
call. You do **not** write commands, scripts, or a `run.sh`.

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
# hardened / remote govd: add --token-file <path> (or GOVD_TOKEN_FILE) — your principal Bearer token,
# read from the file so the raw value never lands in argv. An open/local govd needs none.
```

`fetch` sends govd the var **keys** only (`SEARCH_DIR`, `MIN_SIZE`) — never the values. **Secrets are
never plaintext:** pass a **`*_FILE` pointer** (a path to a `chmod 600` file) that the snippet `cat`s at
runtime; a plaintext-secret key (`PGPASSWORD`, `*_TOKEN`, …) is refused.

**4 · govd governs → you run the blessed plan.** govd checks the claim against its **own** registry, runs
the composition + TLA⁺/TLC model check, and returns one of:

- **`allow`** → the **value-free plan** (tool sequence + each snippet's sha256 + a `${VAR}` wrapper) + a
  per-run WebSocket. The client **verifies your registry matches the blessed hashes**, then runs the
  porters+cores **from your registry** step by step, reporting **status only** over the WS. (`--ledger`
  with no `--fetch-only` does all of this.)
- **`push_back`** → a **destructive** perk needs explicit approval. Re-claim with `--approve <perk>` only
  if the destruction is intended.
- **`reject`** → the claim fails one of govd's **three independent gates** (each fail-closed): **VALIDATE**
  (registry drift — your copy doesn't match the blessed hash), **ACCESS-1** (the skill's *own* `access.json`
  policy closes it to you — `skill_remote_closed` when govd serves others and the skill hasn't opted in), or
  **ACCESS-2** (the claim is outside your token's per-actor ACL scope — a skill/tier you may not run, or a
  destructive/credentialed perk your token isn't granted). Plus the structural rejects — bad var key, a
  plaintext secret, a missing input, a deadlock, or an **ambiguous** skill id (`ambiguous_skill_id` —
  namespace it). None is clearable by `--approve`; fix the *claim* — never route around the refusal.

The loop above is **cooperative** mode (the default): you run the porters+cores from your registry and
report status only. Against a Linux **body** you can run **delegated** instead — add `--delegated`:

```sh
./govd-client --url $GOVD_URL --ledger task-ledger.json --delegated
```

govd hands a signed grant to **exod**, which runs each step confined and Ed25519-signs the authoritative
status; you run **nothing**, and govd records exod's status (an agent self-report is rejected). Either way
the wire is value-free and you read the same verdict. See [containment-delegation.md](docs/containment-delegation.md).

If your principal carries a **per-actor ACL**, a scoped claim on a body also rides an operator-signed
**attestation** (`--attestation`) and a one-time possession **proof** (`--proof-key`) that exod re-checks
off-node. When the operator runs exod in **enforce** mode (an ACL-issuer key pinned, `--acl-strict`), that
re-check means a compromised govd can neither widen your token nor misattribute your run; without it exod
audits rather than refuses. An unscoped (operator-trusted) token needs neither.

You never edit the blessed `run.sh`: a tamper snapshot refuses on drift, and the WS gate refuses any step
whose `plan_sha` or upstream order doesn't match the pinned plan.

**5 · Read the verdict, move on.** The call returns `{decision, plan_sha, results:[{step, exit}], ledger}`.
The full provenance is govd's, at `GET $GOVD_URL/ledger/<run_id>?token=…`. Confirm the steps ran `ok`, note the
`plan_sha`, continue. Done.

## Never

- Run a snippet (`skillChip/.../src/<tool>.sh`) directly, or hand-write the commands a perk would run.
- Put a secret **value** anywhere — ledger, config, or var. Use a `*_FILE` pointer.
- Edit a blessed plan to skip a step, force order, or slip past a contract.
- Rely on a `drift` / `unverified` skill. *Governed* means blessed by hash from the image — nothing less.

## No matching skill?

If discovery shows no `verified` skill for the task, it is **new** work, not a governed run. Use
**`cws-create/evaluate`** (is it a deterministic execution pathway worth governing?) →
**`cws-create/scaffold`**, or **`cws-addperk`** for a new perk on an existing skill — each opens a PR you
review. Once merged and govd's image is rebuilt (the build re-checks every index), it becomes `verified`.

## More

The govd-less local pipeline (validator → composer → compiler → oversight → executor) is in
[`cyberware.md`](cyberware.md); the service internals (HTTP, WebSocket, authenticity, dashboard) are in
[`docs/governance-service.md`](docs/governance-service.md); the live
[dashboard](https://cyberware.systems/) shows every blueprint, perk flow, and contract.
