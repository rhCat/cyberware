#!/usr/bin/env bash
# setup-mac-anchor.sh — stand up THIS macOS host (the dev + agent console) as a cyberware fleet ANCHOR.
#
# macOS cannot run exod/bwrap, so the Mac is a COOPERATIVE govd anchor (it blesses + records governed claims;
# execution is client-side), exactly like the Linux edge anchors — never a confined body. govd is managed by
# YOU via launchd (a per-user LaunchAgent, no root) and bound ONLY to the tailscale overlay IP, never a public
# or 0.0.0.0 interface. The source is THIS repo (the Mac already holds it — no clone). Auth is ON: a minted
# monitor token + an agent principal, so the tailnet-exposed plane is never open.
#
# Idempotent: safe to re-run (keys/tokens minted once; the LaunchAgent is reloaded).
set -euo pipefail

REPO="${REPO:-$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)}"   # this repo (the anchor runs from here)
GOVD_PORT="${GOVD_PORT:-5773}"
# the node name — derived from tailscale (or LocalHostName / hostname), never hardcoded. Override with NODE_NAME.
_TS="$(command -v tailscale 2>/dev/null || echo /Applications/Tailscale.app/Contents/MacOS/Tailscale)"
NODE_NAME="${NODE_NAME:-$("$_TS" status --json 2>/dev/null | python3 -c 'import json,sys;print(json.load(sys.stdin)["Self"]["HostName"])' 2>/dev/null || scutil --get LocalHostName 2>/dev/null || hostname -s)}"
HOME_CW="$HOME/.cyberware/mac-anchor"                              # etc + data live OUTSIDE the repo (clean)
ETC="$HOME_CW/etc"; DATA="$HOME_CW/data"
PLIST="$HOME/Library/LaunchAgents/com.cyberware.govd.plist"
LABEL="com.cyberware.govd"
LOG_DIR="$HOME_CW/log"
log() { printf '\033[36m[mac-anchor]\033[0m %s\n' "$*"; }

[[ "$GOVD_PORT" =~ ^[0-9]+$ ]] || { echo "GOVD_PORT must be numeric (got: $GOVD_PORT)"; exit 1; }
mkdir -p "$ETC" "$DATA" "$LOG_DIR"

# 0. python with the cyberware deps (cryptography). Resolve an ABSOLUTE path — launchd has a minimal env.
PY="${PY:-$(command -v python3)}"
[ -x "$PY" ] || { echo "python3 not found on PATH — set PY=/abs/path/to/python3"; exit 1; }
"$PY" -c "import cryptography" 2>/dev/null || { echo "the chosen python3 ($PY) lacks 'cryptography' — set PY to the env that has it"; exit 1; }
log "python: $PY"

# 1. the tailscale overlay IP — bind ONLY this (never 0.0.0.0 / the LAN/public interface)
TS="$(command -v tailscale || echo /Applications/Tailscale.app/Contents/MacOS/Tailscale)"
TS_IP="$("$TS" ip -4 2>/dev/null | head -1 || true)"
BIND_HOST="${TS_IP:-127.0.0.1}"
[ -n "$TS_IP" ] || log "WARN: no tailscale IP — binding 127.0.0.1 (re-run once tailscale is up; never bind 0.0.0.0)"
log "bind host: $BIND_HOST:$GOVD_PORT"

# 2. principals + monitor token — under ~, 0600, minted ONCE (random; never a value you typed)
[ -f "$ETC/monitor.token" ] || { openssl rand -hex 24 > "$ETC/monitor.token"; chmod 0600 "$ETC/monitor.token"; }
if [ ! -f "$ETC/principals.json" ]; then
  AT="$(openssl rand -hex 24)"; SHA="$(printf '%s' "$AT" | shasum -a 256 | cut -d' ' -f1)"
  printf '{"principals":{"agent-1":{"token_sha":"%s","rate":2.0,"burst":20}}}\n' "$SHA" > "$ETC/principals.json"
  chmod 0600 "$ETC/principals.json"
  echo "$AT" > "$ETC/agent-1.token.GIVE-TO-AGENT-THEN-DELETE"; chmod 0400 "$ETC/agent-1.token.GIVE-TO-AGENT-THEN-DELETE"
  log "minted principal 'agent-1' — token in $ETC/agent-1.token.GIVE-TO-AGENT-THEN-DELETE"
fi

# 3. govd config — COOPERATIVE (no exod block ⇒ never executes), bound ONLY to the tailscale IP
cat > "$ETC/govd.json" <<JSON
{
  "mode": "remote",
  "remote": {"host": "$BIND_HOST", "port": $GOVD_PORT},
  "record_root": "$DATA",
  "principals_path": "$ETC/principals.json"
}
JSON

# 4. the LaunchAgent (no root). Reads the monitor token from its file at launch; binds remote.host = the TS IP.
cat > "$PLIST" <<PLIST_EOF
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
  <key>Label</key><string>$LABEL</string>
  <key>ProgramArguments</key>
  <array>
    <string>/bin/bash</string><string>-c</string>
    <string>cd "$REPO" &amp;&amp; GOVD_MONITOR_TOKEN="\$(cat "$ETC/monitor.token")" GOVD_CONFIG="$ETC/govd.json" GOVD_RECORD_ROOT="$DATA" GOVD_PRINCIPALS="$ETC/principals.json" "$PY" -m infra.govern.govd --config "$ETC/govd.json" --mode remote --port $GOVD_PORT</string>
  </array>
  <key>WorkingDirectory</key><string>$REPO</string>
  <key>RunAtLoad</key><true/>
  <key>KeepAlive</key><true/>
  <key>StandardOutPath</key><string>$LOG_DIR/govd.out.log</string>
  <key>StandardErrorPath</key><string>$LOG_DIR/govd.err.log</string>
</dict>
</plist>
PLIST_EOF
log "wrote LaunchAgent: $PLIST"

# 5. (re)load the agent
launchctl bootout "gui/$(id -u)/$LABEL" 2>/dev/null || true
launchctl bootstrap "gui/$(id -u)" "$PLIST" 2>/dev/null || launchctl load "$PLIST"
launchctl kickstart -k "gui/$(id -u)/$LABEL" 2>/dev/null || true

# 6. health check
sleep 2
if curl -fsS -m 5 "http://$BIND_HOST:$GOVD_PORT/health" >/dev/null 2>&1; then
  log "govd healthy on $BIND_HOST:$GOVD_PORT · $(curl -fsS "http://$BIND_HOST:$GOVD_PORT/health" | grep -o '"exec_mode":"[^"]*"')"
else
  log "WARN: /health not reachable yet — check $LOG_DIR/govd.err.log"
fi

cat <<DONE

==================== Mac anchor ($NODE_NAME) ====================
role      : cooperative anchor (blesses + records; execution client-side) — macOS, no exod/bwrap
bind      : $BIND_HOST:$GOVD_PORT  (tailnet only)
config    : $ETC/govd.json
record    : $DATA
monitor   : $ETC/monitor.token  ->  copy into the fleetdash token_file:
            mkdir -p ~/.cyberware/monitors && cp $ETC/monitor.token ~/.cyberware/monitors/$NODE_NAME.token
agent tok : $ETC/agent-1.token.GIVE-TO-AGENT-THEN-DELETE  (hand to the brain, then delete)
logs      : $LOG_DIR/govd.{out,err}.log
verify    : curl http://$BIND_HOST:$GOVD_PORT/health   ->  "exec_mode":"cooperative"
stop      : launchctl bootout gui/$(id -u)/$LABEL   (and rm $PLIST to disable permanently)
DONE
