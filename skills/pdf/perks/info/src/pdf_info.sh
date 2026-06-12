#!/usr/bin/env bash
# pdf_info — porter: runs the Python core, which reads PDF_FILE/RECORD_STORE from the environment.
# The logic lives in pdf_info.py (standalone — inspect / lint / test it directly): it tries poppler's
# `pdfinfo`, then pypdf, and ALWAYS writes pdf_info.json (a note if no pdf tool is available) so the
# contract's output_exists holds. Read-only; structured JSON output.
set -uo pipefail
: "${PDF_FILE:?}" "${RECORD_STORE:?}"
HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
exec python3 "$HERE/pdf_info.py"
