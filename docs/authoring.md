# Authoring a skill

A skill is a directory on the **skillChip** — cyberware's skill cartridge, a separate repo vendored as the
`skillChip/` submodule (located by `$CYBERWARE_SKILLCHIP`, default `<repo>/skillChip`). Its anatomy:

```
skillChip/<skill>/
  SKILL.md                 context for the intelligence — what it does, what to watch, which logs to check
  blueprint.json           the L++ CFG (the perk-agnostic lifecycle + safety_invariants)
  perks.json               the proven pathways (id, summary, tools, destructive?)
  ledger.json              the FORM the LLM fills → task-ledger.json
  index.json               per-file sha256 + a roll-up skill_sha (by skill_index.py) — the authenticity manifest
  blueprint.{drawio,svg}   generated diagrams (by visualize.py)
  perks/<perk>/
    metadata.json          description · rules · usage · limitation · minimal_example
    manifesto.json         the ${VAR} template: `sequence` (tool order) + `tools` + `env` + `requires`
    src/
      contracts.json       the tool's I/O + checks (required inputs, output_exists)
      <tool>.sh            the proven pathway — emits deterministic structured JSON (audit + debug log)
    test/
      case.json            the perk's OWN governed self-test (vars · fixture · expect) — pinned in the index
      fixture/             (optional) input files the test ships
```

Every file is mechanically connected and verifiable, not prose to be trusted: the blueprint is
model-checked, the contract is enforced at run time, the **index** pins every file, and the **test**
proves the perk through the real channel. The skill's identity is the `skill_sha` over all of it.

## 0. Evaluate first (the on-ramp)

Before authoring, run the idea through **`cws-create/evaluate`** — it classifies it as **execution**
(a tool/pathway — fits cyberware), **design** (taste/aesthetics — *not* the emphasis; keep it as
guidance), or **transformable** (extract the execution core into a governed pathway). Only execution /
transformable skills belong here. If it fits, **`cws-create/scaffold`** lays down the skeleton below.

## 1. Scaffold

```sh
python3 -m infra.tool.scaffold --skill myskill --name "My Skill" \
    --perk fetch:my_fetch:curl --perk store:my_store:python3
#   --perk  <perk_id>:<tool>[:<binary>]
```

This writes the whole skeleton with the standard lifecycle blueprint (`ready → prepared → verified →
executed`, where the executor records each step *as it runs*) and a snippet **stub** per tool. It
already **composes** out of the box — you fill in the snippets and vars.

## 2. The manifesto — the `${VAR}` template

```json
{
  "_perk": "fetch",
  "sequence": ["my_fetch"],                         // the tool-call order
  "tools": { "my_fetch": { "binary": "curl", "params": { "URL": "${URL}" } } },
  "env":   { "URL": "${URL}", "RECORD_STORE": "${record_store}" },   // universal runtime settings
  "requires": ["curl"]                              // the validator checks these are reachable
}
```

`${VAR}` placeholders are filled from the task-ledger's `vars` (and `record_store`). The `sequence`
becomes the compiled script's steps; `requires` is what the validator probes.

## 3. The contract — I/O + checks

```json
{
  "tool": "my_fetch",
  "inputs":  { "URL": { "type": "string", "required": true } },
  "outputs": { "body": { "path": "${RECORD_STORE}/response.body", "type": "file" } },
  "checks":  { "exit_zero": true, "output_exists": "${RECORD_STORE}/response.body" }
}
```

The validator checks `inputs.required` are present; the compiler emits the `output_exists` check after
the final step.

## 4. The snippet — the proven pathway

`src/<tool>.sh` is the tool's entry point (the framework runs `bash <tool>.sh`). It reads its env vars
and emits **one line of structured JSON** on stdout (the audit + debug log); keep it deterministic and
write artifacts under `$RECORD_STORE`.

**When the core is bash** (psql, curl, tar, git, …) — the logic lives in the `.sh`.

**When the core is another language** (Python, …) — keep the logic as its own standalone file and make
the `.sh` a thin **porter**. Don't bury logic in a `<<'PY'` heredoc — a standalone file is far easier
to read, lint, and update:

```
src/<tool>.py     # the core — inspect / lint / test / edit directly; reads its inputs from the env
src/<tool>.sh     # the porter
```

```bash
# src/<tool>.sh
set -euo pipefail
HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
exec python3 "$HERE/<tool>.py"
```

`scaffold.py` writes exactly this when a perk's binary is `python3` (see `skillChip/codebaseqc`, whose
`cbqc_*` tools are standalone `.py` cores behind thin porters).

## 5. Visualize, index + run

```sh
python3 -m infra.tool.visualize   --skill myskill          # → blueprint.{drawio,svg}
python3 -m infra.tool.skill_index --skill myskill          # → index.json (pin every file's sha256)
# fill ledger.json → task-ledger.json, then:
RUN=$(python3 -m infra.govern.runlog --ledger task-ledger.json)         # the grouped run dir
python3 -m infra.govern.validator --ledger task-ledger.json
python3 -m infra.govern.composer  --ledger task-ledger.json
python3 -m infra.govern.compiler  --ledger task-ledger.json             # writes $RUN/run.sh (+ run.{drawio,svg})
python3 -m infra.govern.oversight --script "$RUN/run.sh"
python3 -m infra.govern.executor  --script "$RUN/run.sh" --all          # the governed run
```

With a default `record_store` and no `-o`, the compiler groups every artifact for the run —
`run.sh`, `run.{drawio,svg}`, `.run.sh.bk`, `run-ledger.json`, the outputs, and a pointer-bearing
`task-ledger.json` — under **`~/cyberware_run_logs/<skill>__<perk>__<id>/`** (override with an explicit
`record_store`, or `$CYBERWARE_RUN_LOGS`). Open `$RUN/run.svg` to eyeball what will run before the
executor does.

## 6. Prove it — the in-skill self-test

Each perk carries its own proof: `perks/<perk>/test/case.json` — a **declarative** case run through the
**same governed channel** the agent uses (compile → executor → assert), so the skill verifies itself
rather than being trusted by its prose.

```json
{
  "requires": ["sqlite3"],                       // skip if a binary is absent; OR "skip": "<reason>"
  "setup":  ["sqlite3 demo.db 'CREATE TABLE …'"], // optional shell lines, cwd = the fixture dir
  "vars":   { "DB_FILE": "${FIXTURE}/demo.db", "QUERY": "SELECT 1" },
  "expect": { "outputs": ["query_result.txt"], "contains": { "query_result.txt": "1" } }
}
```

Ship input files under `test/fixture/` (pinned in the index) or build them in `setup`. `expect` supports
`exit` · `outputs` (exist) · `nonempty` · `contains` (substring) · `json` (subset). Run it:

```sh
python3 -m infra.tool.skilltest --skill myskill --perk fetch    # → [ok] / [skip] / [FAIL]
```

Re-run `skill_index --skill myskill` after adding the test so the `test/` files are pinned.
`tests/test_skill_selftests.py` discovers every case in CI and enforces that **every skill self-proves**;
a perk that can't run hermetically (network / live service / repo-mutating) ships a `"skip"` case so it
still carries — and documents — its proof.

## Conventions

- **Read-only by default.** A destructive pathway declares `destructive: true` and is gated by
  `OVERSIGHT_RULE` (waived only by an explicit `--approve`).
- **Structured output is the contract surface.** The JSON line is both the audit log and what the
  executor records (its hash) for tamper-evidence.
- **One perk = one proven way.** Multiple steps live in a perk's `sequence`; multiple *strategies* are
  separate perks.
