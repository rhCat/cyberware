#!/usr/bin/env bash
# fs_archive — tar.gz a directory (proven pathway). Structured JSON output.
set -euo pipefail
: "${SOURCE_DIR:?}" "${RECORD_STORE:?}"
[ -d "$SOURCE_DIR" ] || { printf '{"tool":"fs_archive","status":"error","reason":"not a dir: %s"}\n' "$SOURCE_DIR"; exit 1; }
OUT="${RECORD_STORE%/}/archive.tar.gz"
tar -czf "$OUT" -C "$(dirname "$SOURCE_DIR")" "$(basename "$SOURCE_DIR")"
printf '{"tool":"fs_archive","status":"ok","source":"%s","archive":"%s","bytes":%d}\n' "$SOURCE_DIR" "$OUT" "$(wc -c < "$OUT")"
