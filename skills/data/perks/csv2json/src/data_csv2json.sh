#!/usr/bin/env bash
# data_csv2json — porter: runs the Python core (data_csv2json.py), which reads CSV_FILE/RECORD_STORE from the environment.
set -euo pipefail
HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
exec python3 "$HERE/data_csv2json.py"
