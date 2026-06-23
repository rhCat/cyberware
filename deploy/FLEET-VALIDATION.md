# Fleet — live validation

The deploy scripts in this directory stand the fleet up; this records that it has been **exercised**, not
just stood up. The distinction matters: board redemptions (e.g. P2-T12) are validated locally / in CI, but
the *running* nodes executing a real governed claim end-to-end is a separate proof.

## First live confined claim (2026-06-23)

A real governed claim was driven from an agent (a Mac on the tailnet) through a **deployed DGX confined body**
(`dgx-spark`, rootless `setup-confined-body-user.sh`, `exec_mode=delegated`):

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
