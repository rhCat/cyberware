#!/usr/bin/env bash
# psql_migrate — apply a .sql migration in ONE transaction. Structured JSON output (audit/debug log).
set -euo pipefail
: "${PGHOST:?}" "${PGDATABASE:?}" "${PGUSER:?}" "${MIGRATION:?}" "${RECORD_STORE:?}"
[ -f "$MIGRATION" ] || { printf '{"tool":"psql_migrate","status":"error","reason":"migration not found: %s"}\n' "$MIGRATION"; exit 1; }
LOG="${RECORD_STORE%/}/migrate_applied.log"
# the password is NEVER a plaintext var — read it from a pass-file pointer at runtime (cat reads the file
# as data, it does not execute it), so the secret lives only in that file + this process, never in config
[ -n "${PGPASSWORD_FILE:-}" ] && export PGPASSWORD="$(cat "$PGPASSWORD_FILE")"
psql -h "$PGHOST" -p "${PGPORT:-5432}" -d "$PGDATABASE" -U "$PGUSER" \
  --no-psqlrc -v ON_ERROR_STOP=1 --single-transaction -f "$MIGRATION" > "$LOG" 2>&1
printf '{"tool":"psql_migrate","status":"ok","migration":"%s","applied_log":"%s"}\n' "$MIGRATION" "$LOG"
