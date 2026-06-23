#!/usr/bin/env bash
# setup-confined-body.sh — provision a Linux box as a cyberware CONFINED BODY: native govd (delegated mode)
# + the exod limb (the only thing that executes; bwrap-confined, nobody/no-net) + skills, bound to the
# tailscale overlay. This is the on-node half of P2-T12. Run it natively (NOT in a container): bwrap's
# user-namespace confinement is clean on the host and finicky inside Docker.
#
# Trust model: cyberware does CONFINED COMPUTE only. govd governs the claim; exod runs the step confined and
# signs the authoritative status. NEITHER runs as root — both run as the '$CW_USER' service identity, and the
# confined step drops further to uid 65534 (nobody). Privileged host management is OUT of scope (operator /
# local agent, off-band). Dual-control: govd's grant-issuer key != exod's identity key (the script mints both).
#
# Source model: the body does NOT clone. It MOUNTS the canonical gallery (the same NAS the Mac updater keeps
# verified+current — fetch→ff→skillChip→authenticity-gate→revert-on-drift). CW_SRC points at that mount.
# Mount it READ-ONLY on the body: the body only ever reads/runs the source; only the Mac updater writes it.
# That is the "hook, not a per-node repo copy" shape — one verified source, every body reads the same commit.
#
# Usage (on the body, as a sudo-capable user; the gallery already mounted at CW_SRC):
#   sudo CW_SRC=/mnt/cywaregallery/cyberware bash deploy/setup-confined-body.sh
#
# Prereqs your hand, not mine: AWS/host firewall (overlay-only); tailscale already joined; the NAS gallery
# mounted (read-only) at CW_SRC with its skillChip submodule populated. Idempotent: safe to re-run (keys/
# tokens are minted once, never overwritten).
set -uo pipefail

CW_USER="cyberware"
CW_ETC="/etc/cyberware"
CW_KEYS="$CW_ETC/keys"
CW_DATA="/var/lib/cyberware"
CW_SRC="${CW_SRC:-/mnt/cywaregallery/cyberware}"    # the NAS-mounted canonical gallery (infra/ + skillChip/), read-only
GOVD_PORT="${GOVD_PORT:-5773}"
SOCK_DIR="/run/cyberware"
EXOD_SOCK="$SOCK_DIR/exod.sock"
PY="$(command -v python3)"

log(){ echo "[confined-body] $*"; }
[ "$(id -u)" = 0 ] || { echo "run with sudo (provisioning needs root; the runtime then drops to '$CW_USER'/nobody)"; exit 1; }
[ -f "$CW_SRC/infra/govern/govd.py" ] || { echo "gallery not mounted at CW_SRC=$CW_SRC (mount the NAS gallery read-only first; needs infra/ + skillChip/)"; exit 1; }
[ -d "$CW_SRC/skillChip" ] || { echo "skillChip missing under $CW_SRC — the mounted gallery's submodule isn't populated (the chip is the load set)"; exit 1; }
command -v tailscale >/dev/null || log "WARN: tailscale not found — join the tailnet first (govd binds the overlay IP)"

# 1. deps: bubblewrap = the confinement boundary; cryptography = grant/exod signing; age/jq/curl = plumbing
export DEBIAN_FRONTEND=noninteractive
log "apt: bubblewrap, uidmap, python3-cryptography, age, jq, curl"
apt-get update -qq
apt-get install -y --no-install-recommends bubblewrap uidmap python3 python3-venv python3-cryptography age jq curl ca-certificates >/dev/null

# 2. service identity (non-login) + dirs
id "$CW_USER" >/dev/null 2>&1 || useradd -r -s /usr/sbin/nologin -d "$CW_DATA" "$CW_USER"
install -d -m 0750 -o "$CW_USER" -g "$CW_USER" "$CW_ETC" "$CW_KEYS" "$CW_DATA" "$CW_DATA/govd"

# 3. the TWO keys — dual control: govd's grant-issuer key MUST differ from exod's identity key.
#    raw 32-byte Ed25519, as exod.main / govd._load_exec_mode expect. Minted once, 0400, never overwritten.
if [ ! -f "$CW_KEYS/grant.key" ]; then
  log "minting grant-issuer (govd) + identity (exod) keypairs"
  "$PY" - "$CW_KEYS" <<'PY'
import sys, os
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from cryptography.hazmat.primitives import serialization as s
d = sys.argv[1]
def priv(k): return k.private_bytes(s.Encoding.Raw, s.PrivateFormat.Raw, s.NoEncryption())
def pub(k):  return k.public_key().public_bytes(s.Encoding.Raw, s.PublicFormat.Raw)
grant = Ed25519PrivateKey.generate(); exod = Ed25519PrivateKey.generate()
assert pub(grant) != pub(exod), "grant and exod keys must differ"
for name, blob in [("grant.key", priv(grant)), ("grant.pub", pub(grant)),
                   ("exod.key", priv(exod)),   ("exod.pub", pub(exod))]:
    open(os.path.join(d, name), "wb").write(blob)
