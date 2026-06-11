#!/usr/bin/env bash
# psql_migrate — apply a .sql migration in ONE transaction. Structured JSON output (audit/debug log).
set -euo pipefail
: "${PGHOST:?}" "${PGDATABASE:?}" "${PGUSER:?}" "${MIGRATION:?}" "${RECORD_STORE:?}"
[ -f "$MIGRATION" ] || { printf '{"tool":"psql_migrate","status":"error","reason":"migration not found: %s"}\n' "$MIGRATION"; exit 1; }
LOG="${RECORD_STORE%/}/migrate_applied.log"
PGPASSWORD="${PGPASSWORD:-}" psql -h "$PGHOST" -p "${PGPORT:-5432}" -d "$PGDATABASE" -U "$PGUSER" \
  --no-psqlrc -v ON_ERROR_STOP=1 --single-transaction -f "$MIGRATION" > "$LOG" 2>&1
printf '{"tool":"psql_migrate","status":"ok","migration":"%s","applied_log":"%s"}\n' "$MIGRATION" "$LOG"
