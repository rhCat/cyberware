# Authoring a skill

A skill is a directory under `skills/`. Its anatomy:

```
skills/<skill>/
  SKILL.md                 context for the intelligence — what it does, what to watch, which logs to check
  blueprint.json           the L++ CFG (the perk-agnostic lifecycle + safety_invariants)
  perks.json               the proven pathways (id, summary, tools, destructive?)
  ledger.json              the FORM the LLM fills → task-ledger.json
  blueprint.{drawio,svg}   generated diagrams (by visualize.py)
  perks/<perk>/
    metadata.json          description · rules · usage · limitation · minimal_example
    manifesto.json         the ${VAR} template: `sequence` (tool order) + `tools` + `env` + `requires`
    src/
      contracts.json       the tool's I/O + checks (required inputs, output_exists)
      <tool>.sh            the proven pathway — emits deterministic structured JSON (audit + debug log)
```

## 0. Evaluate first (the on-ramp)

Before authoring, run the idea through **`cws-create/evaluate`** — it classifies it as **execution**
(a tool/pathway — fits cyberware), **design** (taste/aesthetics — *not* the emphasis; keep it as
guidance), or **transformable** (extract the execution core into a governed pathway). Only execution /
transformable skills belong here. If it fits, **`cws-create/scaffold`** lays down the skeleton below.

## 1. Scaffold

```sh
python3 infra/scaffold.py --skill myskill --name "My Skill" \
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

`scaffold.py` writes exactly this when a perk's binary is `python3` (see `skills/codebaseqc`, whose
`cbqc_*` tools are standalone `.py` cores behind thin porters).

## 5. Visualize + run

```sh
python3 infra/visualize.py --skill myskill            # → blueprint.{drawio,svg}
# fill ledger.json → task-ledger.json, then:
python3 infra/validator.py --ledger task-ledger.json
python3 infra/composer.py  --ledger task-ledger.json
python3 infra/compiler.py  --ledger task-ledger.json -o run.sh   # + run.{drawio,svg}
python3 infra/oversight.py --script run.sh
python3 infra/executor.py  --script run.sh --all                 # the governed run
```

Every `compiler.py` run also drops `run.drawio` + `run.svg` (the operate step annotated with this
task's tools) — open the SVG in a browser to eyeball what will run before the executor does.

## Conventions

- **Read-only by default.** A destructive pathway declares `destructive: true` and is gated by
  `OVERSIGHT_RULE` (waived only by an explicit `--approve`).
- **Structured output is the contract surface.** The JSON line is both the audit log and what the
  executor records (its hash) for tamper-evidence.
- **One perk = one proven way.** Multiple steps live in a perk's `sequence`; multiple *strategies* are
  separate perks.
