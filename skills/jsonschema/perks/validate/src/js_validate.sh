#!/usr/bin/env bash
# js_validate — porter: runs the Python core, which reads DATA_FILE/SCHEMA_FILE/RECORD_STORE from the environment.
# The logic lives in js_validate.py (standalone — inspect / lint / test it directly).
set -uo pipefail
: "${DATA_FILE:?}" "${SCHEMA_FILE:?}" "${RECORD_STORE:?}"
HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
exec python3 "$HERE/js_validate.py"
