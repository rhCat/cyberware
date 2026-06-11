#!/usr/bin/env bash
# cbqc_contract — porter: runs the Python core, which reads PROJECT_DIR/SRC_DIR/RECORD_STORE from the environment.
# The logic lives in cbqc_contract.py (standalone — inspect / lint / test it directly).
set -euo pipefail
HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
exec python3 "$HERE/cbqc_contract.py"
