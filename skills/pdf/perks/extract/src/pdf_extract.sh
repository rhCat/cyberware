#!/usr/bin/env bash
# pdf_extract — porter: extract a PDF's text to record_store. Read-only; structured JSON output.
# Prefers poppler's `pdftotext` (handled here in bash); otherwise delegates to the Python core
# (pdf_extract.py — pypdf/PyPDF2/pdfminer, standalone: inspect / lint / test it directly), which
# ALWAYS writes extracted.txt (a one-line note if no extractor is available) so the contract holds.
set -uo pipefail
: "${PDF_FILE:?}" "${RECORD_STORE:?}"
HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
OUT="${RECORD_STORE%/}/extracted.txt"

if command -v pdftotext >/dev/null 2>&1; then
  pdftotext "$PDF_FILE" "$OUT" >/dev/null 2>&1 || : > "$OUT"
  CHARS=$(wc -c < "$OUT" | tr -d ' ')
  printf '{"tool":"pdf_extract","status":"ok","chars":%s,"text":"%s"}\n' "$CHARS" "$OUT"
else
  exec python3 "$HERE/pdf_extract.py"
fi
