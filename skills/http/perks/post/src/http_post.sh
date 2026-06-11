#!/usr/bin/env bash
# http_post — POST a JSON body (proven pathway). Structured JSON output.
set -euo pipefail
: "${URL:?}" "${BODY:?}" "${RECORD_STORE:?}"
OUT="${RECORD_STORE%/}/response.body"
CODE=$(curl -sS -X POST -H 'content-type: application/json' -d "$BODY" -o "$OUT" -w '%{http_code}' "$URL")
printf '{"tool":"http_post","status":"ok","url":"%s","http_code":%s,"body_file":"%s"}\n' "$URL" "$CODE" "$OUT"
