#!/usr/bin/env bash
# http_get — GET a URL (proven pathway). Deterministic structured JSON (audit/debug log).
set -euo pipefail
: "${URL:?}" "${RECORD_STORE:?}"
OUT="${RECORD_STORE%/}/response.body"
CODE=$(curl -sS -o "$OUT" -w '%{http_code}' ${HEADER:+-H "$HEADER"} "$URL")
printf '{"tool":"http_get","status":"ok","url":"%s","http_code":%s,"body_file":"%s","bytes":%d}\n' "$URL" "$CODE" "$OUT" "$(wc -c < "$OUT")"
