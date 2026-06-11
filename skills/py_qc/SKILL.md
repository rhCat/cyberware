---
skill: py_qc
name: Python QC (pytest / lint)
perks: [test, lint]
---

# py_qc — Python QC

Run a Python project's own quality gates through the governed channel: pytest and ruff (flake8
fallback). Read-only with respect to the project — reports land in `record_store`.

## What to look out for
Each tool emits one line of structured JSON with the pass/fail counts (the audit + debug log) and
writes the full tool output under `record_store`. LOGS TO CHECK: that line + `pytest.out` /
`lint.out` + the executor run-ledger. A failing suite exits non-zero — the executor records the
failure; read `pytest.out` before re-running.

## Perks
| perk | tool | nature |
|---|---|---|
| `test` | `py_test` | runs pytest — read-only / safe |
| `lint` | `py_lint` | runs ruff (fallback flake8) — read-only / safe |

- **`test`** — set `PROJECT_DIR` (+ optional `TEST_DIR`, `PYTEST_ARGS`); output `pytest.out`.
- **`lint`** — set `PROJECT_DIR` (+ optional `LINT_TARGET`); output `lint.out`. Needs ruff or flake8
  installed in the environment.

For pure-ast QC with no dependencies (dead code / docstrings / test references), see `codebaseqc`.

## How to use it
Pick a perk, copy `ledger.json` → `task-ledger.json`, fill its vars + `record_store`, then
validate → compose → compile → oversight → executor.
