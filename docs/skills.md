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
| **codebaseqc** | `audit` · `setup` | python3 (ast) | pure-Python QC: usage (dead code) · contract (docstring+return type) · coverage (referenced in tests). `setup` installs a standalone landing script (`codebaseqc.sh`) into a dir — runs without the pipeline, reports go where you choose. Name-based heuristics. |
| **ci-codeqc** | `github_actions` | bash | generate/update `.github/workflows/codeqc.yml` (ruff + mypy + pytest) for any repo. Idempotent: existing workflow backed up to `.bk` before overwrite. |
| **datadog** | `github_ci` | bash · datadog-ci | generate/update `.github/workflows/datadog-ci.yml` — install datadog-ci, run tests, upload JUnit results to Datadog (CI Test Visibility). Idempotent; add the `DD_API_KEY` secret after. |
| **docker** | `build` · `ps` | docker | build an image from a context dir; `ps` lists containers (read-only). Needs a running daemon. |
| **net** | `healthcheck` · `dns` | curl · python3 | HTTP probe (status + latency); DNS resolve (python core via porter). Read-only. |
| **data** | `csv2json` · `jq` | python3 · jq | CSV → JSON array (python core); jq query over a JSON file. |
| **search** | `grep` · `loc` | ripgrep/grep · find | pattern search (rg, fallback grep); line counts by extension. Read-only. |
| **release** | `tag` | git | annotated git tag at HEAD; no-op if it exists. No force, no push (push stays gated). |
| **cws-create** | `evaluate` · `scaffold` | python3 · scaffold.py | **the on-ramp** — classify a candidate skill (execution / design / transformable / unclear) and, if it fits, scaffold it into cyberware format. |
| **cws-addperk** | `evaluate` · `apply` | python3 · git · gh | add a perk to an existing skill, governed — evaluate (exists / generalizable / scope), then branch → formulate + validate → open a PR (merge through the agent). |

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
