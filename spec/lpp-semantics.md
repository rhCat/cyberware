# cyberware — L++ semantics (`spec/lpp-semantics.md`)

> Task **P0-T06**. Defines the meaning of an L++ blueprint — its evaluation order, its invariants, its
> failure semantics, the composition operators, and the relationship between the *checked abstraction*
> and the *enforced data plane*. Normative for `composer` (the abstraction), `compiler`/`executor` (the
> data plane), and every skill's `blueprint.json`.

## 1. The blueprint

A blueprint is a state machine: `states`, an `entry_state`, `terminal_states`, `transitions`
(`from → to` with a `trigger`, an `action`, and a `gate`), `actions` (each a `compute_unit`), and
`safety_invariants`. The shared tool-skill lifecycle is `ready → prepared → verified → executed`, and
`executed` **MUST** be terminal.

## 2. Evaluation order

Evaluation **MUST** begin at `entry_state`. A transition fires only when its `gate` predicate holds; if no
gate of any outgoing transition holds, the state is a sink. A non-terminal sink is a **deadlock** and
**MUST** be rejected by the checker, and every non-terminal state **MUST** be able to reach a terminal
state.

## 3. Invariant meaning

A `safety_invariant` is a predicate that **MUST** hold in every reachable state. `governed_execution_only`
(a task reaches `executed` only through `executor.py`) and `record_during_execution` (each step is written
to the run-ledger as it runs) are the load-bearing ones; a blueprint whose invariants do not hold under
the model checker **MUST NOT** be admitted.

## 4. Failure semantics

A gate that fails **MUST** halt the transition and record the failure (an `exit` code + a log reference),
never silently fall through. A modeled transition **MAY** declare `on_fail` as one of `to` (route to a
state), `retry(n)` (bounded), or `compensate(action)` (a saga step); an unbounded retry **MUST NOT** be
modeled, because it is a liveness violation (no progress).

## 5. Composition operators

Workflows compose blueprints under four operators, whose semantics are defined here and whose product
automaton the checker verifies (the workflow algebra, P4): **`seq`** (ordered; each step's terminal is the
next step's entry), **`par`** (concurrent; the join waits for all branches and **MUST** be free of mutual
wait), **`choice`** (exactly one branch by a gate), and **`saga`** (a sequence whose failure runs the
declared compensations in reverse). A composed workflow **MUST** carry a `workflow_sha` over its canonical
form.

## 6. Refinement — checked abstraction vs enforced data plane

The blueprint is a **checked abstraction**: `composer` lifts it to TLA+ and a checker proves it
deadlock-free and invariant-respecting over the abstract state. The **enforced data plane** is the
compiled script run through `executor.py` against the perk's `contracts.json`. The abstraction **MUST**
over-approximate the data plane (every concrete step maps to a modeled action), and the data plane
**MUST** enforce what the abstraction only assumes — the contract's I/O and checks at the instant of
execution. A property proved on the abstraction is a guarantee only insofar as this refinement holds;
where it cannot be proved, the checker **MUST** record an honest `Unproved` rather than assert it.

---

*Enforced by: F8 / `cws-modelcheck` — deadlock-freedom + the known-bad corpus (structural + EMPIRICAL
today), with invariants→TLC (P4-V01) and failure-as-transitions (P4-V06) the model-check criteria; the
in-skill self-tests (P0-T06, the data plane runs through the real channel); and — for the abstraction↔code
refinement — `alchemy/concord` once that validator lands (the blueprint-concordance gate).*
