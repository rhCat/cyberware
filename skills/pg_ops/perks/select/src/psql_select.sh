#!/usr/bin/env bash
# psql_select — read-only SELECT (proven pathway). Emits deterministic structured JSON (audit/debug log).
set -euo pipefail
: "${PGHOST:?}" "${PGDATABASE:?}" "${PGUSER:?}" "${QUERY:?}" "${RECORD_STORE:?}"
OUT="${RECORD_STORE%/}/select_rows.csv"
PGPASSWORD="${PGPASSWORD:-}" psql -h "$PGHOST" -p "${PGPORT:-5432}" -d "$PGDATABASE" -U "$PGUSER" \
  --no-psqlrc --csv -c "${QUERY} LIMIT ${LIMIT:-100}" > "$OUT"
printf '{"tool":"psql_select","status":"ok","rows_csv":"%s","rows":%d}\n' "$OUT" "$(($(wc -l < "$OUT")-1))"
