#!/usr/bin/env bash
# ssh_check — non-interactive SSH connectivity probe (read-only). Structured JSON output (audit/debug log).
set -uo pipefail
: "${SSH_HOST:?}" "${SSH_USER:?}" "${RECORD_STORE:?}"
KEY="${SSH_KEY_FILE:-}"                         # optional: a private-key PATH passed to ssh -i (never inline secret)
OUT="${RECORD_STORE%/}/ssh_check.json"
# BatchMode=yes => never prompt; ConnectTimeout bounds the hang; accept-new trusts a first-seen host key.
# `true` is a no-op on the remote — this probes reachability + auth without changing anything.
if ssh -o BatchMode=yes -o ConnectTimeout=5 -o StrictHostKeyChecking=accept-new \
       ${KEY:+-i "$KEY"} "$SSH_USER@$SSH_HOST" true >/dev/null 2>&1; then
  REACHABLE=true
else
  REACHABLE=false
fi
# ALWAYS write the result — reachable true|false — so the contract's output_exists holds either way.
printf '{"host":"%s","user":"%s","reachable":%s}\n' "$SSH_HOST" "$SSH_USER" "$REACHABLE" > "$OUT"
printf '{"tool":"ssh_check","status":"ok","reachable":%s,"report":"%s"}\n' "$REACHABLE" "$OUT"
