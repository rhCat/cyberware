#!/usr/bin/env bash
# md_links — porter: runs the Python core, which reads MD_FILE/RECORD_STORE from the environment.
# The logic lives in md_links.py (standalone — inspect / lint / test it directly).
set -euo pipefail
: "${MD_FILE:?}" "${RECORD_STORE:?}"
HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
exec python3 "$HERE/md_links.py"
