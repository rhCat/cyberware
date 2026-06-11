---
skill: codebaseqc
name: Codebase QC (usage / contract / coverage)
perks: [audit]
---

# codebaseqc — pure-Python codebase QC

Three-dimension quality check for a Python repo, **pure-Python ast** — no alembic, no dependencies:
- **usage**   — functions defined but never referenced by name (dead-code heuristic)
- **contract**— public functions missing a docstring or a return type
- **coverage**— public functions whose name never appears in the test dir

## What to look out for
The `audit` perk runs the three tools in sequence; each emits structured JSON and writes a
`*_gaps.json` report to `record_store`. LOGS TO CHECK: `usage_gaps.json`, `contract_gaps.json`,
`coverage_gaps.json`, plus the executor `run-ledger.json`.

> **Honest scope:** these are *name-based* heuristics (the pure-Python pathway). Sound resolution —
> distinguishing `obj.method()` calls, jedi/pyright-grade — is the Intent-Fidelity frontier and the
> reason the original codebaseqc reached for alembic. This migration is the dependency-free version.

## How to use it
Fill `PROJECT_DIR` (+ optional `SRC_DIR`, `TEST_DIR`), then validate → compose → compile → oversight →
executor (the run is 3 governed steps).
