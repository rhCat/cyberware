#!/usr/bin/env bash
# datadog_github_ci — generate/update a Datadog CI Visibility GitHub Actions workflow. Structured JSON.
# Idempotent: an existing workflow is backed up to .bk first (= "updated").
set -uo pipefail
: "${PROJECT_DIR:?}" "${RECORD_STORE:?}"
WFDIR="${PROJECT_DIR%/}/.github/workflows"
WF="$WFDIR/datadog-ci.yml"
mkdir -p "$WFDIR"
ACTION="created"
if [ -f "$WF" ]; then cp "$WF" "$WF.bk"; ACTION="updated"; fi
SVC="${SERVICE:-$(basename "${PROJECT_DIR%/}")}"
cat > "$WF" <<YAML
name: datadog-ci
on:
  push:
    branches: [ "${BRANCH:-main}" ]
  pull_request:
permissions:
  contents: read
jobs:
  test-visibility:
    runs-on: ubuntu-latest
    env:
      DD_API_KEY: \${{ secrets.DD_API_KEY }}
      DD_SITE: "${DD_SITE:-datadoghq.com}"
      DD_ENV: ci
      DD_SERVICE: "${SVC}"
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-node@v4
        with:
          node-version: "20"
      - name: install datadog-ci
        run: npm install -g @datadog/datadog-ci
      - name: run tests (produce JUnit XML)
        run: ${TEST_CMD:-pytest --junitxml=junit.xml}
      - name: upload test results to Datadog
        if: always()
        run: datadog-ci junit upload --service "\$DD_SERVICE" --env "\$DD_ENV" ${JUNIT_PATH:-junit.xml}
YAML
cp "$WF" "${RECORD_STORE%/}/datadog-ci.yml"
printf '{"tool":"datadog_github_ci","status":"ok","action":"%s","service":"%s","workflow":"%s","next":"add the DD_API_KEY repo secret; optionally enable the Datadog GitHub App for pipeline visibility"}\n' "$ACTION" "$SVC" "$WF"
