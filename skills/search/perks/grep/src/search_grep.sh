#!/usr/bin/env bash
# search_grep — search files for a pattern (ripgrep, fallback grep). Structured JSON output.
set -uo pipefail
: "${PATTERN:?}" "${SEARCH_DIR:?}" "${RECORD_STORE:?}"
OUT="${RECORD_STORE%/}/matches.txt"
if command -v rg >/dev/null 2>&1; then rg -n -- "$PATTERN" "$SEARCH_DIR" > "$OUT" 2>/dev/null || true
else grep -rn -- "$PATTERN" "$SEARCH_DIR" > "$OUT" 2>/dev/null || true; fi
COUNT=$(wc -l < "$OUT" | tr -d ' ')
printf '{"tool":"search_grep","status":"ok","matches":%s,"report":"%s"}\n' "$COUNT" "$OUT"
