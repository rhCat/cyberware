#!/usr/bin/env bash
# sqlite_exec — apply a .sql migration script to a local SQLite db in one pass. Structured JSON output (audit/debug log).
set -euo pipefail
: "${DB_FILE:?}" "${SQL_FILE:?}" "${RECORD_STORE:?}"
LOG="${RECORD_STORE%/}/exec_applied.log"
# the SQL is supplied as a file at runtime (read as data, never executed by the shell); guard it exists.
if [ ! -f "$SQL_FILE" ]; then
  printf -- '-- sql file not found: %s\n' "$SQL_FILE" > "$LOG"
  printf '{"tool":"sqlite_exec","status":"error","reason":"sql file not found: %s"}\n' "$SQL_FILE"
  exit 1
fi
# apply the script in a single pass; the redirect creates LOG up front so it always exists for the contract check.
sqlite3 -batch "$DB_FILE" < "$SQL_FILE" > "$LOG" 2>&1
printf '{"tool":"sqlite_exec","status":"ok","sql_file":"%s","applied_log":"%s"}\n' "$SQL_FILE" "$LOG"
