#!/usr/bin/env bash
# cbqc_setup — install a standalone codebaseqc landing script into TARGET_DIR. Structured JSON output.
# The landing script runs the usage/contract/coverage checks WITHOUT the cyberware pipeline; its reports
# go to a dir YOU choose (default <target>/codebaseqc-reports) — they STAY there, never the run logs.
set -uo pipefail
: "${TARGET_DIR:?}" "${RECORD_STORE:?}"
HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SRC="$HERE/../../audit/src"
DEST="${TARGET_DIR%/}"
mkdir -p "$DEST"
cp "$SRC/cbqc_usage.py" "$SRC/cbqc_contract.py" "$SRC/cbqc_coverage.py" "$DEST/"
cat > "$DEST/codebaseqc.sh" <<'LANDING'
#!/usr/bin/env bash
# codebaseqc — standalone runner (installed by cyberware codebaseqc/setup).
# usage: ./codebaseqc.sh <project_dir> [src_subdir] [out_dir]   (out_dir default: ./codebaseqc-reports beside this script)
set -euo pipefail
HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
export PROJECT_DIR="${1:-$(pwd)}"
export SRC_DIR="${2:-.}"
export TEST_DIR="${TEST_DIR:-tests}"
export RECORD_STORE="${3:-$HERE/codebaseqc-reports}"
mkdir -p "$RECORD_STORE"
for t in cbqc_usage cbqc_contract cbqc_coverage; do python3 "$HERE/$t.py"; done
echo "codebaseqc reports -> $RECORD_STORE"
LANDING
chmod +x "$DEST/codebaseqc.sh"
printf '{"tool":"cbqc_setup","status":"ok","installed":"%s","landing":"%s/codebaseqc.sh","run":"%s/codebaseqc.sh <project_dir> [src] [out_dir]"}\n' "$DEST" "$DEST" "$DEST" | tee "${RECORD_STORE%/}/setup.json"
