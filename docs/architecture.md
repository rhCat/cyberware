# Architecture

cyberware is a **verifiable governance runtime for skill execution** — a subset of the Cyberware
Alchemistry at a different angle, and the local instance of the
[Zero Trust Framework](https://github.com/rhCat/trust-model-reflection)'s delegation pillars: the
intelligence *proposes*, the framework *validates / composes / compiles / oversees*, and is the only
channel that *executes*. Blueprints are [L++](https://github.com/rhCat/lpp); Python is the glue.

## Two sides

| side | what | where |
|---|---|---|
| **user** | the skill registry — a skill's context, logic, and proven pathways | `skills/<skill>/` |
| **governance** | the infrastructure that validates, composes, compiles, oversees, executes | `infra/` |

## The pipeline

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

> This same pipeline is captured as a formal **L++ blueprint** — [`infra/pipeline.blueprint.json`](../infra/pipeline.blueprint.json) — so the framework is described in its own formalism (the **ouroboros**). The dashboard renders it at the top of this page; each gate's `✗ fail` route is the stage refusing and logging.

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
run, a `.bk` mismatch, a missing upstream step).

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
*how*. The governance pipeline above is itself captured as a blueprint —
[`infra/pipeline.blueprint.json`](../infra/pipeline.blueprint.json), rendered at the top of this page.

Blueprints render as flowcharts (`infra/tool/visualize.py` → drawio + SVG): **state** = rectangle,
**transition** = line, **gate** = diamond (with its `✓ pass` / `✗ fail → exit·log` branches), **action**
= the predefined-process shape showing its `compute_unit`. The dashboard draws them in a cyberpunk theme.

## Relationship to the rest

cyberware is **not Athenor** (the hosted service that powers the whole Cyberware Alchemistry
workflow). It is the standalone, local enforcement layer — the same verifiable infrastructure
(L++ blueprints, contracts, compiled bash, audit ledgers), pointed at general skill execution.
