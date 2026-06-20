# Skill catalog

Tool skills (operational pathways) — not design/taste skills. They live on the **skillChip** (cyberware's
swappable skill cartridge, a separate repo vendored as the `skillChip/` submodule). Each runs through the
governed pipeline (`validate → compose → compile → oversight → executor`), ships a `blueprint.{drawio,svg}`,
pins every file in an `index.json` (authenticity), and carries a per-perk `test/case.json` that proves it
through the real channel. **37 skills** — discover them at `GET /catalog` or `./govd-client --discover`.
The table below is the **general tool** catalog; the **v1.1 validator family** (which grades the build
against the plan) is listed separately under [Validators](#validators).

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
| **cws-deploy** | `serve` · `status` · `down` | docker | deploy the cyberware **govd engine itself** as a governed container — `serve` builds (if absent) + runs + waits for `/health`, `status` reports, `down` tears down (data volume preserved). The dogfood loop: a governed skill that brings up the engine that governs it. Monitor token via `TOKEN_FILE`. Needs a running daemon. |
| **net** | `healthcheck` · `dns` | curl · python3 | HTTP probe (status + latency); DNS resolve (python core via porter). Read-only. |
| **data** | `csv2json` · `jq` | python3 · jq | CSV → JSON array (python core); jq query over a JSON file. |
| **search** | `grep` · `loc` | ripgrep/grep · find | pattern search (rg, fallback grep); line counts by extension. Read-only. |
| **release** | `tag` | git | annotated git tag at HEAD; no-op if it exists. No force, no push (push stays gated). |
| **sec** | `secrets` · `audit` | grep · python3 | scan a tree for leaked secrets (findings carry file/line/rule, never the value) · best-effort dependency-vuln audit. Read-only. |
| **sqlite** | `query` · `exec` | sqlite3 | local SQLite; `query` read-only, `exec` applies a migration (destructive → approve). |
| **terraform** | `plan` · `apply` | terraform | IaC; `plan` (init/validate/plan) read-only, `apply` destructive → approve. |
| **pdf** | `extract` · `info` | pdftotext/pypdf | extract text · read metadata (Python core; degrades to a note if no extractor). Read-only. |
| **jsonschema** | `validate` · `infer` | python3 | validate JSON against a schema · infer a schema from a sample (stdlib). Read-only. |
| **markdown** | `toc` · `links` | python3 | table of contents from headings · dead relative-link finder. Read-only. |
| **ssh** | `check` · `run` | ssh | connectivity check (read-only) · vetted remote command (destructive → approve; key via `*_FILE`). |
| **alchemy** | `extract` · `conserve` · `classify` · `concord` · `lineage` | python3 | the concordance / transmutation engine — extract claims, conserve through transforms, classify, build the concordance + lineage. The SV-4 concordance ancestor that `cws-release/citrinitas` gates on. |
| **cws-release** | `sign` · `publish` · `receipts` · `transparency` · `revoke` · `keyrotate` · `timeanchor` · `engine` · `citrinitas` · … | python3 | publish & transparency toolchain — cosign the chip manifest (tri-layer refusal), Rekor transparency proofs, signed revocation feed, key-rotation, TSA time-anchor, engine attestation, the Citrinitas gate (13 perks). |
| **cws-create** | `evaluate` · `scaffold` | python3 · scaffold.py | **the on-ramp** — classify a candidate skill (execution / design / transformable / unclear) and, if it fits, scaffold it into cyberware format. |
| **cws-addperk** | `evaluate` · `apply` | python3 · git · gh | add a perk to an existing skill, governed — evaluate (exists / generalizable / scope), then branch → formulate + validate → open a PR (merge through the agent). |

## Validators

The v1.1 build is **graded by its own skills** — each plan task is `validated_by` one of these, and a task
is *redeemed* on the tamper-evident done-ledger only when a governed validator run proves it passed (never
asserted). The on-ramp (`cws-create` / `cws-addperk`) authors new skills; the rest grade the ladder:

| skill | grades (validation class) | notes |
|---|---|---|
| **cws-conform** | SV-1 protocol conformance (V-EXT) | canonical-hash + DSSE/cosign-interop verdicts vs the Go anchor; CWP message-`schemas` (2020-12) corpus |
| **cws-ledgercheck** | SV-2 ledger soundness (V-GOV) | Ledger-v2 chain re-verify · Go `anchor` · durability `torture` · crypto-shred `erasure` · Merkle `checkpoint` |
| **cws-mutate** | gate strength (V-MUT) | a gate that survives its own deletion was never a gate — R3 mutation gates |
| **cws-modelcheck** | blueprint safety (V-PROP) | TLC deadlock / invariant model-checking |
| **cws-redteam** | SV-3 execution boundary (V-RED) | the ≥12-attack expected-refusal corpus through exod+sandbox (the M3 gate) |
| **cws-bench** | SV-3 overhead budgets (V-BENCH) | per-step bwrap p95 from exod's attested meters |
| **cws-observe** | progress by redemption | `status` (classify the DAG vs the plan) · `redeem` (the only done-ledger writer) |
| **cws-pm** | composite operator | drives a playbook of validators + tracks the board (pm.json / pm.md) |
| **harden-pyenv** | reproducible env | hash-locked deps · SBOM · the pinned compute image |
| **cws-redteam-sw** | SV-1/SV-2 software-tier red-team | the precursor corpus (not the M3 kernel gate) |
| **cws-chaos** | resilience under fault (V-CHAOS) | partition · crash · settle-atomicity drills — the system holds, or refuses safely, under injected faults |
| **cws-settle-sim** | SV-6 settlement soundness (V-SETTLE) | the money's lifecycle (quote → settle → capstone) + adversarial zero-sum · float-ban · manipulation · dispute drills |

The execution-boundary validators (`cws-redteam`, `cws-bench`) are described in
[architecture.md](architecture.md#the-kernel-enforced-execution-boundary-sv-3).

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
It honestly shows the open gaps (e.g., no return-type hints yet). The infra is covered by a real
`tests/` suite (unit + integration + per-perk contract), gated in CI; and **every skill carries its own
governed self-test** (`perks/<perk>/test/case.json`, run through the real channel by
`infra.tool.skilltest` and discovered by `tests/test_skill_selftests.py`) — see [Tests](../README.md#tests)
and [authoring.md](authoring.md#6-prove-it--the-in-skill-self-test).
