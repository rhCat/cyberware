#!/usr/bin/env bash
# py_lint — run ruff (fallback flake8) (proven pathway). Structured JSON output.
set -uo pipefail
: "${PROJECT_DIR:?}" "${RECORD_STORE:?}"
cd "$PROJECT_DIR"
OUT="${RECORD_STORE%/}/lint.out"
if command -v ruff >/dev/null; then ruff check "${LINT_TARGET:-.}" > "$OUT" 2>&1; RC=$?
elif command -v flake8 >/dev/null; then flake8 "${LINT_TARGET:-.}" > "$OUT" 2>&1; RC=$?
else echo "no linter (ruff/flake8) found" > "$OUT"; RC=127; fi
printf '{"tool":"py_lint","status":"%s","exit":%d,"report":"%s"}\n' "$([ $RC -eq 0 ] && echo ok || echo issues)" "$RC" "$OUT"
