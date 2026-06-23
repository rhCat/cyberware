#!/usr/bin/env bash
# setup-edge-anchor-user.sh — ROOTLESS cooperative govd ANCHOR, entirely under $HOME. The cloud-edge twin of
# setup-confined-body.sh's model, but matching the under-~ rootless principle: NO Docker, NO /etc, NO system
# units, NO sudo for the runtime. govd governs + records (COOPERATIVE — no exod, it never executes), runs as
# YOU via `systemctl --user`, bound ONLY to the tailscale overlay IP (never the public cloud interface).
#
# Source: the edge can't mount the NAS gallery, so it keeps a LOCAL clone under ~ (you have SSH read access
# to the repo — the same access the runner uses). cryptography goes in a venv under ~ (Ubuntu 24.04's PEP-668
# blocks `pip --user`); it's needed because govd imports it transitively on startup (delegate -> exodverify).
# Running as you, reading ~-owned files, means the uid/permission friction of the containerized model is gone.
#
# Usage (as your normal user; you have SSH read access to the repo):
#   bash deploy/setup-edge-anchor-user.sh
# Idempotent: safe to re-run (clone is fast-forwarded; keys/tokens minted once).
set -uo pipefail

CW_BASE="${CW_BASE:-$HOME/cyberware}"                 # all state under ~ (never /)
CW_SRC="${CW_SRC:-$CW_BASE/src}"                       # local clone of the source (no NAS to mount)
REPO="${REPO:-git@github.com:rhCat/cyberware.git}"
GOVD_PORT="${GOVD_PORT:-5773}"
ETC="$CW_BASE/etc"; DATA="$CW_BASE/data/govd"; VENV="$CW_BASE/venv"
UNITS="$HOME/.config/systemd/user"
SYS_PY="$(command -v python3 || true)"

log(){ echo "[edge-anchor] $*"; }
[ "$(id -u)" != 0 ] || { echo "run as your NORMAL user, NOT root — this is the rootless, ~-rooted edge anchor"; exit 1; }
[ -n "$SYS_PY" ] || { echo "python3 not found"; exit 1; }
[[ "$GOVD_PORT" =~ ^[0-9]+$ ]] || { echo "GOVD_PORT must be numeric (got: $GOVD_PORT)"; exit 1; }
command -v git >/dev/null || { echo "git not found"; exit 1; }
command -v tailscale >/dev/null || log "WARN: tailscale not found — govd binds the overlay IP"

# refuse a DUPLICATE governance plane: an OLD containerized/system govd on this host (it binds 127.0.0.1 and
# we bind the tailnet IP, so not a literal port clash — two govd planes is the hazard). Tear it down first.
if { command -v docker >/dev/null && docker ps --filter name=cyberware-govd --format '{{.Names}}' 2>/dev/null | grep -q cyberware-govd; } \
   || systemctl is-active --quiet cyberware-govd 2>/dev/null; then
  echo "the containerized/system cyberware-govd is still running (it holds port $GOVD_PORT) — tear it down first:"
  echo "  sudo systemctl disable --now cyberware-govd; docker rm -f cyberware-govd 2>/dev/null"
  echo "  sudo rm -f /etc/systemd/system/cyberware-govd.service /usr/local/bin/cyberware-govd-run.sh; sudo systemctl daemon-reload"
  exit 1
fi

umask 077
mkdir -p "$ETC" "$DATA" "$UNITS"

# 1. source — a local clone (the edge can't mount the NAS). Cloned once; re-runs fast-forward it.
if [ ! -d "$CW_SRC/.git" ]; then
  log "cloning source -> $CW_SRC (needs your SSH read access to BOTH cyberware.git AND the skillChip.git submodule)"
  git clone --recursive "$REPO" "$CW_SRC" || { echo "clone failed — do you have SSH read access to the repo + skillChip submodule?"; exit 1; }
else
  log "updating existing clone at $CW_SRC"
  git -C "$CW_SRC" fetch -q origin main \
    && git -C "$CW_SRC" merge --ff-only origin/main >/dev/null 2>&1 \
    || log "WARN: ff-only update failed (network down or non-ff upstream) — keeping current source"
  # do NOT swallow a submodule auth failure: a chip-less govd would start green and govern an empty registry
  git -C "$CW_SRC" submodule update --init --recursive >/dev/null 2>&1 \
    || { echo "skillChip submodule update FAILED — you need SSH read access to git@github.com:rhCat/skillChip.git too"; exit 1; }
fi
[ -f "$CW_SRC/infra/govern/govd.py" ] || { echo "source incomplete at $CW_SRC (infra/ missing)"; exit 1; }
# the chip is what govd governs — refuse a chip-less anchor (would pass /health but /catalog would be empty)
[ -f "$CW_SRC/skillChip/index.json" ] || { echo "skillChip cartridge missing at $CW_SRC/skillChip — clone --recursive needs skillChip.git access"; exit 1; }

# 2. cryptography in a venv under ~ (govd imports it on startup; PEP-668-safe, fully rootless)
# guard on pip (not python3): a partial venv (python3-venv without ensurepip) leaves bin/python3 but no pip
if [ ! -x "$VENV/bin/pip" ]; then
  log "creating venv $VENV"
  rm -rf "$VENV"
  "$SYS_PY" -m venv "$VENV" || { echo "venv create failed — one-time root step: sudo apt install -y python3-venv"; exit 1; }
  [ -x "$VENV/bin/pip" ] || { echo "venv has no pip (ensurepip missing) — one-time root step: sudo apt install -y python3-venv, then re-run"; rm -rf "$VENV"; exit 1; }
