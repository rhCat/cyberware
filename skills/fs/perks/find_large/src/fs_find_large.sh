#!/usr/bin/env bash
# fs_find_large — list files over a size threshold (read-only). Structured JSON output.
set -euo pipefail
: "${SEARCH_DIR:?}" "${RECORD_STORE:?}"
OUT="${RECORD_STORE%/}/large_files.txt"
find "$SEARCH_DIR" -type f -size +"${MIN_SIZE:-100M}" -print > "$OUT" 2>/dev/null || true
printf '{"tool":"fs_find_large","status":"ok","search_dir":"%s","threshold":"%s","listing":"%s","count":%d}\n' "$SEARCH_DIR" "${MIN_SIZE:-100M}" "$OUT" "$(wc -l < "$OUT")"
