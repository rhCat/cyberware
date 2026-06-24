#!/usr/bin/env bash
# deploy/body-entrypoint.sh — boot a cyberware BODY inside the container: exod (the confined limb) + govd
# (delegated). Run by `chipfetch --exec` (the image CMD), so the chip is already cloud-fetched + VALIDATED and
# CYBERWARE_SKILLCHIP is exported — both exod and govd (this script's children) inherit it.
#
# Everything is minted ONCE into the mounted /data volume (keys, monitor token, an agent principal) and runs as
# the NON-ROOT image user; exod further drops each STEP to nobody (65534) inside its sandbox. govd is the
# foreground process (PID 1's child) so the container's lifecycle == govd's; exod is a supervised background
# child that dies with it.
set -euo pipefail
DATA="${GOVD_RECORD_ROOT:-/data/body}"
KEYS="$DATA/keys"; ETC="$DATA/etc"
SOCK="${EXOD_SOCKET:-$DATA/exod.sock}"
PORT="${GOVD_PORT:-5773}"
BACKEND="${EXOD_SANDBOX_BACKEND:-bwrap}"
mkdir -p "$KEYS" "$ETC"

# 1. keys — grant-issuer (govd) + exod identity, raw 32-byte Ed25519, dual-control (different keys), minted ONCE
if [ ! -f "$KEYS/exod.key" ]; then
  python3 - "$KEYS" <<'PY'
import os, sys
from cryptography.hazmat.primitives import serialization as S
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
K = sys.argv[1]
rp = lambda k: k.private_bytes(S.Encoding.Raw, S.PrivateFormat.Raw, S.NoEncryption())
ru = lambda k: k.public_key().public_bytes(S.Encoding.Raw, S.PublicFormat.Raw)
g, e = Ed25519PrivateKey.generate(), Ed25519PrivateKey.generate()
assert ru(g) != ru(e), "grant and exod keys must differ (dual control)"
for n, b in (("grant.key", rp(g)), ("grant.pub", ru(g)), ("exod.key", rp(e)), ("exod.pub", ru(e))):
    p = os.path.join(K, n); open(p, "wb").write(b); os.chmod(p, 0o600)
PY
fi

# 2. auth — a monitor token + an agent principal, minted ONCE. The plane is network-exposed (remote mode), so
#    auth MUST be on (govd refuses an exposed plane with auth off). The agent token is handed to the brain.
[ -f "$ETC/monitor.token" ] || { python3 -c "import secrets;print(secrets.token_hex(24))" > "$ETC/monitor.token"; chmod 600 "$ETC/monitor.token"; }
if [ ! -f "$ETC/principals.json" ]; then
  python3 - "$ETC" <<'PY'
import hashlib, json, os, secrets, sys
E = sys.argv[1]; tok = secrets.token_hex(24)
json.dump({"principals": {"agent-1": {"token_sha": hashlib.sha256(tok.encode()).hexdigest(),
                                      "rate": 2.0, "burst": 20}}}, open(os.path.join(E, "principals.json"), "w"))
open(os.path.join(E, "agent-1.token.GIVE-TO-AGENT"), "w").write(tok)
os.chmod(os.path.join(E, "principals.json"), 0o600); os.chmod(os.path.join(E, "agent-1.token.GIVE-TO-AGENT"), 0o400)
PY
  echo "[body] minted principal 'agent-1' — token at $ETC/agent-1.token.GIVE-TO-AGENT (hand to the brain, then delete)"
fi

# 3. govd config — DELEGATED to exod over the in-container UDS
cat > "$ETC/govd.json" <<JSON
{
  "mode": "remote",
  "remote": {"host": "0.0.0.0", "port": $PORT},
  "record_root": "$DATA",
  "principals_path": "$ETC/principals.json",
  "exec_mode": "delegated",
  "exod": {"socket": "$SOCK", "grant_key": "$KEYS/grant.key", "pub": "$KEYS/exod.pub"}
}
JSON

# 4. start exod — the ONLY thing that executes; non-root (we are the image's cyberware user), selected backend.
#    Run under `docker run --runtime=runsc` for sysctl-independent gVisor confinement, or with the bwrap default
#    under a runtime that permits unprivileged user namespaces.
python3 -m infra.exec.exod --socket "$SOCK" --key "$KEYS/exod.key" --issuer-pub "$KEYS/grant.pub" \
  --backend "$BACKEND" &
EXOD_PID=$!
trap 'kill "$EXOD_PID" 2>/dev/null || true' TERM INT EXIT
for _ in $(seq 1 100); do [ -S "$SOCK" ] && break; sleep 0.1; done
[ -S "$SOCK" ] || { echo "[body] exod socket never appeared — exod failed to start (backend=$BACKEND)"; exit 1; }
echo "[body] exod up (backend=$BACKEND, socket=$SOCK); starting govd (delegated) on :$PORT"

# 5. govd (delegated) in the foreground — reads the monitor token from its file; binds the container interface
#    (map it to the node's tailnet IP with `-p <tailnet-ip>:$PORT:$PORT`).
exec env GOVD_MONITOR_TOKEN="$(cat "$ETC/monitor.token")" GOVD_PRINCIPALS="$ETC/principals.json" \
  python3 -m infra.govern.govd --config "$ETC/govd.json" --mode remote --port "$PORT"
