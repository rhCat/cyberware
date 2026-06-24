#!/usr/bin/env bash
# setup-confined-body-user.sh — ROOTLESS confined body, entirely under $HOME. For hosts with a tight or
# write-restricted / (e.g. an NVIDIA DGX, where you "always work on ~"): NO writes to /, NO system user,
# NO sudo for the runtime. All state lives under ~, the units are `systemctl --user`, and everything runs
# as YOU. This is the home-rooted twin of deploy/setup-confined-body.sh (which uses /etc + a system user).
#
# Confinement is still REAL: exod confines each step with bwrap in an UNPRIVILEGED user namespace (the
# kernel boundary needs no root on Linux) and drops the step to uid 65534. Bonus: running as the user who
# MOUNTED the gallery means it can actually read CW_SRC — no cross-user mount-permission gap.
#
# Usage (as your normal user; the gallery mounted at CW_SRC and readable by you):
#   CW_SRC=/mnt/cywaregallery/cyberware bash deploy/setup-confined-body-user.sh
#
# Only-root prereq (one time, IF a dep is missing — the script tells you):
#   sudo apt install -y bubblewrap uidmap            # bwrap = the confinement boundary
#   # 'cryptography' can go rootless too: pip install --user cryptography
# Idempotent: safe to re-run (keys/tokens minted once, never overwritten).
set -uo pipefail

CW_SRC="${CW_SRC:-/mnt/cywaregallery/cyberware}"      # the gallery YOU mounted (read)
CW_BASE="${CW_BASE:-$HOME/cyberware}"                 # ALL runtime state lives here, under ~ (never /)
GOVD_PORT="${GOVD_PORT:-5773}"
BACKEND="${EXOD_SANDBOX_BACKEND:-bwrap}"              # P2-T04: confinement backend — bwrap (default) | runsc (gVisor)
XRD="${XDG_RUNTIME_DIR:-/run/user/$(id -u)}"          # tmpfs runtime dir (RAM) — the socket lives here, not on /
EXOD_SOCK="$XRD/cyberware/exod.sock"
ETC="$CW_BASE/etc"; KEYS="$ETC/keys"; DATA="$CW_BASE/data/govd"
UNITS="$HOME/.config/systemd/user"
PY="$(command -v python3 || true)"

log(){ echo "[confined-body-user] $*"; }
[ "$(id -u)" != 0 ] || { echo "run as your NORMAL user, NOT root — this is the rootless, ~-rooted deploy (use setup-confined-body.sh for the system/root model)"; exit 1; }
[ -n "$PY" ] || { echo "python3 not found"; exit 1; }
[ -f "$CW_SRC/infra/govern/govd.py" ] || { echo "gallery not at CW_SRC=$CW_SRC — mount it (and it must be readable by you)"; exit 1; }
[ -r "$CW_SRC/infra/exec/exod.py" ] || { echo "cannot READ $CW_SRC (mount perms) — you must be able to read the gallery you mounted"; exit 1; }
if [ "$BACKEND" = "runsc" ]; then
  command -v runsc >/dev/null || { echo "gVisor (runsc) missing for EXOD_SANDBOX_BACKEND=runsc — install runsc (https://gvisor.dev/docs/user_guide/install/), then re-run"; exit 1; }
else
  command -v bwrap >/dev/null || { echo "bubblewrap (bwrap) missing — one-time root step: sudo apt install -y bubblewrap uidmap"; exit 1; }
fi
"$PY" -c "import cryptography" 2>/dev/null || { echo "python 'cryptography' missing — rootless: pip install --user cryptography  (or one-time root: sudo apt install -y python3-cryptography)"; exit 1; }

