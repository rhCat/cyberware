#!/usr/bin/env bash
# py_test — run pytest (proven pathway). Structured JSON output.
set -uo pipefail
: "${PROJECT_DIR:?}" "${RECORD_STORE:?}"
cd "$PROJECT_DIR"
OUT="${RECORD_STORE%/}/pytest.out"
"${PYTHON:-python3}" -m pytest "${TEST_DIR:-tests}" ${PYTEST_ARGS:-} > "$OUT" 2>&1
RC=$?
printf '{"tool":"py_test","status":"%s","exit":%d,"report":"%s"}\n' "$([ $RC -eq 0 ] && echo ok || echo fail)" "$RC" "$OUT"
exit $RC
