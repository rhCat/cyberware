#!/usr/bin/env bash
# docker_ps — list containers (read-only). Structured JSON output.
set -uo pipefail
: "${RECORD_STORE:?}"
OUT="${RECORD_STORE%/}/containers.txt"
docker ps ${ALL:+-a} --format '{{.ID}} {{.Image}} {{.Status}} {{.Names}}' > "$OUT" 2>/dev/null
RC=$?
COUNT=$([ -f "$OUT" ] && wc -l < "$OUT" | tr -d ' ' || echo 0)
printf '{"tool":"docker_ps","status":"%s","count":%s,"report":"%s"}\n' "$([ $RC -eq 0 ] && echo ok || echo fail)" "$COUNT" "$OUT"
