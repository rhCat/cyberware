# cyberware — operating guide for the agent

> **This is the governing document.** If you are an agent (an LLM) using cyberware, read this first.
> It tells you how to run skills through the governed channel — and what you must never do.

## The model — you propose, the framework governs

cyberware is a **verifiable governance runtime for skill execution**. You do **not** run commands
ad-hoc. You write a small JSON form — a **task-ledger** — that names a **skill**, a **perk**, and the
inputs, and the framework **validates → composes → compiles → oversees → executes** it.
**`infra/executor.py` is the only channel that runs.** The runtime *is* the rule: bypass it and you
leave a visible gap (an unrecorded run, a tamper mismatch, a skipped step).

## The one rule

Channel **all** execution through `infra/executor.py`. Never:

- run a snippet (`skills/<skill>/perks/<perk>/src/<tool>.sh`) directly;
- edit a compiled `run.sh` to slip past a contract — the `.bk` tamper-check snapshots it on first run
  and **refuses** on drift;
- skip a stage, or run a step whose upstream steps have not run (the executor refuses).

If a task needs a destructive action, it **pushes back at oversight**; it proceeds only with an
explicit, logged `--approve`.

## How to run a skill — the loop

**1. Pick a skill + perk.** Browse `skills/`, or the [dashboard](https://rhcat.github.io/cyberware/).
Read the skill's `SKILL.md` and the perk's `perks/<perk>/metadata.json` (rules · usage · limitation ·
minimal_example) to learn the inputs.

**2. Write the task-ledger** — copy `skills/<skill>/ledger.json` → `task-ledger.json` and fill only
these fields:

```json
{
  "skill": "<skill>",
  "perk": "<perk>",
  "record_store": "<absolute dir for outputs + the run-ledger>",
  "vars": { "...": "the vars the perk's manifesto declares" }
}
```

**3. Run the pipeline** (in order):

```sh
L=task-ledger.json
python3 infra/validator.py --ledger "$L"                 # claims real?
python3 infra/composer.py  --ledger "$L"                 # L++ -> TLC: no deadlock
python3 infra/compiler.py  --ledger "$L" -o run.sh       # -> step-wise bash (+ run.{drawio,svg})
python3 infra/oversight.py --script run.sh               # OVERSIGHT_RULE (push back on danger)
python3 infra/executor.py  --script run.sh --all         # THE governed run (the ONLY channel)
```

**4. Read the result.** Each tool prints **one line of structured JSON** (the audit + debug log); every
step is appended to `run-ledger.json` under your `record_store` as it runs.

## What each stage enforces

| stage | enforces |
|---|---|
| `validator` | record_store writable · runtimes + required binaries reachable · required vars present |
| `composer` | the L++ blueprint cannot deadlock (TLC, with a structural fallback) |
| `compiler` | the perk's tool sequence + contracts → one step-wise bash; each tool a gated step + its contract check |
| `oversight` | the script clears `OVERSIGHT_RULE`; destructive/dangerous patterns push back unless `--approve`d |
| `executor` | `.bk` tamper-check · upstream-step gate · run-ledger provenance. **THE channel.** |

## Growing the registry — use the internals, don't hand-roll

- **A new skill?** Run **`cws-create/evaluate`** first. It classifies the idea: **execution** (a
  deterministic tool/pathway — fits cyberware), **design** (taste/aesthetics — *not* the emphasis; keep
  it as guidance), **transformable** (extract the execution core). Only execution skills belong. Then
  **`cws-create/scaffold`** lays down the skeleton.
- **A new perk for an existing skill?** Use **`cws-addperk`** — `evaluate` (exists? generalizable?
  scope?) → `apply` (branch → formulate + validate → open a PR). **The merge is never automatic** — you
  review and merge on approval.

## The boundary

Build **tool skills** — operational pathways (query, fetch, build, scan, archive, tag, …). **Not**
**design / taste skills** (palette, typography, "no purple fade"). cyberware governs *deterministic
execution*, not aesthetics. A taste skill stays guidance; it does not become a governed pathway.

## Anatomy + conventions

A skill is `skills/<skill>/`:

```
SKILL.md       context for you — what it does, what to watch, which logs to check
blueprint.json the L++ lifecycle: ready → prepared → verified → executed  (executed = terminal)
perks.json     the proven pathways (id · summary · tools · destructive?)
ledger.json    the FORM you fill → task-ledger.json
perks/<perk>/
  metadata.json   rules · usage · limitation · minimal_example
  manifesto.json  the ${VAR} template: sequence (tool order) · tools · env · requires
  src/contracts.json   the tool's I/O + checks
  src/<tool>.sh        the entry point (bash-core logic here; other-language core = standalone file + thin porter)
```

- **The `.sh` is the entry point.** Bash-core logic lives in it; for Python (etc.) keep the core a
  standalone `<tool>.py` behind a thin `.sh` porter — never bury logic in a `<<'PY'` heredoc.
- **Structured JSON output is the contract surface** — the executor records its hash for tamper-evidence.
- **Recording is part of executing** — each step is written to the run-ledger *as it runs*, which is why
  the lifecycle ends at `executed`, not a separate `recorded`.

## More

[`docs/architecture.md`](docs/architecture.md) · [`docs/authoring.md`](docs/authoring.md) ·
[`docs/skills.md`](docs/skills.md) · [`docs/SPEC.md`](docs/SPEC.md) · the live
[dashboard](https://rhcat.github.io/cyberware/) (blueprints, perk flows, contracts, code).
