#!/usr/bin/env bash
# ci_github_actions — generate/update a GitHub Actions code-QC workflow for a repo. Structured JSON.
# Idempotent: re-running regenerates; an existing workflow is backed up to .bk first (= "updated").
set -euo pipefail
: "${PROJECT_DIR:?}" "${RECORD_STORE:?}"
WFDIR="${PROJECT_DIR%/}/.github/workflows"
WF="$WFDIR/codeqc.yml"
mkdir -p "$WFDIR"
ACTION="created"
if [ -f "$WF" ]; then cp "$WF" "$WF.bk"; ACTION="updated"; fi
cat > "$WF" <<YAML
name: code-qc
on:
  push:
    branches: [ "${BRANCH:-main}" ]
  pull_request:
permissions:
  contents: read
jobs:
  codeqc:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: "${PYTHON_VERSION:-3.12}"
      - name: install
        run: |
          python -m pip install --upgrade pip
          pip install ruff mypy pytest pytest-cov
      - name: lint (ruff)
        run: ruff check ${SRC_DIR:-.}
      - name: types (mypy)
        run: mypy ${SRC_DIR:-.} || true
      - name: test (pytest)
        run: |
          if [ -d ${TEST_DIR:-tests} ]; then pytest ${TEST_DIR:-tests} --cov=${SRC_DIR:-.}; else echo "no ${TEST_DIR:-tests}/ dir — skipping"; fi
YAML
cp "$WF" "${RECORD_STORE%/}/codeqc.yml"
printf '{"tool":"ci_github_actions","status":"ok","action":"%s","workflow":"%s"}\n' "$ACTION" "$WF"
