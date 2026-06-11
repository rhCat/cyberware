#!/usr/bin/env bash
# search_loc — count files + lines for an extension (read-only). Structured JSON output.
set -uo pipefail
: "${SEARCH_DIR:?}" "${RECORD_STORE:?}"
EXT="${EXT:-py}"
OUT="${RECORD_STORE%/}/loc.txt"
find "$SEARCH_DIR" -type f -name "*.${EXT}" -not -path '*/.*' > "${OUT}.files" 2>/dev/null || true
FILES=$(wc -l < "${OUT}.files" | tr -d ' ')
if [ -s "${OUT}.files" ]; then LINES=$(xargs wc -l < "${OUT}.files" 2>/dev/null | tail -1 | awk '{print $1}'); else LINES=0; fi
: "${LINES:=0}"
printf '%s files, %s lines (*.%s)\n' "$FILES" "$LINES" "$EXT" > "$OUT"
printf '{"tool":"search_loc","status":"ok","ext":"%s","files":%s,"lines":%s,"report":"%s"}\n' "$EXT" "$FILES" "$LINES" "$OUT"
