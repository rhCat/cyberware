#!/usr/bin/env bash
# cws_evaluate — porter: runs the Python core (cws_evaluate.py), which reads SKILL_NAME/SKILL_DESC/RECORD_STORE from the environment.
set -euo pipefail
HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
exec python3 "$HERE/cws_evaluate.py"
