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

## Two sides — engine + cartridge

cyberware is the **engine**; the skills are the **cartridge** — the [**skillChip**](https://github.com/rhCat/skillChip), a separate repo vendored here as the `skillChip/` **git submodule** (the feed-stock cartridge). The engine reads the chip from `registry.SKILLCHIP` — `<repo>/skillChip` by default, or wherever **`$CYBERWARE_SKILLCHIP`** points; swap the chip and the same engine governs a different feed-stock. The chip is self-describing: `skillChip/index.json` is its manifest (every skill + `skill_sha`, plus a roll-up `chip_sha`). The govd container **validates the chip at boot** and can acquire it two ways: baked-local (default) or **`CLOUD_MODE=1`** — a live clone of `CLOUD_SOURCE` at `CLOUD_SOURCE_TAG` (token via `CLOUD_SOURCE_TOKEN` for a private source); see [governance-service.md](docs/governance-service.md).

```
THE CARTRIDGE — the skillChip (submodule)   THE ENGINE — the governance infrastructure
  skillChip/<skill>/                          infra/
    SKILL.md      context for intelligence      govern/   validator · composer · compiler · oversight
    perks.json    the proven pathways                     executor · runlog · govd · govd_client
    blueprint.json  the action CFG (L++)                  OVERSIGHT_RULE.json · EXECUTOR_RULE.json
    ledger.json   the form the LLM fills                  govd_config.json · govd_dashboard.html
    index.json    per-file sha256 + skill_sha   tool/     scaffold · visualize · skill_index · skilltest
    perks/<perk>/                               document/ pipeline.blueprint.{json,drawio,svg}
      metadata.json   rules · usage · limits
      manifesto.json  ${VAR} template + seq
      src/contracts.json   I/O + checks
      src/<tool>           the snippet
      test/case.json       the perk's OWN governed self-test (pinned in index.json)
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
        oversight.py   ── OVERSIGHT_RULE over the script (regex/optional sub-agent) → pass | push back
            ▼
        executor.py    ── the governed run: .bk tamper-check, IN-CHANNEL oversight scan (refuses on
                          violations; --approve waivers are ledger-recorded), upstream-step check,
                          run-ledger provenance, EXECUTOR_RULE. The agent NEVER runs the script
                          directly — only here.
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
- **the OVERSIGHT_RULE scan runs in-channel** before any step — running `oversight.py` first is
  pre-flight visibility, but the executor refuses unwaived violations regardless; `--approve` waivers
  are explicit and ledger-recorded;
- **upstream steps are checked** — a step can't run if its predecessors didn't;
- `EXECUTOR_RULE.json` (usage monitors, limits) is enforced at the call boundary.

If the compiled script or a step's output was altered to bypass governance, the executor sees the drift
and refuses. That is the enforcement layer — the runtime *is* the rule.

## Quickstart

```sh
L=examples/pg_ops.select.task-ledger.json
python3 -m infra.govern.validator  --ledger $L                          # claims real?
python3 -m infra.govern.composer   --ledger $L                          # L++ → TLC, no deadlock
python3 -m infra.govern.compiler   --ledger $L -o /tmp/run.sh           # → the step-wise bash
python3 -m infra.govern.oversight  --script /tmp/run.sh                 # OVERSIGHT_RULE
python3 -m infra.govern.executor   --script /tmp/run.sh --step 1        # governed run (the ONLY channel)
```

## Authoring + visualizing

```sh
# scaffold a new skill skeleton — composes out of the box; fill the snippets + vars
python3 -m infra.tool.scaffold --skill myskill --name "My Skill" --perk fetch:my_fetch:curl --perk store:my_store:python3

# render a blueprint as draw.io XML + self-contained SVG (entry blue, terminal green)
python3 -m infra.tool.visualize --skill pg_ops               # → skillChip/pg_ops/blueprint.{drawio,svg}
python3 -m infra.tool.visualize --ledger task.json -o run    # annotated with the chosen perk's steps
```

**Every `compiler.py` run also drops `<script>.drawio` + `<script>.svg` beside the compiled bash**,
the operate step annotated with that task's actual tool sequence. The SVG renders in any browser —
the only fast way to eyeball what a compiled task will do before the executor runs it.

## Tests

The infra is covered by a real suite under [`tests/`](tests/) — the governance behavior is pinned, so
*verifiable* applies to the verifier too:

- **unit** — `runlog` (run-dir resolution), `oversight.scan` (deny-list + hardened patterns),
  `compiler` (script shape, var quoting, gate-binding + resolved contract), `composer` (the structural
  deadlock check actually *catches* a broken blueprint), `scaffold`, `visualize` (well-formed diagrams).
- **integration** — the executor channel: tamper snapshot + drift refusal, **in-channel oversight**
  refuse/waive, the upstream gate, step validation, provenance; and the full
  validate→compose→compile→oversee→execute pipeline.
- **per-perk contract** — every one of the 41 perks (across 22 skills) compiles to a clean, consistent,
  oversight-clear script.
- **in-skill self-tests** — each skill carries its OWN proof: `perks/<perk>/test/case.json`, run
  end-to-end **through the governed executor** on shipped fixtures (`infra.tool.skilltest`, discovered by
  `test_skill_selftests.py`); non-hermetic perks (network / live service / repo-mutating) ship a `skip`
  case. The proof is **pinned in each skill's `index.json`**, so it can't drift from the tool.

```sh
pytest tests          # ~250 tests, a few seconds
```

CI runs this and **gates on it** (`.github/workflows/codeqc.yml`, regenerated by the `ci-codeqc` skill
itself — the ouroboros).

## Docs

**[→ live dashboard at rhcat.github.io/cyberware](https://rhcat.github.io/cyberware/)** — a static site
(auto-deployed by [`.github/workflows/pages.yml`](.github/workflows/pages.yml) on every push) to review
every skill — blueprint, perk flow, contracts, and snippet code — with the review documents below as
in-site tabs. It is **self-discovering**: the page fetches the real registry at runtime (no build step,
no baked `data.js`), so it always reflects the current skills. Preview locally (assemble like the deploy,
then serve):

```sh
D=$(mktemp -d); cp docs/site/index.html "$D"; cp -r skillChip "$D"; mkdir "$D/docs"; cp docs/*.md "$D/docs"; cp cyberware.md "$D"
python3 -c "import os,json; json.dump(sorted(d for d in os.listdir('skillChip') if os.path.exists(f'skillChip/{d}/perks.json')), open('$D/skills.json','w'))"
python3 -m http.server -d "$D" 8765           # → http://localhost:8765
```

- [architecture](docs/architecture.md) — the skill-as-package, the two execution planes, governance, authenticity, self-proof
- [governance-service](docs/governance-service.md) — **govd**: the control/audit plane, discovery (`/catalog`), the WebSocket, the dashboard
- [authoring](docs/authoring.md) — scaffold + the perk / manifesto / contract / snippet / self-test pattern
- [skills](docs/skills.md) — the catalog (22 skills)
- [SKILL.md](SKILL.md) — the agent contract: discover → claim → run the blessed plan → review the verdict
- [spec](docs/SPEC.md) — the original specification
