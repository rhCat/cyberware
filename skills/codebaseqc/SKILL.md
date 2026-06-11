---
skill: codebaseqc
name: Codebase QC (usage / contract / coverage)
perks: [audit, setup]
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

## Perks
- **`audit`** — run all three checks through the governed pipeline. Fill `PROJECT_DIR` (+ optional
  `SRC_DIR`, `TEST_DIR`); the run is 3 governed steps and the `*_gaps.json` reports land in the run dir.
- **`setup`** — install a **standalone landing script** (`codebaseqc.sh` + the three `cbqc_*.py`) into a
  `TARGET_DIR`, so you can run codebaseqc *without* the cyberware pipeline. Then:
  `./codebaseqc.sh <project_dir> [src_subdir] [out_dir]` — its reports go to a dir **you** choose (they
  stay there, not the run logs).
