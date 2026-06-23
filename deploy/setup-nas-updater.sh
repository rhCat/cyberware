#!/usr/bin/env bash
# setup-nas-updater.sh — install the cyberware SOURCE UPDATER on a Linux host that mounts the canonical
# gallery read-WRITE. This host is the ONE writer of the gallery (cyberware's BUILD_TRIGGER analog); the
# confined bodies mount the same gallery read-ONLY and only ever read the verified commit it publishes.
#
# Why a Linux host and not the Mac: the gallery lives on an SMB share. macOS TCC blocks launchd background
# agents from doing file I/O on network volumes ("Operation not permitted"), so the Mac can't run the timer.
# A Linux box that mounts the share natively (e.g. the DGX / alembic-worker host) has no such restriction.
#
# What it does each tick: git fetch origin main -> fast-forward only -> submodule (skillChip) update ->
# AUTHENTICITY GATE (python3 -m infra.tool.skill_index --check) -> revert-on-drift. It NEVER advances the
# gallery onto a non-fast-forward or a chip that fails its own committed hashes — the kernel the bodies
# enforce governance with only ever moves to a verified commit.
#
# Usage (as a sudo-capable user on the updater host; the gallery already mounted read-WRITE at CW_GALLERY):
#   sudo CW_GALLERY=/mnt/cywaregallery/cyberware bash deploy/setup-nas-updater.sh
#
# Knobs (env): CW_GALLERY (the rw gallery clone) · INTERVAL (seconds between ticks, default 600) ·
#   RUN_USER (the identity the timer runs as — MUST have rw access to the mount; defaults to the invoking
#   sudo user, since SMB/NFS mounts are typically owned by a specific uid, not root).
# Idempotent: safe to re-run (rewrites the script + units, re-enables the timer).
set -uo pipefail

CW_GALLERY="${CW_GALLERY:-/mnt/cywaregallery/cyberware}"
INTERVAL="${INTERVAL:-600}"
RUN_USER="${RUN_USER:-${SUDO_USER:-root}}"
BIN="/usr/local/bin/cyberware-source-update.sh"
PY="$(command -v python3 || true)"

log(){ echo "[nas-updater] $*"; }
[ "$(id -u)" = 0 ] || { echo "run with sudo (installs a systemd unit + timer)"; exit 1; }
[ -n "$PY" ] || { echo "python3 not found (needed for the chip authenticity gate)"; exit 1; }
[ -d "$CW_GALLERY/.git" ] || { echo "no git clone at CW_GALLERY=$CW_GALLERY — mount the NAS gallery (read-write) there first"; exit 1; }
[ -f "$CW_GALLERY/infra/tool/skill_index.py" ] || { echo "$CW_GALLERY doesn't look like the cyberware gallery (infra/tool/skill_index.py missing)"; exit 1; }
# the updater must be able to WRITE the mount as RUN_USER — verify before we wire a timer that would only fail
if ! sudo -u "$RUN_USER" test -w "$CW_GALLERY/.git"; then
  echo "RUN_USER='$RUN_USER' cannot write $CW_GALLERY/.git — set RUN_USER to the uid that owns the mount (this host is the gallery's WRITER)"; exit 1
fi

# 1. the updater script (substitutes the gallery path; logs to journald via the oneshot service)
log "writing $BIN (gallery=$CW_GALLERY)"
cat > "$BIN" <<UPDATER
#!/usr/bin/env bash
# cyberware-source-update.sh — keep the canonical gallery current with verified main. Installed by
# deploy/setup-nas-updater.sh; run by the cyberware-source-update.timer. Logs to journald.
set -uo pipefail
SRC="$CW_GALLERY"
log(){ echo "[\$(date '+%F %T')] \$*"; }
[ -d "\$SRC/.git" ] || { log "gallery not present at \$SRC (NAS mounted rw?) — skip"; exit 0; }
cd "\$SRC" || { log "cannot cd \$SRC — skip"; exit 0; }
if ! git fetch --quiet origin main 2>/tmp/cw_fetch.\$\$; then
  log "fetch failed: \$(tr '\n' ' ' </tmp/cw_fetch.\$\$ | tail -c 180)"; rm -f /tmp/cw_fetch.\$\$; exit 0
fi
rm -f /tmp/cw_fetch.\$\$
LOCAL="\$(git rev-parse HEAD 2>/dev/null)"; REMOTE="\$(git rev-parse origin/main 2>/dev/null)"
[ -n "\$REMOTE" ] || { log "no origin/main — skip"; exit 0; }
[ "\$LOCAL" = "\$REMOTE" ] && exit 0                       # already current — stay quiet
log "advancing \$LOCAL -> \$REMOTE"
git merge --ff-only origin/main >/dev/null 2>&1 || { log "NON-fast-forward (local diverged) — manual intervention; NOT touching the bodies' source"; exit 1; }
git submodule update --init --recursive >/dev/null 2>&1   # keep the chip (skillChip) at its pinned commit
if python3 -m infra.tool.skill_index --check >/dev/null 2>&1; then
  log "updated to \$REMOTE · chip authentic OK"
else
  log "CHIP AUTHENTICITY FAILED at \$REMOTE — REVERTING to \$LOCAL (bodies keep the last good source)"
  git reset --hard "\$LOCAL" >/dev/null 2>&1
  git submodule update --init --recursive >/dev/null 2>&1
  exit 1
fi
UPDATER
chmod 0755 "$BIN"

# 2. systemd oneshot service + timer (every \$INTERVAL seconds). Runs as RUN_USER (owns the mount), not root.
cat > /etc/systemd/system/cyberware-source-update.service <<UNIT
[Unit]
Description=cyberware source updater (advance the NAS gallery to verified main)
After=network-online.target remote-fs.target
Wants=network-online.target
[Service]
Type=oneshot
User=$RUN_USER
ExecStart=$BIN
UNIT

cat > /etc/systemd/system/cyberware-source-update.timer <<UNIT
[Unit]
Description=run the cyberware source updater every ${INTERVAL}s
[Timer]
OnBootSec=2min
OnUnitActiveSec=${INTERVAL}
Persistent=true
[Install]
WantedBy=timers.target
UNIT

systemctl daemon-reload
systemctl enable --now cyberware-source-update.timer >/dev/null 2>&1 || true

# 3. run once now to prove the whole chain (fetch -> ff -> chip gate) works as RUN_USER
log "first run (as $RUN_USER):"
systemctl start cyberware-source-update.service
sleep 1
journalctl -u cyberware-source-update.service -n 5 --no-pager 2>/dev/null | sed 's/^/    /' || true

cat <<DONE

==================== NAS source updater installed ====================
host role : the gallery's WRITER (one writer; bodies mount the same gallery READ-ONLY)
gallery   : $CW_GALLERY   (must stay mounted read-WRITE for $RUN_USER)
repo auth : $RUN_USER must have READ access to the private repo — an SSH key authorized for
            github.com:rhCat/cyberware (the gallery's remote is SSH), or switch the remote to HTTPS+token.
            The 'first run' log above shows whether the fetch actually authenticated.
timer     : cyberware-source-update.timer  (every ${INTERVAL}s, Persistent)
logs      : journalctl -u cyberware-source-update.service -f
manual run: sudo systemctl start cyberware-source-update.service
the gate  : fetch -> ff-only -> skillChip -> 'skill_index --check' -> revert-on-drift (never publishes a tampered/divergent chip)
======================================================================
DONE
