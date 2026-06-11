#!/usr/bin/env bash
# addperk_pr — push the perk-update branch + open a PR to the working branch + notify. Structured JSON.
set -uo pipefail
: "${SKILL:?}" "${PERK:?}" "${RECORD_STORE:?}"
HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO="$(cd "$HERE/../../../../.." && pwd)"
cd "$REPO" || exit 1
BR="perk/${SKILL}-${PERK}"
BASE="${BASE:-main}"
OUT="${RECORD_STORE%/}/pr.json"
git push -u origin "$BR" >/dev/null 2>&1 || true
PR=$(gh pr create --base "$BASE" --head "$BR" --title "perk: add ${SKILL}/${PERK}" \
      --body "Adds perk \`${PERK}\` to \`${SKILL}\` (formulated + composes). Review and merge through the agent." 2>/dev/null || echo "")
printf '{"tool":"addperk_pr","status":"ok","branch":"%s","base":"%s","pr":"%s","notify":"Perk PR opened on %s. Review it; tell the agent to merge (gh pr merge) once approved."}\n' "$BR" "$BASE" "$PR" "$BR" | tee "$OUT"
