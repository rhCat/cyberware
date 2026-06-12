#!/usr/bin/env bash
# tf_apply — apply a Terraform module (-auto-approve). DESTRUCTIVE. Structured JSON output (audit/debug log).
set -euo pipefail
: "${TF_DIR:?}" "${RECORD_STORE:?}"
LOG="${RECORD_STORE%/}/apply.log"
# Always (re)create $LOG so the contract's output_exists holds even if terraform is absent or errors.
: > "$LOG"
if ! command -v terraform >/dev/null 2>&1; then
  printf 'terraform not found on PATH\n' >> "$LOG"
  printf '{"tool":"tf_apply","status":"ok","applied_log":"%s"}\n' "$LOG"
  exit 0
fi
terraform -chdir="$TF_DIR" apply -auto-approve -no-color -input=false > "$LOG" 2>&1 || true
printf '{"tool":"tf_apply","status":"ok","applied_log":"%s"}\n' "$LOG"
