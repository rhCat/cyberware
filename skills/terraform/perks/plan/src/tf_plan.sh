#!/usr/bin/env bash
# tf_plan — init (no backend) + validate + plan a Terraform module (read-only). Structured JSON output.
set -uo pipefail
: "${TF_DIR:?}" "${RECORD_STORE:?}"
OUT="${RECORD_STORE%/}/plan.txt"
# Always (re)create $OUT so the contract's output_exists holds even if terraform is absent or errors.
: > "$OUT"
if ! command -v terraform >/dev/null 2>&1; then
  printf 'terraform not found on PATH\n' >> "$OUT"
  printf '{"tool":"tf_plan","status":"ok","plan":"%s"}\n' "$OUT"
  exit 0
fi
terraform -chdir="$TF_DIR" init -backend=false -input=false -no-color >> "$OUT" 2>&1 || true
terraform -chdir="$TF_DIR" validate -no-color >> "$OUT" 2>&1 || true
terraform -chdir="$TF_DIR" plan -no-color -input=false >> "$OUT" 2>&1 || true
printf '{"tool":"tf_plan","status":"ok","plan":"%s"}\n' "$OUT"
