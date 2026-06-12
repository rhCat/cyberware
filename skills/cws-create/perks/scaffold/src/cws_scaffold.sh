#!/usr/bin/env bash
# cws_scaffold — lay down a cyberware skill skeleton via infra.tool.scaffold (the "create" step). Structured JSON.
set -uo pipefail
: "${NEW_SKILL:?}" "${NEW_NAME:?}" "${PERKS:?}" "${RECORD_STORE:?}"
HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO="$(cd "$HERE/../../../../.." && pwd)"
OUT="${RECORD_STORE%/}/scaffold.log"
ARGS=""
for p in $PERKS; do ARGS="$ARGS --perk $p"; done   # PERKS = space-separated <pid>:<tool>[:<binary>]
PYTHONPATH="$REPO" python3 -m infra.tool.scaffold --skill "$NEW_SKILL" --name "$NEW_NAME" $ARGS > "$OUT" 2>&1
RC=$?
printf '{"tool":"cws_scaffold","status":"%s","skill":"%s","exit":%d,"log":"%s"}\n' "$([ $RC -eq 0 ] && echo ok || echo fail)" "$NEW_SKILL" "$RC" "$OUT"
exit $RC