# the chosen confinement backend must ACTUALLY work on this kernel. Fail early, loudly — never deploy a limb
# that can't confine (exod fail-closes per step, but the operator should know NOW, not via errored steps).
if [ "$BACKEND" = "runsc" ]; then
  if ! runsc --rootless do true >/tmp/cw_runsc.$$ 2>&1; then
    echo "runsc smoke FAILED — gVisor cannot confine on this host:"; sed 's/^/    /' /tmp/cw_runsc.$$
    rm -f /tmp/cw_runsc.$$
    echo "  rootless runsc still needs unprivileged user namespaces for setup; the Sentry is the isolation, but"
    echo "  the rootless bootstrap is not. one-time root fix (same as bwrap): sudo sysctl -w kernel.apparmor_restrict_unprivileged_userns=0"
    echo "  (persist in /etc/sysctl.d/). Or run runsc with a privileged platform. Without it exod refuses, never runs unconfined."
    exit 1
  fi
  rm -f /tmp/cw_runsc.$$
  log "runsc OK — gVisor confinement is enforceable on this host"
else
  # rootless confinement must ACTUALLY work on this kernel (unprivileged user namespaces). Fail early, loudly.
  if ! bwrap --unshare-user --uid 65534 --gid 65534 --ro-bind / / true 2>/tmp/cw_bwrap.$$; then
    echo "rootless bwrap smoke FAILED — unprivileged user namespaces appear DISABLED on this kernel:"; sed 's/^/    /' /tmp/cw_bwrap.$$
    rm -f /tmp/cw_bwrap.$$
    echo "  one-time root fix: sudo sysctl -w kernel.apparmor_restrict_unprivileged_userns=0   (Ubuntu 24.04+)"
    echo "  or: sudo sysctl -w kernel.unprivileged_userns_clone=1 ; sudo sysctl -w user.max_user_namespaces=10000"
    echo "  (persist via a file in /etc/sysctl.d/). Without it, exod cannot confine and refuses to run unconfined."
    exit 1
  fi
  rm -f /tmp/cw_bwrap.$$
  log "rootless bwrap OK — unprivileged userns works; confinement is enforceable"
fi

umask 077
mkdir -p "$ETC" "$KEYS" "$DATA" "$UNITS" "$XRD/cyberware"

# keys — dual control: grant-issuer (govd) key != exod identity key. raw 32-byte Ed25519. Minted once.
if [ ! -f "$KEYS/grant.key" ]; then
  log "minting grant-issuer (govd) + identity (exod) keypairs under $KEYS"
  "$PY" - "$KEYS" <<'PYK'
import sys, os
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from cryptography.hazmat.primitives import serialization as s
d = sys.argv[1]
priv = lambda k: k.private_bytes(s.Encoding.Raw, s.PrivateFormat.Raw, s.NoEncryption())
pub  = lambda k: k.public_key().public_bytes(s.Encoding.Raw, s.PublicFormat.Raw)
g = Ed25519PrivateKey.generate(); e = Ed25519PrivateKey.generate()
assert pub(g) != pub(e), "grant and exod keys must differ"
for n, b in [("grant.key", priv(g)), ("grant.pub", pub(g)), ("exod.key", priv(e)), ("exod.pub", pub(e))]:
    open(os.path.join(d, n), "wb").write(b)
