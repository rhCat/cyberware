---
skill: ci-codeqc
name: CI code-QC generator
perks: [github_actions]
---

# ci-codeqc — generate/update a code-QC CI for any repo

Writes a GitHub Actions **code-qc** workflow (`.github/workflows/codeqc.yml`) into a target repo:
checkout → setup Python → install → **ruff** (lint) → **mypy** (types) → **pytest --cov** (test).
Idempotent — re-running regenerates it; an existing workflow is backed up to `.bk` first, so the same
skill both *creates* and *updates* the CI.

## What to look out for
The tool emits structured JSON with `action` = `created | updated` and the workflow path; LOGS TO
CHECK: that line + `${record_store}/codeqc.yml` (a copy) + the executor run-ledger.

## How to use it
Fill `PROJECT_DIR` (+ optional `SRC_DIR`, `TEST_DIR`, `PYTHON_VERSION`, `BRANCH`), then
validate → compose → compile → oversight → executor. The workflow lands in the target repo; commit it.
