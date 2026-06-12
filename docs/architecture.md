# Architecture

cyberware is a **verifiable governance runtime for skill execution** — a subset of the Cyberware
Alchemistry at a different angle, and the local instance of the
[Zero Trust Framework](https://github.com/rhCat/trust-model-reflection)'s delegation pillars: the
intelligence *proposes*, the framework *validates / composes / compiles / oversees*, and is the only
channel that *executes*. Blueprints are [L++](https://github.com/rhCat/lpp); Python is the glue.

## Two sides

cyberware is the **engine**; the skills are a separate **cartridge** — the [**skillChip**](https://github.com/rhCat/skillChip), its own git repo vendored here as the `skillChip/` submodule (the "feed-stock cartridge"). The engine reads every skill from the chip; the chip carries no governance of its own.

| side | what | where |
|---|---|---|
| **skillChip** | the cartridge — the skills, each a self-contained, verifiable **package** (context · lifecycle · pathways · contracts · authenticity · proof). A separate repo, vendored as a submodule. | `skillChip/<skill>/` |
| **governance** | the engine — the infrastructure that validates · composes · compiles · oversees · executes — and governs/audits as a service | `infra/` |

The chip is located by `infra/registry.py` (`registry.SKILLCHIP`): the hardcoded default `<repo>/skillChip`, overridable with **`$CYBERWARE_SKILLCHIP`**. The chip is **self-describing** — `skillChip/index.json` is its **manifest**: every skill with its `skill_sha`, plus a roll-up `chip_sha`, which cyberware retrieves to discover + verify the whole chip as a unit (each skill keeps its own `index.json` for file-level authenticity). Swap the chip — point `$CYBERWARE_SKILLCHIP` elsewhere — and the same engine governs a different feed-stock, unchanged.

`infra/` is a Python package, invoked as `python3 -m infra.<pkg>.<module>`:

- **`infra/govern/`** — the pipeline (`validator`, `composer`, `compiler`, `oversight`, `executor`,
  `runlog`) **and the service plane** (`govd`, `govd_client`).
- **`infra/tool/`** — registry tooling: `visualize` (blueprint → drawio/SVG), `skill_index`
  (authenticity), `skilltest` (in-skill self-tests), `scaffold` (new skills).
- **`infra/document/`** — the framework's own formal artifacts (the pipeline blueprint, the rule files).

## A skill is a package

A skill is **not a prose description you trust** — it is a self-contained unit you can verify and build
upon. `skillChip/<skill>/`:

```
SKILL.md            context: what it does, what to watch, which logs to check
blueprint.json      the L++ lifecycle (ready → prepared → verified → executed)
perks.json          the proven pathways (id · summary · tools · destructive?)
ledger.json         the form the agent fills → task-ledger.json
index.json          per-file sha256 + a roll-up skill_sha — the authenticity manifest
perks/<perk>/
  metadata.json       rules · usage · limitation · minimal_example
  manifesto.json      the ${VAR} template: tool sequence · env · requires
  src/contracts.json  the tool's I/O + checks
  src/<tool>.sh       the entry point (a Python core sits behind a thin .sh porter)
  test/case.json      the perk's OWN governed self-test (+ a fixture/ dir)
```

Six mechanically-connected blocks, each verifiable rather than asserted: the **blueprint** is
model-checked (TLC), the **contract** is enforced at execution, the **index** pins every file, the
**test** proves the perk through the real channel. Add or change any block and the skill's `skill_sha`
changes — a skill's identity *is* the hash of its parts.

## Two execution planes

The same governance runs two ways, sharing `validator` / `composer` / `compiler` / `oversight` /
`executor`:

**1 · Local pipeline** (in-process) — the agent runs the stages itself, end to end:

```
SKILL.md ─► LLM fills the form → task-ledger.json
            │
   validator.py   claims real? — record_store writable, runtime + required binaries reachable,
            │                    contract's required inputs present, host reachable (soft)
   composer.py    L++ → TLA+ → TLC — no abstract deadlock (non-terminal sink); structural fallback
            │                        (reachability / terminal-reachable) when no JRE/tla2tools
   compiler.py    blueprint + manifesto + contracts + snippets → ONE step-wise bash + run.{drawio,svg}
            │                        (the diagram annotated with this task's tool sequence)
   oversight.py   OVERSIGHT_RULE over the script — destructive/dangerous patterns push back; approvable
            │                        rules waived only by an explicit, logged --approve (pre-flight view)
   executor.py    THE channel — .bk tamper-check, IN-CHANNEL oversight scan (refuses on violations;
                                 waivers ledger-recorded), upstream gate, run-ledger provenance, EXECUTOR_RULE
```

**2 · govd — the service plane** (`infra/govern/govd.py`, a control/audit plane). **No data crosses the
boundary.** The agent sends a **claim** (skill, perk, var **KEYS** — never values, files, or secrets);
govd checks it against its **own** trusted registry, runs compose + TLC, and blesses a **value-free,
code-free PLAN** (tool sequence + each snippet's sha256 + a `${VAR}` wrapper), pinning the plan's sha256.
The agent binds its vars **locally**, runs the porters+cores **from its own registry**, and reports
**status** over a per-run WebSocket; govd owns the provenance ledger and monitors the plan **hash**.
Secrets are never plaintext — a `*_FILE` pointer is read at runtime via `cat`. Full detail:
[`governance-service.md`](governance-service.md).

> This pipeline is itself captured as a formal **L++ blueprint** —
> [`infra/document/pipeline.blueprint.json`](../infra/document/pipeline.blueprint.json) — so the framework
> is described in its own formalism (the **ouroboros**); the dashboard renders it.

## The governance model

`executor.py` is the chokepoint. The agent channels **all** work through it:

1. **Tamper-check** — the script is snapshotted to `.<script>.bk` on first run; if it later drifts
   (an agent editing a compiled step to slip past a contract), the run is **refused**.
2. **In-channel oversight** — the same `OVERSIGHT_RULE` scan runs inside the executor before any step;
   unwaived violations are **refused** (exit 7) and recorded. Skipping the `oversight.py` pre-flight
   does not skip the gate; `--approve` waivers are explicit and ledger-recorded.
3. **Upstream gate** — a step cannot run unless its predecessors are recorded as run.
4. **Provenance ledger** — every run (ts, step, exit, duration, output hash, output tail) is appended
   to `run-ledger.json` under the record_store. Out-of-band runs leave a hole in the chain.
5. **EXECUTOR_RULE** — timeout and other call-boundary limits.

The runtime *is* the rule: you cannot bypass governance without leaving a visible gap (an unrecorded
run, a `.bk` mismatch, a missing upstream step). govd extends the same idea across a boundary — the
per-run session token gates the WebSocket and the ledger read; a `step_result` is recorded only after a
`grant` for that exact step with the blessed `plan_sha`.

## Authenticity — the skill's identity

Each skill's `index.json` pins the sha256 of every file in that skill plus a roll-up `skill_sha`
(`infra/tool/skill_index`), and the chip's own `skillChip/index.json` manifest rolls those up again into a
`chip_sha` over the whole cartridge. It is the reference both planes verify against, so a skill's version —
and the chip as a unit — is checkable **without passing files back and forth**; only hashes cross the wire:

- **build-time gate** — the Docker image runs `skill_index --check --all` right after copying the
  registry, so a drifted index (a stripped file, an un-regenerated hash) **fails the build**.
- **govd** won't bless a registry that doesn't match its index, and pins the perk's closure hashes in
  the plan; **the agent** verifies its own registry against those hashes before running.
- **discovery** — `GET /catalog` is value-free (skills · perks · var-KEYS · `skill_sha` · verified).
  The agent's client (`govd_client.discover`) compares its local `skill_sha` to govd's and tags each
  skill **verified** (matches the blessed image), **drift** (diverged), or **unverified** (a *new* skill
  the image has never seen — visible but not governable until added and the image rebuilt).

## Self-proof — each skill carries its own test

A perk's `test/case.json` is a **declarative** case — `vars`, a `fixture/` dir, `requires`, and an
`expect` block (`exit` / `outputs` / `nonempty` / `contains` / `json`) — run through the **same governed
channel the agent uses** (`infra/tool/skilltest`: compile → executor → assert). Because the `test/` files
are pinned in `index.json`, the proof is **part of the skill's tamper-evident identity** and cannot drift
from the tool. `tests/test_skill_selftests.py` discovers every case, runs it, and enforces the invariant
that **every skill self-proves**; non-hermetic perks (network, live service, repo-mutating) ship a `skip`
case so the skill still carries — and documents — its proof.

## The blueprint (L++)

Every tool skill shares one **perk-agnostic lifecycle**:

```
ready → prepared → verified → executed        (executed = terminal)
```

The terminal is **executed**, not "recorded" — recording is part of *executing*: the executor writes
each step to the run-ledger **as it runs**, not in a separate phase after. `safety_invariants` encode
this — chiefly **`governed_execution_only`** (a task reaches `executed` only through `executor.py`) and
**`record_during_execution`**, plus the skill's own guardrails. Perks are *optional* in the blueprint:
the blueprint says what to watch and which logs to check; a perk supplies the concrete, contract-bound
*how*. The governance pipeline above is itself captured as a blueprint.

Blueprints render as flowcharts (`infra/tool/visualize.py` → drawio + SVG): **state** = rectangle,
**transition** = line, **gate** = diamond (with its `✓ pass` / `✗ fail → exit·log` branches), **action**
= the predefined-process shape showing its `compute_unit`. The dashboard draws them in a cyberpunk theme;
its Flow tab renders the **task** blueprint — the perk's actual gated sequence, value-free.

## The agent contract

The loadable entry skill is the root [`SKILL.md`](../SKILL.md): the five-step loop an agent follows —
**discover** what's governed (`/catalog`) → emit the **claim** (its only output; never the commands) →
govd blesses → **run** the blessed plan from the agent's own registry → **review** the verdict. The
agent authors no commands; the skill code is the registry's, blessed by hash.

## Relationship to the rest

cyberware is **not Athenor** (the hosted service that powers the whole Cyberware Alchemistry
workflow). It is the standalone, local enforcement layer — the same verifiable infrastructure
(L++ blueprints, contracts, compiled bash, audit ledgers, authenticity indexes, in-skill proofs),
pointed at general skill execution.