PYK
  chmod 0400 "$KEYS"/*.key; chmod 0444 "$KEYS"/*.pub
fi

# monitor token + principals registry (agent bearer auth)
[ -f "$ETC/monitor.token" ] || { openssl rand -hex 24 > "$ETC/monitor.token"; chmod 0400 "$ETC/monitor.token"; }
if [ ! -f "$ETC/principals.json" ]; then
  AT="$(openssl rand -hex 24)"; SHA="$(printf %s "$AT" | sha256sum | cut -d' ' -f1)"
  printf '{"principals":{"agent-1":{"token_sha":"%s","rate":2.0,"burst":20}}}\n' "$SHA" > "$ETC/principals.json"; chmod 0600 "$ETC/principals.json"
  echo "$AT" > "$ETC/agent-1.token.GIVE-TO-AGENT-THEN-DELETE"; chmod 0400 "$ETC/agent-1.token.GIVE-TO-AGENT-THEN-DELETE"
  log "minted principal 'agent-1' — token in $ETC/agent-1.token.GIVE-TO-AGENT-THEN-DELETE (hand to the brain, then delete)"
fi

# govd config — DELEGATED, exod over the XDG socket, record_root + everything under ~
TS_IP="$(tailscale ip -4 2>/dev/null | head -1)"; BIND_HOST="${TS_IP:-127.0.0.1}"
[ -n "$TS_IP" ] || log "WARN: no tailscale IP — binding 127.0.0.1 (fleet can't reach it; re-run once tailscale is up)"
cat > "$ETC/govd.json" <<JSON
{
  "mode": "remote",
  "remote": {"host": "$BIND_HOST", "port": $GOVD_PORT},
  "record_root": "$DATA",
  "principals_path": "$ETC/principals.json",
  "exec_mode": "delegated",
  "exod": {"socket": "$EXOD_SOCK", "grant_key": "$KEYS/grant.key", "pub": "$KEYS/exod.pub"}
}
JSON

# systemd --user units (no root). RuntimeDirectory makes %t/cyberware (= $XDG_RUNTIME_DIR/cyberware = $EXOD_SOCK's dir).
cat > "$UNITS/cyberware-exod.service" <<UNIT
[Unit]
Description=cyberware exod (rootless confined limb — the only thing that executes)
After=network-online.target
[Service]
WorkingDirectory=$CW_SRC
Environment=PYTHONDONTWRITEBYTECODE=1
RuntimeDirectory=cyberware
RuntimeDirectoryMode=0750
ExecStart=$PY -m infra.exec.exod --socket $EXOD_SOCK --key $KEYS/exod.key --issuer-pub $KEYS/grant.pub --backend $BACKEND
Restart=always
RestartSec=5
[Install]
WantedBy=default.target
UNIT

cat > "$UNITS/cyberware-govd.service" <<UNIT
[Unit]
Description=cyberware govd (governance/audit; never executes) — delegated to exod
After=network-online.target cyberware-exod.service
Requires=cyberware-exod.service
[Service]
WorkingDirectory=$CW_SRC
RuntimeDirectory=cyberware
RuntimeDirectoryMode=0750
Environment=PYTHONDONTWRITEBYTECODE=1
Environment=GOVD_CONFIG=$ETC/govd.json
Environment=GOVD_RECORD_ROOT=$DATA
Environment=GOVD_PRINCIPALS=$ETC/principals.json
ExecStart=/usr/bin/env bash -c 'GOVD_MONITOR_TOKEN="\$(cat $ETC/monitor.token)" $PY -m infra.govern.govd --config $ETC/govd.json --mode remote --port $GOVD_PORT'
Restart=always
RestartSec=5
[Install]
WantedBy=default.target
UNIT

systemctl --user daemon-reload
systemctl --user enable --now cyberware-exod cyberware-govd >/dev/null 2>&1 || true
# keep the user units alive without an active login session (this is a server role)
loginctl enable-linger "$(id -un)" 2>/dev/null \
  || log "NOTE: enable linger so the units survive logout — one-time: sudo loginctl enable-linger $(id -un)"
sleep 3

log "exod socket: $([ -S "$EXOD_SOCK" ] && echo present || echo MISSING)"
if curl -fsS -m 5 "http://$BIND_HOST:$GOVD_PORT/health" >/dev/null 2>&1; then
  log "govd healthy on $BIND_HOST:$GOVD_PORT · $(curl -fsS "http://$BIND_HOST:$GOVD_PORT/health" | grep -o '"exec_mode":"[^"]*"')"
else
  log "WARN: govd /health not ready — check: systemctl --user status cyberware-exod cyberware-govd ; journalctl --user -u cyberware-exod -u cyberware-govd -n 40"
fi

cat <<DONE

============ rootless confined body (govd + exod, delegated) — entirely under \$HOME ============
state     : $CW_BASE   (etc/keys, data/govd — nothing on /)
socket    : $EXOD_SOCK (tmpfs)
units     : systemctl --user {status,restart} cyberware-exod cyberware-govd
logs      : journalctl --user -u cyberware-exod -u cyberware-govd -f
verify    : curl http://$BIND_HOST:$GOVD_PORT/health   ->  "exec_mode":"delegated","exod_attached":true
linger    : sudo loginctl enable-linger $(id -un)   (so it runs when you're logged out)
token     : hand $ETC/agent-1.token.GIVE-TO-AGENT-THEN-DELETE to the brain, then delete it
=================================================================================================
DONE
