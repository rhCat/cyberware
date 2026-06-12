#!/usr/bin/env bash
# ssh_run — run a vetted command on a remote host over SSH (destructive). Structured JSON output (audit/debug log).
set -euo pipefail
: "${SSH_HOST:?}" "${SSH_USER:?}" "${COMMAND:?}" "${RECORD_STORE:?}"
KEY="${SSH_KEY_FILE:-}"                         # optional: a private-key PATH passed to ssh -i (never inline secret)
LOG="${RECORD_STORE%/}/ssh_output.log"
# BatchMode=yes => never prompt; accept-new trusts a first-seen host key. Capture stdout+stderr into LOG.
# `|| true` keeps the step from aborting under `set -e` on a non-zero remote exit, so LOG always exists.
ssh -o BatchMode=yes -o StrictHostKeyChecking=accept-new \
    ${KEY:+-i "$KEY"} "$SSH_USER@$SSH_HOST" "$COMMAND" > "$LOG" 2>&1 || true
printf '{"tool":"ssh_run","status":"ok","output_log":"%s"}\n' "$LOG"
