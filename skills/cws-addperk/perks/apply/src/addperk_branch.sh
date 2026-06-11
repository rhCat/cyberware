#!/usr/bin/env bash
# addperk_branch — create + checkout the perk-update branch. Structured JSON.
set -uo pipefail
: "${SKILL:?}" "${PERK:?}" "${RECORD_STORE:?}"
HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO="$(cd "$HERE/../../../../.." && pwd)"
cd "$REPO" || exit 1
BR="perk/${SKILL}-${PERK}"
git checkout -b "$BR" 2>/dev/null || git checkout "$BR"
RC=$?
printf '{"tool":"addperk_branch","status":"%s","branch":"%s"}\n' "$([ $RC -eq 0 ] && echo ok || echo fail)" "$BR" | tee "${RECORD_STORE%/}/branch.json"
exit $RC
