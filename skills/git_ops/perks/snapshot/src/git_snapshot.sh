#!/usr/bin/env bash
# git_snapshot — stage all + commit (proven pathway). Structured JSON output.
set -euo pipefail
: "${REPO_DIR:?}" "${MESSAGE:?}" "${RECORD_STORE:?}"
cd "$REPO_DIR"
git add -A
OUT="${RECORD_STORE%/}/git_snapshot.json"
if git diff --cached --quiet; then printf '{"tool":"git_snapshot","status":"noop","reason":"nothing to commit"}\n' | tee "$OUT"; exit 0; fi
git commit -m "$MESSAGE" --no-verify >/dev/null
SHA=$(git rev-parse --short HEAD)
printf '{"tool":"git_snapshot","status":"ok","repo":"%s","sha":"%s"}\n' "$REPO_DIR" "$SHA" | tee "$OUT"