PY
  chmod 0400 "$CW_KEYS"/*.key; chmod 0444 "$CW_KEYS"/*.pub
  chown -R "$CW_USER:$CW_USER" "$CW_KEYS"
fi

# 4. principals registry (agent Bearer auth) + monitor token — same as the control plane
if [ ! -f "$CW_ETC/monitor.token" ]; then
  umask 077; openssl rand -hex 24 > "$CW_ETC/monitor.token"; chown "$CW_USER:$CW_USER" "$CW_ETC/monitor.token"
fi
if [ ! -f "$CW_ETC/principals.json" ]; then
  AGENT_TOKEN="$(openssl rand -hex 24)"; SHA="$(printf %s "$AGENT_TOKEN" | sha256sum | cut -d' ' -f1)"
  printf '{"principals":{"agent-1":{"token_sha":"%s","rate":2.0,"burst":20}}}\n' "$SHA" > "$CW_ETC/principals.json"
  chown "$CW_USER:$CW_USER" "$CW_ETC/principals.json"
  echo "$AGENT_TOKEN" > "$CW_ETC/agent-1.token.GIVE-TO-AGENT-THEN-DELETE"; chmod 0400 "$CW_ETC/agent-1.token.GIVE-TO-AGENT-THEN-DELETE"
  log "minted principal 'agent-1' — token in $CW_ETC/agent-1.token.GIVE-TO-AGENT-THEN-DELETE (hand to the brain, then delete)"
fi

# 5. govd config — DELEGATED mode, pointing at the exod socket + the two keys. Bound to the overlay IP.
TS_IP="$(tailscale ip -4 2>/dev/null | head -1)"
BIND_HOST="${TS_IP:-127.0.0.1}"
[ -n "$TS_IP" ] || log "WARN: no tailscale IP — binding 127.0.0.1 (fleet can't reach it; re-run once tailscale is up)"
cat > "$CW_ETC/govd.json" <<JSON
{
  "mode": "remote",
  "remote": {"host": "$BIND_HOST", "port": $GOVD_PORT},
  "record_root": "$CW_DATA/govd",
  "principals_path": "$CW_ETC/principals.json",
  "exec_mode": "delegated",
  "exod": {"socket": "$EXOD_SOCK", "grant_key": "$CW_KEYS/grant.key", "pub": "$CW_KEYS/exod.pub"}
}
JSON
chown "$CW_USER:$CW_USER" "$CW_ETC/govd.json"

# 6. systemd units — both run as $CW_USER (never root). RuntimeDirectory makes /run/cyberware (the socket dir).
#    exod first (govd dials its socket). exod confines each step in bwrap -> nobody.
cat > /etc/systemd/system/cyberware-exod.service <<UNIT
[Unit]
Description=cyberware exod (the confined limb — the only thing that executes)
After=network-online.target
Wants=network-online.target
[Service]
User=$CW_USER
WorkingDirectory=$CW_SRC
RuntimeDirectory=cyberware
RuntimeDirectoryMode=0750
ExecStart=$PY -m infra.exec.exod --socket $EXOD_SOCK --key $CW_KEYS/exod.key --issuer-pub $CW_KEYS/grant.pub
Restart=always
RestartSec=5
[Install]
WantedBy=multi-user.target
UNIT

cat > /etc/systemd/system/cyberware-govd.service <<UNIT
[Unit]
Description=cyberware govd (governance/audit plane; never executes) — delegated to exod
After=network-online.target tailscaled.service cyberware-exod.service
Wants=network-online.target
Requires=cyberware-exod.service
[Service]
User=$CW_USER
WorkingDirectory=$CW_SRC
Environment=GOVD_CONFIG=$CW_ETC/govd.json
Environment=GOVD_RECORD_ROOT=$CW_DATA/govd
Environment=GOVD_PRINCIPALS=$CW_ETC/principals.json
ExecStart=/usr/bin/env bash -c 'GOVD_MONITOR_TOKEN="\$(cat $CW_ETC/monitor.token)" $PY -m infra.govern.govd --config $CW_ETC/govd.json --mode remote --port $GOVD_PORT'
Restart=always
RestartSec=5
[Install]
WantedBy=multi-user.target
UNIT

systemctl daemon-reload
systemctl enable --now cyberware-exod cyberware-govd >/dev/null 2>&1 || true
sleep 3
log "exod socket: $([ -S "$EXOD_SOCK" ] && echo present || echo MISSING)"
if curl -fsS -m 5 "http://$BIND_HOST:$GOVD_PORT/health" >/dev/null 2>&1; then
  EM="$(curl -fsS "http://$BIND_HOST:$GOVD_PORT/health" | grep -o '"exec_mode":"[^"]*"' || echo '(exec_mode field absent — old image?)')"
  log "govd healthy on $BIND_HOST:$GOVD_PORT · $EM"
else
  log "WARN: govd /health not ready — check: journalctl -u cyberware-govd -u cyberware-exod"
fi

cat <<DONE

==================== confined body ready (govd + exod, delegated) — YOUR remaining steps ====================
1. Firewall (host/AWS): $GOVD_PORT reachable ONLY over the overlay (the tailnet), never public.
2. Verify delegated mode: curl http://$BIND_HOST:$GOVD_PORT/health  -> should show "exec_mode":"delegated","exod_attached":true
   (needs the hardened image/code with #136; an old cooperative build won't show these fields.)
3. Hand 'agent-1' token (in $CW_ETC/agent-1.token.GIVE-TO-AGENT-THEN-DELETE) to the brain, then delete it.
4. Confined execution is REAL only on Linux+bwrap (this host). exod refuses to run unconfined anywhere else.
=============================================================================================================
DONE
