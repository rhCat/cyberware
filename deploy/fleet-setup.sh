#!/usr/bin/env bash
# deploy/fleet-setup.sh — stand up THIS host as a cyberware fleet node, then register it in a fleetdash config.
#
# Generic + reusable: NO node identity is baked in — the node's name and overlay IP are DERIVED from the host
# and tailscale at run time. Your real fleet lives in ~/.cyberware/fleet.json (never committed);
# deploy/fleet.example.json is only a TEMPLATE.
#
# Usage:
#   deploy/fleet-setup.sh <role> [-- role-script-args...]
#       body         confined body — govd (delegated) + exod, Linux rootless     -> setup-confined-body-user.sh
#       anchor       cooperative anchor — govd blesses + records, Linux rootless  -> setup-edge-anchor-user.sh
#       mac-anchor   cooperative anchor on macOS (launchd)                         -> setup-mac-anchor.sh
#       nas-updater  NAS source-updater (systemd timer)                            -> setup-nas-updater.sh
#       lightsail    base node provisioning (cloud / Lightsail)                    -> setup-lightsail-node.sh
#
#   deploy/fleet-setup.sh register [NAME] [ROLE] [FLEET_JSON]
#       append THIS host's row to a fleetdash config (default ~/.cyberware/fleet.json). NAME defaults to the
#       tailscale machine name (or hostname); ROLE defaults to 'anchor'; the overlay IP + port (5773) are derived.
#
#   deploy/fleet-setup.sh dash [FLEET_JSON] [PORT]
#       launch the fleet monitor over a config (default ~/.cyberware/fleet.json on :8787).
set -euo pipefail
HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
GOVD_PORT="${GOVD_PORT:-5773}"
FLEET_DEFAULT="$HOME/.cyberware/fleet.json"

_ts() { command -v tailscale 2>/dev/null || echo /Applications/Tailscale.app/Contents/MacOS/Tailscale; }
_overlay_ip() { "$(_ts)" ip -4 2>/dev/null | head -1; }
_node_name() {
  local n
  n="$("$(_ts)" status --json 2>/dev/null \
       | python3 -c 'import json,sys;print(json.load(sys.stdin)["Self"]["HostName"])' 2>/dev/null || true)"
  [ -n "$n" ] && { echo "$n"; return; }
  command -v scutil >/dev/null 2>&1 && { scutil --get LocalHostName 2>/dev/null && return; }
  hostname -s
}

cmd="${1:-}"; shift || true
case "$cmd" in
  body)        exec bash "$HERE/setup-confined-body-user.sh" "$@" ;;
  anchor)      exec bash "$HERE/setup-edge-anchor-user.sh" "$@" ;;
  mac-anchor)  exec bash "$HERE/setup-mac-anchor.sh" "$@" ;;
  nas-updater) exec bash "$HERE/setup-nas-updater.sh" "$@" ;;
  lightsail)   exec bash "$HERE/setup-lightsail-node.sh" "$@" ;;
  register)
    name="${1:-$(_node_name)}"; role="${2:-anchor}"; fleet="${3:-$FLEET_DEFAULT}"
    ip="$(_overlay_ip)"; [ -n "$ip" ] || { echo "no tailscale overlay IP — is tailscale up?"; exit 1; }
    url="http://$ip:$GOVD_PORT"
    python3 - "$fleet" "$name" "$role" "$url" <<'PY'
import json, os, sys
fleet, name, role, url = sys.argv[1:5]
fleet = os.path.expanduser(fleet)
d = json.load(open(fleet)) if os.path.isfile(fleet) else {"nodes": []}
d.setdefault("nodes", [])
d["nodes"] = [n for n in d["nodes"] if n.get("name") != name]            # idempotent replace
d["nodes"].append({"name": name, "role": role, "url": url,
                   "token_file": f"~/.cyberware/monitors/{name}.token"})
os.makedirs(os.path.dirname(fleet), exist_ok=True)
json.dump(d, open(fleet, "w"), indent=2)
print(f"registered {name} ({role}) {url}  ->  {fleet}")
print(f"  drop this node's monitor token into: ~/.cyberware/monitors/{name}.token")
PY
    ;;
  dash)
    fleet="${1:-$FLEET_DEFAULT}"; port="${2:-8787}"
    cd "$HERE/.." && exec python3 -m infra.tool.fleetdash --config "$fleet" --serve "$port" ;;
  *)
    sed -n '2,33p' "$HERE/$(basename "${BASH_SOURCE[0]}")"
    exit 1 ;;
esac
