# Fleet — live validation

The deploy scripts in this directory stand the fleet up; this records that it has been **exercised**, not
just stood up. The distinction matters: board redemptions (e.g. P2-T12) are validated locally / in CI, but
the *running* nodes executing a real governed claim end-to-end is a separate proof.

## First live confined claim (2026-06-23)

A real governed claim was driven from an agent (a Mac on the tailnet) through a **deployed DGX confined body**
(`body-1`, rootless `setup-confined-body-user.sh`, `exec_mode=delegated`):

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

`cws-bench/bwrap-overhead` on `body-1` — N=30 benign steps through exod into the bwrap SandboxProfile,
timed from exod's **attested `meter.wall_ms`** (not the agent's stopwatch). Budget: p95 ≤ 100 ms.

```
{ "backend": "bwrap", "n": 30, "p50": 15.068, "p95": 17.62, "max": 71.472, "budget_ms": 100, "within": true }
```

The confinement boundary on the deployed body costs ~15 ms median / ~18 ms p95 per step — **within budget**
(the lone 71 ms max is still under). Higher than the ~4 ms bare-metal reference because the source is on the
NAS SMB mount (import/exec I/O), but comfortably inside the budget. Run it on a body:
`cd <gallery>/cyberware && python3 -m infra.tool.skilltest --skill cws-bench --perk bwrap-overhead`.

## Fleet monitor

`infra/tool/fleetdash.py` wraps every node's `/monitor` into one who-fired-what-**where** dashboard (per-node
health + a merged decision feed, `exec=exod` on the confined bodies). `python3 -m infra.tool.fleetdash
--config deploy/fleet.example.json --serve 8787`; tokens come from per-node `token_file`s, never argv.
