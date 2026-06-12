#!/usr/bin/env bash
# md_toc — porter: runs the Python core, which reads MD_FILE/RECORD_STORE from the environment.
# The logic lives in md_toc.py (standalone — inspect / lint / test it directly).
set -euo pipefail
: "${MD_FILE:?}" "${RECORD_STORE:?}"
HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
exec python3 "$HERE/md_toc.py"
