#!/usr/bin/env bash
# addperk_eval — porter: runs addperk_eval.py, which reads SKILL/PERK/PERK_DESC/RECORD_STORE from the environment.
set -euo pipefail
HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
exec python3 "$HERE/addperk_eval.py"
