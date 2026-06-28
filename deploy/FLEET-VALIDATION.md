# Fleet — live validation

The deploy scripts in this directory stand the fleet up; this records that it has been **exercised**, not
just stood up. The distinction matters: board redemptions (e.g. P2-T12) are validated locally / in CI, but
the *running* nodes executing a real governed claim end-to-end is a separate proof.

## First live confined claim (2026-06-23)

A real governed claim was driven from an agent (a Mac on the tailnet) through a **deployed DGX confined body**
(rootless `setup-confined-body-user.sh`, `exec_mode=delegated`):

```
claim: fs/find_large  SEARCH_DIR=/usr  MIN_SIZE=10M     (read-only; the limb has no network)
driver: python3 -m infra.govern.govd_client --url http://<body>:5773 \
          --ledger task.json --token-file <agent-1 token>     # GOVD_TOKEN_FILE — raw token never in argv

result (run_id 2f9d94ab75c4431a, body's authoritative ledger):
  principal   = agent-1                      # the agent authenticated with its principal Bearer token
  decision    = allow                        # govd blessed the claim
  var_keys    = [MIN_SIZE, SEARCH_DIR]        # only KEYS crossed to govd — values stayed agent-side / went to the limb
  snippet_shas= {fs_find_large.sh}           # the closure exod re-derives + pins at time-of-use
  event       = step_result
                authority = exod              # the CONFINED LIMB executed it (bwrap, uid 65534, no net)
                keyid     = ed25519:38b41994  # signed with exod's identity key — the only status the ledger trusts
  /health runs: 0 -> 1
```

### What this proves on real hardware
- **The fleet executes** — agent → govd (bless + oversee) → exod (bwrap-confined) → signed result → recorded. P2-T12 live, not just CI.
- **Principal auth holds** — the body returns `401` to an unauthenticated `/govern`; the agent authenticated with the `agent-1` Bearer token (supplied via `GOVD_TOKEN_FILE`). This required the agent-side fix in `govd_client` (it previously sent no auth header — the missing client half of P1-T08).
- **The boundary invariants hold** — value-free claim (KEYS only), closure-pinned snippet, and an **exod-signed** authoritative result (`authority:"exod"`), all on the live node.

### To reproduce
```
GOVD_TOKEN_FILE=<path-to-agent-token> \
  python3 -m infra.govern.govd_client --url http://<body-tailscale-ip>:5773 --ledger <task-ledger.json>
# then read the body's ledger:  GET /ledger/<run_id>?token=<session_token>
```
Discovery is ungated (`--discover` needs no token); only `/govern` requires the principal token.

## Confined-execution overhead (2026-06-24)

`cws-bench/bwrap-overhead` on the confined body — N=30 benign steps through exod into the bwrap SandboxProfile,
timed from exod's **attested `meter.wall_ms`** (not the agent's stopwatch). Budget: p95 ≤ 100 ms.

```
{ "backend": "bwrap", "n": 30, "p50": 15.068, "p95": 17.62, "max": 71.472, "budget_ms": 100, "within": true }
```

The confinement boundary on the deployed body costs ~15 ms median / ~18 ms p95 per step — **within budget**
(the lone 71 ms max is still under). Higher than the ~4 ms bare-metal reference because the source is on the
NAS SMB mount (import/exec I/O), but comfortably inside the budget. Run it on a body:
`cd <gallery>/cyberware && python3 -m infra.tool.skilltest --skill cws-bench --perk bwrap-overhead`.

## Standing up a fleet

`deploy/fleet-setup.sh` is the generic entry point — no node identity is baked in (names + overlay IPs are
derived from the host + tailscale at run time). On each host:

```
deploy/fleet-setup.sh body          # confined body  — govd (delegated) + exod   (Linux, rootless)
deploy/fleet-setup.sh anchor        # cooperative anchor — govd blesses + records (Linux, rootless)
deploy/fleet-setup.sh mac-anchor    # cooperative anchor on macOS (launchd)
deploy/fleet-setup.sh nas-updater   # NAS source-updater (systemd timer)
deploy/fleet-setup.sh register      # append THIS host's row to ~/.cyberware/fleet.json (derives name + IP)
deploy/fleet-setup.sh dash          # launch the fleet monitor over ~/.cyberware/fleet.json
```

It dispatches to the per-role `setup-*.sh`. Your real fleet lives in **`~/.cyberware/fleet.json`** (yours,
never committed); `deploy/fleet.example.json` is only a TEMPLATE (placeholder names + `100.64.0.x` overlay
IPs) — never put real node IPs/names in the repo.

## Fleet monitor

`infra/tool/fleetdash.py` wraps every node's `/monitor` into one who-fired-what-**where** dashboard (per-node
health + a merged decision feed, `exec=exod` on the confined bodies). `deploy/fleet-setup.sh dash` (or
`python3 -m infra.tool.fleetdash --config ~/.cyberware/fleet.json --serve 8787`); tokens come from per-node
`token_file`s, never argv.

