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
            │                        rules waived only by an explicit, logged --approve
   executor.py    THE channel — .bk tamper-check, upstream gate, run-ledger provenance, EXECUTOR_RULE
```

> This same pipeline is captured as a formal **L++ blueprint** — [`infra/pipeline.blueprint.json`](../infra/pipeline.blueprint.json) — so the framework is described in its own formalism (the **ouroboros**). The dashboard renders it at the top of this page; each gate's `✗ fail` route is the stage refusing and logging.

## The governance model

`executor.py` is the chokepoint. The agent channels **all** work through it:

1. **Tamper-check** — the script is snapshotted to `.<script>.bk` on first run; if it later drifts
   (an agent editing a compiled step to slip past a contract), the run is **refused**.
2. **Upstream gate** — a step cannot run unless its predecessors are recorded as run.
3. **Provenance ledger** — every run (ts, step, exit, duration, output hash, output tail) is appended
   to `run-ledger.json` under the record_store. Out-of-band runs leave a hole in the chain.
4. **EXECUTOR_RULE** — timeout and other call-boundary limits.

The runtime *is* the rule: you cannot bypass governance without leaving a visible gap (an unrecorded
run, a `.bk` mismatch, a missing upstream step).

## The blueprint (L++)

Every tool skill shares one **perk-agnostic lifecycle**:

```
ready → prepared → operated → verified → recorded        (recorded = terminal)
```

with `safety_invariants` that the conductor cannot violate — chiefly **`governed_execution_only`**
(tools run only through `executor.py`) and the skill's own guardrails (e.g. `no_destructive_without_
approval`). Perks are *optional* in the blueprint: the blueprint says what to watch and which logs to
check; a perk supplies the concrete, contract-bound *how*.

## Relationship to the rest

cyberware is **not Athenor** (the hosted service that powers the whole Cyberware Alchemistry
workflow). It is the standalone, local enforcement layer — the same verifiable infrastructure
(L++ blueprints, contracts, compiled bash, audit ledgers), pointed at general skill execution.
