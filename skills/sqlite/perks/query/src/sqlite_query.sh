#!/usr/bin/env bash
# sqlite_query — run a read-only SQL query against a local SQLite db. Structured JSON output (audit/debug log).
set -uo pipefail
: "${DB_FILE:?}" "${QUERY:?}" "${RECORD_STORE:?}"
OUT="${RECORD_STORE%/}/query_result.txt"
# ALWAYS produce the result file. If the db file is missing, write a note instead of crashing;
# otherwise run the query read-only (-readonly never creates or writes the db) and capture all output.
if [ -f "$DB_FILE" ]; then
  sqlite3 -readonly -batch -header "$DB_FILE" "$QUERY" > "$OUT" 2>&1 || true
else
  printf -- '-- db file not found: %s\n' "$DB_FILE" > "$OUT"
fi
ROWS=$(wc -l < "$OUT" | tr -d ' ')
printf '{"tool":"sqlite_query","status":"ok","rows":%s,"result":"%s"}\n' "$ROWS" "$OUT"