## SandboxProfile community tier — gVisor (P2-T04)

The execution boundary has a **second backend behind the same value-free `SandboxProfile` driver**
(`infra/exec/sandbox.py`): bwrap (the default/spine) and **gVisor (`runsc`)** for the community tier. The
gVisor renderer (`oci_config`) maps the SAME profile to an OCI runtime spec; `sandbox.confinement(profile,
backend)` proves the two are **seam-equivalent** — identical capability binds, network isolation, nobody
uid/gid, all caps dropped, no-new-privileges, masked `/proc`, readonly rootfs — so the community backend can
never *weaken* the boundary. The community tier is also the **no-secrets floor**: a community capability
manifest that requests a credential is refused at both the schema and the runtime (`capmanifest`).

Per the task's allowed "**one green backend + a documented stub**":
- **bwrap is the green backend** — the full kernel red-team corpus (`cws-redteam`) is green under it (SV-3/M3,
  already closed). Run it on any Linux+bwrap node: `python3 -m infra.tool.skilltest --skill cws-redteam`.
- **gVisor is the seam + a host-gated stub.** The rendering + the no-secrets tier are proven on **any** host
  (pure functions — `cws-redteam/rt-gvisor-tier`, redeemed for P2-T04). The **live attack corpus under
  `runsc`** is gated on a gVisor host (`sandbox.runsc_available()`), exactly as bwrap is gated on
  `is_available()`. To run it where `runsc` is installed:
  ```
  # on a gVisor node (runsc on PATH):
  python3 -c "from infra.exec import sandbox, redteam; print(sandbox.runsc_available())"   # -> True
  # the sandbox-family attacks exec through the runsc backend; rt-gvisor-tier reports runsc_live=true
  ```
  `rt-gvisor-tier`'s `redteam.json` records `bwrap_live` / `runsc_live` honestly, so a host without a backend
  is visible as a skip — never a fabricated pass.

## One image = a full body (govd + exod), non-root, runsc-ready

`Dockerfile.body` is a single **non-root** image that runs **govd (delegated) + exod (the confined limb)** —
so any Linux node becomes a full body with one `docker pull`, governing AND executing governed acts. It's the
sibling of `./Dockerfile` (govd-only) plus bwrap + exod + `deploy/body-entrypoint.sh`. Built + signed by
`.github/workflows/body-image.yml` (on a `vN.N.N` tag) → `ghcr.io/rhCat/cyberware-body`.

**Run it under gVisor (recommended)** — the Sentry is the isolation, so NO `--privileged` and NO dependency on
the host's unprivileged-userns sysctl (this sidesteps the Ubuntu hardening that breaks bwrap):
```
docker run -d --name cyberware-body --runtime=runsc \
  -p <tailnet-ip>:5773:5773 -p <tailnet-ip>:8773:8773 -v cyberware-body:/data/body \
  -e CLOUD_MODE=1 \                       # chip-at-boot: clone + validate the live chip (drift-refused)
  ghcr.io/rhCat/cyberware-body:latest
```
**Or under runc with bwrap** (bwrap needs the userns caps the runtime masks): add `--privileged` (or the
least-privilege `--cap-add SYS_ADMIN --cap-add SYS_CHROOT --security-opt seccomp=unconfined`). Either way the
step itself always runs as `nobody`.

> **Bind the overlay IP, never the host's `0.0.0.0`.** govd (`:5773`) and the fleet-discovery plane (`:8773`)
> inside the container both bind `0.0.0.0`, so the `-p` mapping is what scopes them — always
> `-p <tailnet-ip>:5773:5773 -p <tailnet-ip>:8773:8773`. A bare `-p 5773:5773` (or `8773:8773`) publishes the
> plane on EVERY host interface (LAN/public). Auth is on (both refuse without a token; `:8773/fleet/*` is
> Bearer-gated against the same principals registry — only its own `/fleet/health` liveness is open), but the
> overlay-only binding is the first fence — keep it.

The entrypoint mints, ONCE, into the `/data/body` volume: the grant + exod keypairs (dual-control), a monitor
token, and an `agent-1` principal. Wire them:
```
docker exec cyberware-body cat /data/body/etc/agent-1.token.GIVE-TO-AGENT   # hand to the brain
docker exec cyberware-body cat /data/body/etc/monitor.token                  # -> ~/.cyberware/monitors/<name>.token
deploy/fleet-setup.sh register <name> body http://<tailnet-ip>:5773          # add the row to ~/.cyberware/fleet.json
```
**Update:** `docker pull ghcr.io/rhCat/cyberware-body:latest && docker restart cyberware-body` refreshes the
infra; the chip is re-fetched + re-validated at boot (CLOUD_MODE), so chip updates stay nimble — no rebuild.
