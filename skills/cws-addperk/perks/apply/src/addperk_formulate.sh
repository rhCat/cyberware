#!/usr/bin/env bash
# addperk_formulate — porter: runs addperk_formulate.py, which reads SKILL/PERK/PERK_DESC/TOOL/BINARY/RECORD_STORE from the environment.
set -euo pipefail
HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
exec python3 "$HERE/addperk_formulate.py"
