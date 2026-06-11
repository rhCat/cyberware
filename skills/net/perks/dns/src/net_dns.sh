#!/usr/bin/env bash
# net_dns — porter: runs the Python core (net_dns.py), which reads HOST/RECORD_STORE from the environment.
set -euo pipefail
HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
exec python3 "$HERE/net_dns.py"
