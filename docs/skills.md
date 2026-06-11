# Skill catalog

Tool skills (operational pathways) — not design/taste skills. Each runs through the governed pipeline
(`validate → compose → compile → oversight → executor`) and ships a `blueprint.{drawio,svg}`.

| skill | perks | tools | notes / guard |
|---|---|---|---|
| **pg_ops** | `select` · `migrate` | psql | governed PostgreSQL; `select` read-only, `migrate` in one transaction. DROP/TRUNCATE push back unless `--approve`. |
| **http** | `get` · `post` | curl | responses captured to record_store with status + size. pipe-to-shell blocked. |
| **fs** | `archive` · `find_large` | tar · find | `archive` → tar.gz; `find_large` read-only listing. rm-at-root / rm -rf gated. |
| **git_ops** | `snapshot` · `status` | git | `snapshot` = stage+commit (no push — push is intentionally not a skill); `status` read-only. force-push / reset --hard gated. |
| **py_qc** | `test` · `lint` | pytest · ruff/flake8 | run a project's tests / linter, reports to record_store. |
| **codebaseqc** | `audit` | python3 (ast) | pure-Python QC: usage (dead code) · contract (docstring+return type) · coverage (referenced in tests). Name-based heuristics; sound resolution is the Intent-Fidelity frontier. |
| **ci-codeqc** | `github_actions` | bash | generate/update `.github/workflows/codeqc.yml` (ruff + mypy + pytest) for any repo. Idempotent: existing workflow backed up to `.bk` before overwrite. |

## Choosing a perk

A **perk** is a *predetermined, proven, viable pathway*. The blueprint says what to watch and which
logs to check; a perk says exactly how to act. Pick the perk whose `metadata.json` matches your task
(its `rules`, `usage`, `limitation`, and `minimal_example`), copy `ledger.json` → your
`task-ledger.json`, fill the vars its `manifesto.json` declares, and submit it to the pipeline.

## Adding a skill

See [authoring.md](authoring.md) — `scaffold.py` writes a composing skeleton; fill the snippets and
vars. The registry is meant to grow: tools are the unit, perks are the proven pathways within them.

## Self-audit

`examples/self-audit/` holds the framework's own `codebaseqc` report — cyberware QC'd by cyberware.
It honestly shows the open gaps (no return-type hints, no `tests/` dir yet).
