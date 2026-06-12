#!/usr/bin/env bash
# psql_select — read-only SELECT (proven pathway). Emits deterministic structured JSON (audit/debug log).
set -euo pipefail
: "${PGHOST:?}" "${PGDATABASE:?}" "${PGUSER:?}" "${QUERY:?}" "${RECORD_STORE:?}"
OUT="${RECORD_STORE%/}/select_rows.csv"
# the password is NEVER a plaintext var — read it from a pass-file pointer at runtime (cat reads the file
# as data, it does not execute it), so the secret lives only in that file + this process, never in config
[ -n "${PGPASSWORD_FILE:-}" ] && export PGPASSWORD="$(cat "$PGPASSWORD_FILE")"
psql -h "$PGHOST" -p "${PGPORT:-5432}" -d "$PGDATABASE" -U "$PGUSER" \
  --no-psqlrc --csv -c "${QUERY} LIMIT ${LIMIT:-100}" > "$OUT"
printf '{"tool":"psql_select","status":"ok","rows_csv":"%s","rows":%d}\n' "$OUT" "$(($(wc -l < "$OUT")-1))"
