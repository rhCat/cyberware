#!/usr/bin/env bash
# Rebuild the offline wheelhouse from the hash-pinned lock, natively (linux cp312) in a container.
# The wheels are reproducible from infra/pyenv/requirements.lock; vendor/wheelhouse/SHA256SUMS verifies them.
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
rm -rf "$ROOT/vendor/wheelhouse"; mkdir -p "$ROOT/vendor/wheelhouse"
docker run --rm --platform linux/amd64 -v "$ROOT:/w" -w /w python:3.12-slim \
  python -m pip download -r infra/pyenv/requirements.lock -d vendor/wheelhouse
( cd "$ROOT/vendor/wheelhouse" && shasum -a 256 *.whl | sort -k2 > SHA256SUMS )
echo "wheelhouse rebuilt: $(ls "$ROOT"/vendor/wheelhouse/*.whl | wc -l | tr -d ' ') wheels"
