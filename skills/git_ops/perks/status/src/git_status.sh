#!/usr/bin/env bash
# git_status — porcelain status (read-only). Structured JSON output.
set -euo pipefail
: "${REPO_DIR:?}" "${RECORD_STORE:?}"
cd "$REPO_DIR"
OUT="${RECORD_STORE%/}/git_status.txt"
git status --porcelain=v1 -b > "$OUT"
DIRTY=$(grep -vc '^##' "$OUT" || true)
printf '{"tool":"git_status","status":"ok","repo":"%s","dirty_files":%s,"report":"%s"}\n' "$REPO_DIR" "$DIRTY" "$OUT"
