#!/usr/bin/env bash
# release_tag — create an annotated git tag at HEAD (proven pathway). Structured JSON output.
set -uo pipefail
: "${REPO_DIR:?}" "${VERSION:?}" "${RECORD_STORE:?}"
OUT="${RECORD_STORE%/}/release_tag.json"
cd "$REPO_DIR" || { printf '{"tool":"release_tag","status":"error","reason":"bad repo dir"}\n' | tee "$OUT"; exit 1; }
if git rev-parse "$VERSION" >/dev/null 2>&1; then printf '{"tool":"release_tag","status":"noop","reason":"tag exists","tag":"%s"}\n' "$VERSION" | tee "$OUT"; exit 0; fi
git tag -a "$VERSION" -m "${MESSAGE:-release $VERSION}"
RC=$?
SHA=$(git rev-parse --short HEAD 2>/dev/null)
printf '{"tool":"release_tag","status":"%s","tag":"%s","sha":"%s","report":"%s"}\n' "$([ $RC -eq 0 ] && echo ok || echo fail)" "$VERSION" "$SHA" "$OUT" | tee "$OUT"
exit $RC
