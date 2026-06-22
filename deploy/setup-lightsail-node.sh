#!/usr/bin/env bash
# setup-lightsail-node.sh — provision an AWS Lightsail node to close cyberware v1.1's remaining
# infra-gated tasks. Each capability flag maps to the task(s) it unblocks:
#
#   --gvisor    gVisor/runsc sandbox runtime          -> P2-T04 (community-tier SandboxProfile) -> P3-T11
#   --postgres  local PostgreSQL                       -> P5-T01 (sqlite-WAL -> Postgres adapter) -> P5-T04
#   --stripe    Stripe client + secret slot            -> P6-T14 (Stripe SettlementAdapter)        -> P6-T15
#   --llm       LLM-key secret slot                    -> P6-T09 (llm/* intelligence perk; also needs alchemy)
#   --base      service user + secret store + govd unit (always sensible; implied by any flag)
#   --firewall  host ufw (SSH-first, OPT-IN)           -> defence-in-depth; the AWS-side firewall is YOURS
#   --all       base + gvisor + postgres + stripe + llm
#
# Usage (on the node, as a sudo-capable user):
#     curl -fsSLO <raw-url>/deploy/setup-lightsail-node.sh   # or: it's in the cloned repo
#     sudo bash setup-lightsail-node.sh --gvisor --postgres   # pick the capabilities you want
#
# WHAT THIS SCRIPT DOES NOT DO (your hand, not mine):
#   * It never touches AWS. The Lightsail firewall / "only my PC may SSH" rule is set in the AWS console
#     (or `aws lightsail put-instance-public-ports`) by you — this script only optionally hardens the HOST.
#   * It never contains or prints a secret. It creates the secret STORE; you add the actual Stripe test key
#     and LLM key yourself (instructions printed at the end). Secrets stay sops/age-encrypted at rest.
#   * It does not run cyberware AS ROOT. Provisioning needs root (apt); the govd/exod runtime runs under a
#     non-root service identity — the executor refuses uid 0 (CYBERWARE_ALLOW_ROOT is an operator escape only).
#
# Idempotent: safe to re-run. Tested target: Ubuntu 22.04/24.04 (Lightsail default).
set -uo pipefail

CW_USER="cyberware"
CW_HOME="/opt/cyberware"
CW_ETC="/etc/cyberware"
GOVD_IMAGE="${GOVD_IMAGE:-ghcr.io/rhcat/cyberware:latest}"
GOVD_PORT="${GOVD_PORT:-5773}"
DO_BASE=0 DO_GVISOR=0 DO_POSTGRES=0 DO_STRIPE=0 DO_LLM=0 DO_FW=0
for a in "$@"; do case "$a" in
  --base) DO_BASE=1 ;;  --gvisor) DO_GVISOR=1 ;;  --postgres) DO_POSTGRES=1 ;;
  --stripe) DO_STRIPE=1 ;;  --llm) DO_LLM=1 ;;  --firewall) DO_FW=1 ;;
  --all) DO_BASE=1 DO_GVISOR=1 DO_POSTGRES=1 DO_STRIPE=1 DO_LLM=1 ;;
  *) echo "unknown flag: $a"; exit 2 ;;
esac; done
[ $(( DO_GVISOR+DO_POSTGRES+DO_STRIPE+DO_LLM+DO_FW )) -gt 0 ] && DO_BASE=1
[ "$DO_BASE" = 0 ] && { echo "nothing selected — pass at least one of --base/--gvisor/--postgres/--stripe/--llm/--firewall/--all"; exit 2; }
[ "$(id -u)" = 0 ] || { echo "run with sudo (provisioning needs root; the runtime then drops to '$CW_USER')"; exit 1; }
log(){ echo "[setup] $*"; }

require_docker(){
  command -v docker >/dev/null || { echo "Docker is required (this node already runs the CI runner, so it should be present). Install Docker Engine first."; exit 1; }
}