fi
"$VENV/bin/python3" -c "import cryptography" 2>/dev/null \
  || "$VENV/bin/pip" install --quiet cryptography==49.0.0 \
  || { echo "pip install cryptography into the venv failed (network?)"; exit 1; }
PY="$VENV/bin/python3"
# the venv python must also see the source's infra/ — it does, via WorkingDirectory=$CW_SRC (cwd on sys.path)
( cd "$CW_SRC" && "$PY" -c "import infra.govern.govd" ) >/dev/null 2>&1 \
  && log "govd import chain OK (venv python + source)" || { echo "govd import failed under the venv — check cryptography/source"; exit 1; }

# 3. principals + monitor token — under ~, owned by YOU (no container-uid mismatch ever)
[ -f "$ETC/monitor.token" ] || { openssl rand -hex 24 > "$ETC/monitor.token"; chmod 0600 "$ETC/monitor.token"; }
if [ ! -f "$ETC/principals.json" ]; then
  AT="$(openssl rand -hex 24)"; SHA="$(printf %s "$AT" | sha256sum | cut -d' ' -f1)"
  printf '{"principals":{"agent-1":{"token_sha":"%s","rate":2.0,"burst":20}}}\n' "$SHA" > "$ETC/principals.json"; chmod 0600 "$ETC/principals.json"
  echo "$AT" > "$ETC/agent-1.token.GIVE-TO-AGENT-THEN-DELETE"; chmod 0400 "$ETC/agent-1.token.GIVE-TO-AGENT-THEN-DELETE"
  log "minted principal 'agent-1' — token in $ETC/agent-1.token.GIVE-TO-AGENT-THEN-DELETE (hand to the brain, then delete)"
fi

# 4. govd config — COOPERATIVE (no exod block → never executes), bound ONLY to the tailscale IP
TS_IP="$(tailscale ip -4 2>/dev/null | head -1)"; BIND_HOST="${TS_IP:-127.0.0.1}"
[ -n "$TS_IP" ] || log "WARN: no tailscale IP — binding 127.0.0.1 (re-run once tailscale is up; do NOT bind 0.0.0.0 on a cloud node)"
cat > "$ETC/govd.json" <<JSON
{
  "mode": "remote",
  "remote": {"host": "$BIND_HOST", "port": $GOVD_PORT},
  "record_root": "$DATA",
  "principals_path": "$ETC/principals.json"
}
JSON

# 5. systemd --user unit (no root). govd binds remote.host from the config = the tailscale IP.
cat > "$UNITS/cyberware-govd.service" <<UNIT
[Unit]
Description=cyberware govd (rootless edge anchor — cooperative; governs + records, never executes)
# (no After=network-online.target — a --user unit can't order on the system target; Restart=always covers a not-yet-up tailnet)
[Service]
WorkingDirectory=$CW_SRC
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
systemctl --user enable cyberware-govd >/dev/null 2>&1 || true
systemctl --user restart cyberware-govd            # restart (not just --now) so a RE-RUN applies the rewritten govd.json
loginctl enable-linger "$(id -un)" 2>/dev/null || true   # needs root via polkit; verified + warned below
LINGER="$(loginctl show-user "$(id -un)" -p Linger --value 2>/dev/null || echo no)"
sleep 3

if curl -fsS -m 5 "http://$BIND_HOST:$GOVD_PORT/health" >/dev/null 2>&1; then
  log "govd healthy on $BIND_HOST:$GOVD_PORT · $(curl -fsS "http://$BIND_HOST:$GOVD_PORT/health" | grep -o '"exec_mode":"[^"]*"')"
else
  log "WARN: govd /health not ready — check: systemctl --user status cyberware-govd ; journalctl --user -u cyberware-govd -n 40"
fi
[ "$LINGER" = yes ] || log "‼ LINGER NOT ENABLED — the anchor will DIE when you log out. One-time: sudo loginctl enable-linger $(id -un)"

cat <<DONE

============ rootless edge anchor (cooperative govd) — entirely under \$HOME ============
state     : $CW_BASE   (etc, data/govd, src, venv — nothing on /, no Docker, no /etc)
source    : $CW_SRC   (local clone; keep current with: git -C $CW_SRC pull --ff-only && systemctl --user restart cyberware-govd)
unit      : systemctl --user {status,restart} cyberware-govd
logs      : journalctl --user -u cyberware-govd -f
verify    : curl http://$BIND_HOST:$GOVD_PORT/health   ->  "exec_mode":"cooperative"  (binds the tailnet IP only)
linger    : $([ "$LINGER" = yes ] && echo "enabled" || echo "NOT enabled ‼ — run: sudo loginctl enable-linger $(id -un)  (else the anchor dies on logout)")
token     : hand $ETC/agent-1.token.GIVE-TO-AGENT-THEN-DELETE to the brain, then delete it
NOTE: this REPLACES the containerized govd. Tear that down first:
  sudo systemctl disable --now cyberware-govd 2>/dev/null; docker rm -f cyberware-govd 2>/dev/null
  sudo rm -f /etc/systemd/system/cyberware-govd.service /usr/local/bin/cyberware-govd-run.sh; sudo systemctl daemon-reload
=========================================================================================
DONE
