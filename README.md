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

`executor.py` enforces this **in software**. The security ladder's **SV-3** rung makes the boundary
**kernel-enforced**: `infra/exec/` adds signed capability **grants**, the **exod** daemon (a separate OS
principal whose Ed25519 signature is the *only* status the ledger trusts — replacing the executor's
self-report), and a **bwrap SandboxProfile** that runs each step inside unshared kernel namespaces. The
refusals then hold **with the in-process scan disabled** — proven by the `cws-redteam` corpus (≥12 attacks
refused) and budgeted by `cws-bench`. See
[architecture.md](docs/architecture.md#the-kernel-enforced-execution-boundary-sv-3).

## Quickstart

```sh
L=examples/pg_ops.select.task-ledger.json
python3 -m infra.govern.validator  --ledger $L                          # claims real?
python3 -m infra.govern.composer   --ledger $L                          # L++ → TLC, no deadlock
python3 -m infra.govern.compiler   --ledger $L -o /tmp/run.sh           # → the step-wise bash
python3 -m infra.govern.oversight  --script /tmp/run.sh                 # OVERSIGHT_RULE
python3 -m infra.govern.executor   --script /tmp/run.sh --step 1        # governed run (the ONLY channel)
```

## Run the governed server (Docker)

A **signed** image of the govd governance server is published to GitHub Packages — pull and run an overseen
govd in one line (it bakes the chip, validates it at boot, and refuses to start on drift):

```sh
docker run --rm -p 5773:5773 ghcr.io/rhcat/cyberware:latest    # boots govd; prints a monitor token → http://127.0.0.1:5773/
docker run -p 5773:5773 -v cyberware-govd:/data/govd ghcr.io/rhcat/cyberware:latest   # persist the provenance ledger
```

Verify the image's signature (keyless cosign via GitHub OIDC — no key to manage):

```sh
cosign verify ghcr.io/rhcat/cyberware:latest \
  --certificate-identity-regexp 'https://github.com/rhCat/cyberware/.github/workflows/server-image.yml@.*' \
  --certificate-oidc-issuer https://token.actions.githubusercontent.com
```

Serve a **live** chip instead of the baked one: add `-e CLOUD_MODE=1` (clones `rhCat/skillChip` at boot and
refuses on drift). The image is the **governor** — it observes + governs and never executes; the agent runs the
blessed plan's porters from its own registry against it. Published on a `vN.N.N` tag (or on demand) by
[`server-image.yml`](.github/workflows/server-image.yml).

## Authoring + visualizing

```sh
# scaffold a new skill skeleton — composes out of the box; fill the snippets + vars
python3 -m infra.tool.scaffold --skill myskill --name "My Skill" --perk fetch:my_fetch:curl --perk store:my_store:python3

# render a blueprint as draw.io XML + self-contained SVG (entry blue, terminal green)
python3 -m infra.tool.visualize --skill pg_ops               # → skillChip/general/pg_ops/blueprint.{drawio,svg}
python3 -m infra.tool.visualize --ledger task.json -o run    # annotated with the chosen perk's steps
```

**Every `compiler.py` run also drops `<script>.drawio` + `<script>.svg` beside the compiled bash**,
the operate step annotated with that task's actual tool sequence. The SVG renders in any browser —
the only fast way to eyeball what a compiled task will do before the executor runs it.

## Local development

Skills live on the **chip**, so developing one means pointing the engine at *your* chip and iterating.
The engine resolves the chip from **`$CYBERWARE_SKILLCHIP`** (default `<repo>/skillChip`). Whatever the
source, `skill_index --check` runs at boot and govd **refuses to start on an unauthentic or drifted
chip** — you can't accidentally serve a broken cartridge.

**Native loop — edit → re-pin → serve (no Docker, tightest):**

```sh
export CYBERWARE_SKILLCHIP=$PWD/skillChip            # or any chip dir you're working in
# … edit a skill under $CYBERWARE_SKILLCHIP/<source>/<skill>/ …
python3 -m infra.tool.skill_index --skill <skill>   # re-pin the skill's authenticity index
python3 -m infra.tool.skill_index --chip            # roll it into chip_sha (a NEW skill: --chip --add <skill>)
python3 -m infra.tool.skilltest   --skill <skill>   # run its governed self-tests
python3 -m infra.govern.govd --mode local           # serve YOUR chip → http://127.0.0.1:5773/
```

Skip the re-pin and boot fails closed — authenticity catches the drift. See
[authoring.md](docs/authoring.md) for the perk / manifesto / contract / snippet / self-test pattern.

**Against the published image — mount your local chip** (same governor, your cartridge, no rebuild):

```sh
docker run -p 5773:5773 -v $PWD/skillChip:/app/skillChip ghcr.io/rhcat/cyberware:latest
```

**Against a fork or dev branch** — clone it live at boot (good for a teammate or CI):

```sh
docker run -p 5773:5773 -e CLOUD_MODE=1 \
  -e CLOUD_SOURCE=https://github.com/you/skillChip.git -e CLOUD_SOURCE_TAG=my-branch \
  ghcr.io/rhcat/cyberware:latest
# private fork: add -e CLOUD_SOURCE_TOKEN=…   (GIT_ASKPASS-only — never logged or persisted)
```

| pointer | style | rebuild? | best for |
|---|---|---|---|
| `$CYBERWARE_SKILLCHIP` | native | no | editing skills locally (tightest loop) |
| `-v …:/app/skillChip` | container | no | testing your chip in the real image |
| `CLOUD_MODE` + `CLOUD_SOURCE` | container | no | a fork / branch / CI |

Either side ahead of the other is **reported, never silent**: a skill your chip has but the governor
doesn't → claims `reject: unknown_skill_perk` and discovery tags it `unverified`; a local edit that
diverges from the governed hash → `drift`; the governor's own copy failing its index → `server_drift`.

## Tests

The infra is covered by a real suite under [`tests/`](tests/) — the governance behavior is pinned, so
*verifiable* applies to the verifier too:

- **unit** — `runlog` (run-dir resolution), `oversight.scan` (deny-list + hardened patterns),
  `compiler` (script shape, var quoting, gate-binding + resolved contract), `composer` (the structural
  deadlock check actually *catches* a broken blueprint), `scaffold`, `visualize` (well-formed diagrams).
- **integration** — the executor channel: tamper snapshot + drift refusal, **in-channel oversight**
  refuse/waive, the upstream gate, step validation, provenance; and the full
  validate→compose→compile→oversee→execute pipeline.
- **per-perk contract** — every one of the 133 perks (across 38 skills) compiles to a clean, consistent,
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

**[→ the homepage at cyberware.systems](https://cyberware.systems/)** + the live **[registry dashboard](https://cyberware.systems/dashboard.html)** — a static site
(auto-deployed by [`.github/workflows/pages.yml`](.github/workflows/pages.yml) on every push) to review
every skill — blueprint, perk flow, contracts, and snippet code — with the review documents below as
in-site tabs. It is **self-discovering**: the page fetches the real registry at runtime (no build step,
no baked `data.js`), so it always reflects the current skills. Preview locally (assemble like the deploy,
then serve):

```sh
D=$(mktemp -d); cp docs/site/index.html "$D"; cp -r skillChip "$D"; mkdir "$D/docs"; cp docs/*.md "$D/docs"; cp cyberware.md "$D"
cp infra/document/pipeline.blueprint.svg "$D/pipeline.svg"; cp infra/document/pipeline.blueprint.json "$D/pipeline.blueprint.json"
python3 -c "import os,json; r='skillChip'; flat=[{'name':d,'dir':d} for d in os.listdir(r) if os.path.isfile(os.path.join(r,d,'perks.json'))]; nested=[{'name':s,'dir':d+'/'+s} for d in os.listdir(r) if os.path.isdir(os.path.join(r,d)) for s in os.listdir(os.path.join(r,d)) if os.path.isfile(os.path.join(r,d,s,'perks.json'))]; json.dump(sorted(flat+nested, key=lambda e:e['name']), open('$D/skills.json','w'))"
python3 -m http.server -d "$D" 8765           # → http://localhost:8765
```

- [governed-vs-free](docs/governed-vs-free.md) — the thesis: free up to the gate, accountable past it — why cyberware governs at the moment of commitment
- [architecture](docs/architecture.md) — the skill-as-package, the two execution planes, governance, authenticity, self-proof
- [governance-service](docs/governance-service.md) — **govd**: the control/audit plane, discovery (`/catalog`), the WebSocket, the dashboard
- [authoring](docs/authoring.md) — scaffold + the perk / manifesto / contract / snippet / self-test pattern
- [skills](docs/skills.md) — the catalog (38 skills)
- [SKILL.md](SKILL.md) — the agent contract: discover → claim → run the blessed plan → review the verdict
- [spec](docs/SPEC.md) — the original specification