do_base(){
  log "base: apt deps, service user, secret store, govd unit"
  export DEBIAN_FRONTEND=noninteractive
  apt-get update -qq
  # bubblewrap = the kernel sandbox boundary the exec/limb runs steps inside (nobody, empty caps);
  # age+sops = the secret store; jq/curl = plumbing; python3 = the agent (cortex) runtime + the chip.
  apt-get install -y --no-install-recommends bubblewrap uidmap age jq curl ca-certificates python3 python3-venv >/dev/null
  command -v sops >/dev/null || { log "installing sops"; curl -fsSL -o /usr/local/bin/sops \
      https://github.com/getsops/sops/releases/latest/download/sops-v3.9.0.linux.amd64 && chmod +x /usr/local/bin/sops; }
  id "$CW_USER" >/dev/null 2>&1 || useradd -r -m -d "$CW_HOME" -s /usr/sbin/nologin "$CW_USER"
  install -d -m 0750 -o "$CW_USER" -g "$CW_USER" "$CW_ETC" "$CW_ETC/secrets"
  # secret store key (age). The PRIVATE key never leaves the node; you encrypt secrets TO its public key.
  if [ ! -f "$CW_ETC/age.key" ]; then
    sudo -u "$CW_USER" age-keygen -o "$CW_ETC/age.key" 2>"$CW_ETC/age.pub.txt"; chmod 0400 "$CW_ETC/age.key"
    grep -o 'age1[0-9a-z]*' "$CW_ETC/age.pub.txt" | head -1 > "$CW_ETC/age.pub"
    log "age recipient: $(cat "$CW_ETC/age.pub")"
  fi
  # monitor token + principals registry (P1-T08). A token authenticates a principal at /govern; only its
  # sha256 is stored server-side. We MINT a token here and register its sha; hand the raw token to the agent.
  if [ ! -f "$CW_ETC/monitor.token" ]; then
    umask 077; openssl rand -hex 24 > "$CW_ETC/monitor.token"; chown "$CW_USER:$CW_USER" "$CW_ETC/monitor.token"
  fi
  if [ ! -f "$CW_ETC/principals.json" ]; then
    AGENT_TOKEN="$(openssl rand -hex 24)"; SHA="$(printf %s "$AGENT_TOKEN" | sha256sum | cut -d' ' -f1)"
    printf '{"principals":{"agent-1":{"token_sha":"%s","rate":2.0,"burst":20}}}\n' "$SHA" > "$CW_ETC/principals.json"
    chown "$CW_USER:$CW_USER" "$CW_ETC/principals.json"
    echo "$AGENT_TOKEN" > "$CW_ETC/agent-1.token.GIVE-TO-AGENT-THEN-DELETE"; chmod 0400 "$CW_ETC/agent-1.token.GIVE-TO-AGENT-THEN-DELETE"
    log "minted agent principal 'agent-1' — raw token in $CW_ETC/agent-1.token.GIVE-TO-AGENT-THEN-DELETE (hand to the VPS agent, then delete)"
  fi
  require_docker
  docker pull "$GOVD_IMAGE" >/dev/null 2>&1 || log "WARN: could not pull $GOVD_IMAGE (private? run: docker login ghcr.io)"
  # systemd unit: govd in REMOTE mode (binds 0.0.0.0 in-container; published only on loopback — put a TLS
  # edge in front for remote). Non-root in-image (uid 1000). Token + principals mounted read-only.
  cat > /etc/systemd/system/cyberware-govd.service <<UNIT
[Unit]
Description=cyberware govd (governance/audit plane; never executes)
After=docker.service
Requires=docker.service
[Service]
Restart=always
ExecStartPre=-/usr/bin/docker rm -f cyberware-govd
ExecStart=/usr/bin/docker run --rm --name cyberware-govd \\
  -p 127.0.0.1:${GOVD_PORT}:5773 \\
  -v cyberware-govd:/data/govd \\
  -v ${CW_ETC}/principals.json:/run/principals.json:ro \\
  -v ${CW_ETC}/monitor.token:/run/monitor.token:ro \\
  -e GOVD_PRINCIPALS=/run/principals.json \\
  -e PYTHONDONTWRITEBYTECODE=1 \\
  --read-only --tmpfs /tmp \\
  ${GOVD_IMAGE} \\
  sh -c 'GOVD_MONITOR_TOKEN="\$(cat /run/monitor.token)" python3 -m infra.govern.govd --mode remote --port 5773'
ExecStop=/usr/bin/docker stop cyberware-govd
[Install]
WantedBy=multi-user.target
UNIT
  systemctl daemon-reload
  systemctl enable --now cyberware-govd >/dev/null 2>&1 || true
  sleep 3
  curl -fsS -m 5 "http://127.0.0.1:${GOVD_PORT}/health" >/dev/null 2>&1 \
    && log "govd healthy on 127.0.0.1:${GOVD_PORT}" || log "WARN: govd /health not ready yet — check: journalctl -u cyberware-govd"
}

do_gvisor(){  # P2-T04: community-tier sandbox. Lightsail has NO /dev/kvm, so runsc uses the systrap/ptrace
              # platform (works without nested virt); Firecracker microVMs are N/A here (KVM-only).
  require_docker
  log "gvisor (runsc) for P2-T04 — ptrace platform (no /dev/kvm on Lightsail)"
  if ! command -v runsc >/dev/null; then
    ( set -e; cd /tmp
      ARCH=$(uname -m); URL="https://storage.googleapis.com/gvisor/releases/release/latest/${ARCH}"
      for f in runsc containerd-shim-runsc-v1; do curl -fsSL -o "$f" "${URL}/${f}"; curl -fsSL -o "$f.sha512" "${URL}/${f}.sha512"
        sha512sum -c "$f.sha512"; chmod +x "$f"; mv "$f" /usr/local/bin/; done )
  fi
  runsc --platform=systrap install >/dev/null 2>&1 || runsc install >/dev/null 2>&1 || true
  # merge the runsc runtime into daemon.json (don't clobber) + tell runsc to use systrap (no KVM)
  python3 - <<'PY'
import json, os
p="/etc/docker/daemon.json"; d=json.load(open(p)) if os.path.exists(p) and os.path.getsize(p) else {}
d.setdefault("runtimes",{})["runsc"]={"path":"/usr/local/bin/runsc","runtimeArgs":["--platform=systrap"]}
json.dump(d, open(p,"w"), indent=2)
PY
  systemctl restart docker
  docker run --rm --runtime=runsc hello-world >/dev/null 2>&1 \
    && log "runsc OK (docker run --runtime=runsc ...)" || log "WARN: runsc smoke failed — check /etc/docker/daemon.json + journalctl -u docker"
}

do_postgres(){  # P5-T01: the store interface's Postgres adapter needs a live Postgres to test against.
  log "postgres for P5-T01"
  export DEBIAN_FRONTEND=noninteractive
  apt-get install -y --no-install-recommends postgresql postgresql-client >/dev/null
  systemctl enable --now postgresql >/dev/null 2>&1 || true
  sudo -u postgres psql -tc "SELECT 1 FROM pg_roles WHERE rolname='cyberware'" | grep -q 1 \
    || sudo -u postgres psql -c "CREATE ROLE cyberware LOGIN PASSWORD 'CHANGE_ME_set_a_real_password'" >/dev/null
  sudo -u postgres psql -tc "SELECT 1 FROM pg_database WHERE datname='cyberware'" | grep -q 1 \
    || sudo -u postgres createdb -O cyberware cyberware
  log "postgres: db 'cyberware' role 'cyberware' (LOCAL socket). Set a real password + put PGPASSWORD in the"
  log "  secret store (NOT plaintext) — the adapter reads it via a *_FILE pointer / SopsAgeVault."
}

do_stripe(){  # P6-T14: Stripe SettlementAdapter. The lib goes in the agent's test venv; the TEST-MODE key is
              # a secret YOU add (a settle-RAIL, never a skill). Never a live key.
  log "stripe client for P6-T14 (TEST MODE only)"
  python3 -m venv "$CW_HOME/venv" 2>/dev/null || true
  "$CW_HOME/venv/bin/pip" install --quiet --upgrade stripe >/dev/null 2>&1 || log "WARN: pip stripe failed (network?)"
  chown -R "$CW_USER:$CW_USER" "$CW_HOME/venv" 2>/dev/null || true
  log "add your Stripe TEST key (sk_test_...) to the secret store — see the closing instructions. Never prod."
}

do_llm(){  # P6-T09: the llm/* intelligence perk needs a live LLM API key (a secret) AND the alchemy
           # extraction engine (putrefactio) — that engine is cyberware-internal, not an apt package.
  log "llm secret slot for P6-T09"
  log "  1) add your LLM API key to the secret store (closing instructions)."
  log "  2) the alchemy validator needs the putrefactio/alembic extraction engine reachable — provision it"
  log "     per the alchemy skill's requirements (it skips in CI when absent); not an OS package."
}

do_firewall(){  # OPT-IN, SSH-FIRST. The AWS Lightsail firewall is the real boundary (yours); this is host
                # defence-in-depth. We ALLOW SSH before enabling, so you are not locked out.
  log "host ufw (SSH-first). The AWS Lightsail firewall remains YOUR responsibility."
  apt-get install -y --no-install-recommends ufw >/dev/null
  ufw allow OpenSSH >/dev/null 2>&1 || ufw allow 22/tcp >/dev/null 2>&1
  ufw --force enable >/dev/null
  log "ufw enabled with SSH allowed. govd stays on loopback (TLS edge handles remote). Add ports as needed."
}

[ "$DO_BASE" = 1 ] && do_base
[ "$DO_GVISOR" = 1 ] && do_gvisor
[ "$DO_POSTGRES" = 1 ] && do_postgres
[ "$DO_STRIPE" = 1 ] && do_stripe
[ "$DO_LLM" = 1 ] && do_llm
[ "$DO_FW" = 1 ] && do_firewall

cat <<DONE

==================== setup complete — YOUR remaining steps (not automatable here) ====================
1. AWS firewall: in the Lightsail console (or aws lightsail put-instance-public-ports), restrict SSH (22)
   to YOUR PC's IP only. Do NOT expose govd's port publicly — front it with a TLS edge if remote.
2. Secrets (never plaintext — encrypt to this node's age recipient $(cat $CW_ETC/age.pub 2>/dev/null)):
     echo -n 'sk_test_...'  | age -r "\$(cat $CW_ETC/age.pub)" -o $CW_ETC/secrets/stripe_test_key.age   # P6-T14
     echo -n '<LLM_API_KEY>'| age -r "\$(cat $CW_ETC/age.pub)" -o $CW_ETC/secrets/llm_api_key.age        # P6-T09
     echo -n '<PGPASSWORD>' | age -r "\$(cat $CW_ETC/age.pub)" -o $CW_ETC/secrets/pgpassword.age          # P5-T01
   The kernel resolves these via SopsAgeVault / a *_FILE pointer; the agent only ever names a credential.
3. Agent (cortex): give the VPS agent ONLY (a) the govd endpoint, (b) the principal token in
   $CW_ETC/agent-1.token.GIVE-TO-AGENT-THEN-DELETE, (c) the chip. It claims to govd; actions are governed.
   Then delete that token file. The agent never gets SSH or a credentialed shell — that IS the architecture.
4. TLS edge (remote govd): put Caddy/a tunnel in front of 127.0.0.1:${GOVD_PORT} with the monitor token;
   never expose the raw port.
5. Close the tasks: drive each ready validator THROUGH this node's govd and redeem onto the done-ledger
   (P2-T04 via --gvisor, P5-T01 via --postgres, P6-T14 via --stripe, P6-T09 via --llm + alchemy engine).
======================================================================================================
DONE
