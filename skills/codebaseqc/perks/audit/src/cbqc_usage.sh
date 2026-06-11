#!/usr/bin/env bash
# cbqc_usage — porter: runs the Python core, which reads PROJECT_DIR/SRC_DIR/RECORD_STORE from the environment.
# The logic lives in cbqc_usage.py (standalone — inspect / lint / test it directly).
set -euo pipefail
HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
exec python3 "$HERE/cbqc_usage.py"
