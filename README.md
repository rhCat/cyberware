# cyberware

**A verifiable governance runtime for skill execution.** Same infrastructure as the Cyberware
Alchemistry — L++ blueprints, contracts, compiled bash, audit ledgers — at a different angle: not
the Athenor service that powers the whole alchemistry workflow, but the **independent, local
enforcement layer**. The intelligence proposes; the framework validates, composes, compiles,
oversees, and is the **only channel that executes**.

Blueprints are [L++](https://github.com/rhCat/lpp) (the 4-axiom logic frame). Python is the glue —
because glue is what this needs.

> **Using cyberware as an agent?** Start with **[`cyberware.md`](cyberware.md)** — the operating guide:
> how to run a skill through the governed channel (validate → compose → compile → oversee → execute),
> how to grow the registry (`cws-create`, `cws-addperk`), and what you must never do.

## Two sides

```
USER SIDE — the skill registry              GOVERNANCE SIDE — the infrastructure
  skills/<skill>/                             infra/
    SKILL.md      context for intelligence      validator.py   claims in the ledger are real
    perks.json    the proven pathways           composer.py    L++ → TLC (no logical deadlock)
    blueprint.json  the action CFG (L++)        compiler.py    ledger+contracts+snippets → bash
    ledger.json   the form the LLM fills        oversight.py   enforce OVERSIGHT_RULE (push back)
    perks/<perk>/                               executor.py    the ONLY way to run — governs + audits
      metadata.json   rules · usage · limits    OVERSIGHT_RULE.json   no drop table/schema, …
      manifesto.json  ${VAR} template + seq     EXECUTOR_RULE.json    monitor-usage rules for the executor
      src/contracts.json   I/O + checks
      src/<tool>           the snippet
```

## The flow

```
SKILL.md ─► LLM fills ledger.json (the form, bounded by blueprint + perk manifesto)
            │
            ▼  task-ledger.json
        validator.py   ── claims real? (runtime reachable, dir exists + writable, host up)
            ▼
        composer.py    ── compile L++ from blueprint+ledger → TLC → no abstract deadlock
            ▼
        compiler.py    ── blueprint + contracts + snippets → ONE bash script (step-wise --run flags)
            ▼
        oversight.py   ── OVERSIGHT_RULE over the script (ast/regex/optional sub-agent) → pass | push back
            ▼
        executor.py    ── the governed run: registers metadata, .bk tamper-check, upstream-step check,
                          enforces EXECUTOR_RULE. The agent NEVER runs the script directly — only here.
```

## Why a skill = blueprint + perks

- **`blueprint.json`** is the skill's *general* behaviour as an L++ CFG — what the intelligence should
  *look out for* and *which logs to check*. Perks are **optional** in the blueprint.
- **Perks** are *predetermined, proven, viable pathways* — the concrete, contract-bound way to do a
  specific task. The blueprint says what to watch; a perk says exactly how to act. Every tool run emits
  **deterministic structured output** that is both the audit log and the debug log.

## The governance principle

The agent channels **all** work through `executor.py`. It is the chokepoint:
- every run's metadata is registered to a persistent ledger (who ran what, when, with which inputs);
- a `.<script>.bk` is taken on first run and re-checked every run — **if the script changed, it's flagged**
  (an agent editing a compiled step to bypass a contract is caught);
- **upstream steps are checked** — a step can't run if its predecessors didn't;
- `EXECUTOR_RULE.json` (usage monitors, limits) is enforced at the call boundary.

If the compiled script or a step's output was altered to bypass governance, the executor sees the drift
and refuses. That is the enforcement layer — the runtime *is* the rule.

## Quickstart

```sh
L=examples/pg_ops.select.task-ledger.json
python3 infra/validator.py  --ledger $L                          # claims real?
python3 infra/composer.py   --ledger $L                          # L++ → TLC, no deadlock
python3 infra/compiler.py   --ledger $L -o /tmp/run.sh           # → the step-wise bash
python3 infra/oversight.py  --script /tmp/run.sh                 # OVERSIGHT_RULE
python3 infra/executor.py   --script /tmp/run.sh --step 1        # governed run (the ONLY channel)
```

## Authoring + visualizing

```sh
# scaffold a new skill skeleton — composes out of the box; fill the snippets + vars
python3 infra/scaffold.py --skill myskill --name "My Skill" --perk fetch:my_fetch:curl --perk store:my_store:python3

# render a blueprint as draw.io XML + self-contained SVG (entry blue, terminal green)
python3 infra/visualize.py --skill pg_ops               # → skills/pg_ops/blueprint.{drawio,svg}
python3 infra/visualize.py --ledger task.json -o run    # annotated with the chosen perk's steps
```

**Every `compiler.py` run also drops `<script>.drawio` + `<script>.svg` beside the compiled bash**,
the operate step annotated with that task's actual tool sequence. The SVG renders in any browser —
the only fast way to eyeball what a compiled task will do before the executor runs it.

## Docs

**[→ live dashboard at rhcat.github.io/cyberware](https://rhcat.github.io/cyberware/)** — a static site
(auto-deployed by [`.github/workflows/pages.yml`](.github/workflows/pages.yml) on every push) to review
every skill — blueprint, perk flow, contracts, and snippet code — with the review documents below as
in-site tabs. Regenerate + serve locally:

```sh
python3 infra/build_site.py                  # → docs/site/data.js
python3 -m http.server -d docs/site 8765     # → http://localhost:8765
```

- [architecture](docs/architecture.md) — the two sides, the pipeline, the governance model
- [authoring](docs/authoring.md) — scaffold + the perk / manifesto / contract / snippet pattern
- [skills](docs/skills.md) — the catalog
- [spec](docs/SPEC.md) — the original specification
