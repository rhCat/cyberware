#!/usr/bin/env bash
# data_jq — run a jq query over a JSON file (proven pathway). Structured JSON output.
set -uo pipefail
: "${JSON_FILE:?}" "${QUERY:?}" "${RECORD_STORE:?}"
OUT="${RECORD_STORE%/}/jq_result.json"
jq "$QUERY" "$JSON_FILE" > "$OUT" 2>/dev/null
RC=$?
printf '{"tool":"data_jq","status":"%s","exit":%d,"out":"%s"}\n' "$([ $RC -eq 0 ] && echo ok || echo fail)" "$RC" "$OUT"
exit $RC
