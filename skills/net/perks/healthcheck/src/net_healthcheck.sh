#!/usr/bin/env bash
# net_healthcheck — HTTP probe: status code + total latency (proven pathway). Structured JSON output.
set -uo pipefail
: "${URL:?}" "${RECORD_STORE:?}"
OUT="${RECORD_STORE%/}/healthcheck.json"
RES=$(curl -sS -o /dev/null -w '%{http_code} %{time_total}' --max-time "${TIMEOUT:-10}" "$URL" 2>/dev/null || echo "000 0")
CODE="${RES%% *}"; LAT="${RES##* }"
H=$([ "${CODE:0:1}" = "2" ] || [ "${CODE:0:1}" = "3" ] && echo healthy || echo unhealthy)
printf '{"tool":"net_healthcheck","status":"ok","http_code":%s,"latency_s":%s,"health":"%s","report":"%s"}\n' "$CODE" "$LAT" "$H" "$OUT" | tee "$OUT"
