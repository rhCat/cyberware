#!/usr/bin/env bash
# js_infer — porter: runs the Python core, which reads DATA_FILE/RECORD_STORE from the environment.
# The logic lives in js_infer.py (standalone — inspect / lint / test it directly).
set -uo pipefail
: "${DATA_FILE:?}" "${RECORD_STORE:?}"
HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
exec python3 "$HERE/js_infer.py"
