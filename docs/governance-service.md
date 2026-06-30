# govd — the governance server

`infra/govern/govd.py` is a **control/audit plane**. It governs the *claim* and records *status*. It never sees
task data and it never executes.

The agent sends a **claim** — skill, perk, and var **keys** (names only; no values, no file contents, no
secrets). govd checks the claim against its **own** trusted registry and blesses a **value-free plan**
(the tool sequence + each snippet's sha256 + a wrapper with `${VAR}` placeholders), pinning the plan's
sha256. The agent binds its own vars **locally** and runs **locally**; over a per-run WebSocket it reports
**status** only (step ran, exit, ok/fail). govd monitors the plan **hash**, not the content, and owns the
provenance ledger. Like a bank session: the ledger, not the contents of your box.

## Principles

- **No data crosses the boundary.** Only the claim (keys) and status. govd reads nothing the agent holds —
  no values, no files, no command output. The provenance ledger stores var **names** only.
- **Secrets are never plaintext.** A plaintext-secret key (`PGPASSWORD`, `*_TOKEN`, `*_SECRET`, …) is
  refused. Pass a **`*_FILE` pointer** (a path to a `chmod 600` pass file); the snippet reads it at runtime
  with `cat "$X_FILE"` (reading a file as data, never executing it). The secret lives only in that file and
  the running process — never in a config, a ledger, or the script.
- **Destructiveness is declared, not sniffed.** A perk marked `destructive:true` (e.g. `pg_ops/migrate`)
  pushes back until the claim carries `approve:["<perk>"]`. govd never inspects payload to decide this — the
  proven pathway is what's governed, not the bytes flowing through it.
- **Oversight monitors the plan sha256.** The per-step gate checks the agent's `plan_sha` against the pinned
  one. On an inconsistency it investigates by **plain text diff** (`plan_diff`) — read as strings, compared
  as strings — and **never** executes, sources, or pipes a submitted plan.
- **Private per-run sessions.** Each `allow` mints a `session_token` that gates the WS and the ledger read.
  The upstream-order gate is server-owned and can't be forged: a `step_result` is recorded only after a
  `grant` for that exact step with the blessed `plan_sha`.
- **Composition runs here, including TLC.** govern() composes the blueprint — a structural reachability
  check plus the **TLA+/TLC** deadlock model check (`composer`). The Docker image bundles a headless JRE +
  `tla2tools.jar` (`$TLA2TOOLS_JAR`), so TLC runs for real in-container (not the structural-only fallback);
  the result (`"no deadlock (TLC)"`) is returned in `/govern` and recorded in the ledger. TLC is cached per
  blueprint (they're static), so it runs once per skill. A detected deadlock rejects the claim.

## HTTP

```
GET  /health                          -> {status, mode, host, port, registry, chip_sha, chip, runs}
GET  /catalog                         -> value-free discovery: skills · perks · var-KEYS · skill_sha · verified
GET  /price?skill=…&perk=…[&model&mode] -> value-free USAGE QUOTE before a run (LLM cost + tool fee, itemized; total reconciles to a Stripe charge; ungated)
GET  /flow/run/<run_id>?token=…        -> THIS run's task-blueprint SVG (perk's gated sequence; value-free; monitor-gated)
GET  /flow/<skill>                     -> the skill's generic lifecycle blueprint.svg (value-free; ungated)
POST /govern  {skill, perk, var_keys, approve?}
       -> 200 allow      {run_id, decision, plan, plan_sha, session_token, ws}     plan = sequence+wrapper+hashes
          409 push_back  {run_id, decision, needs_approve, ...}                    destructive perk → approve
          403 reject     {run_id, decision, problems, ...}   fails a gate (see "Claim gates" below) or is structural (ambiguous_skill_id, bad key, secret key, missing input, deadlock)
GET  /ledger/<run_id>?token=…          -> the server-side provenance chain (requires the run's SESSION token — not the agent Bearer, not the monitor token)
GET  /monitor/state                   -> dashboard snapshot: runs · decisions · live feed (value-free; monitor-token gated)
GET  /monitor/stream                  -> Server-Sent-Events push of the snapshot on change (monitor-token gated)
GET  /monitor/run/<run_id>            -> one run's value-free detail for the dashboard (monitor-token gated)
GET  /trace/<run_id>                  -> the run's cross-plane trace: claim→grant→step spans (monitor-token gated)
GET  /intoto/<run_id>                 -> the run's in-toto provenance statement (monitor-token gated)

# fleet discovery plane — a SECOND listener on :8773 (default-on; see "Fleet discovery" below)
GET  :8773/fleet/health               -> the fleet plane's own liveness (ungated; for the container healthcheck)
GET  :8773/fleet/nodes                -> live fleet roster: each node's url · arch · chip_sha · skills · tier · healthy (Bearer-gated)
GET  :8773/fleet/find?skill=…[&tier=…&all=1] -> WHERE to run skill X: a healthy node's :5773 url (Bearer-gated; 404 if none)
```
(`/oversight` is a **WebSocket**, not HTTP — see the WebSocket section below.)

The `plan` is value-free **and code-free**: `{skill, perk, sequence, wrapper, snippet_shas, skill_sha}`.
`snippet_shas` is the perk's whole `src/` closure (every `.sh` porter **and** `.py` core) taken from the
skill's `index.json`; **no file bodies are shipped**. The agent runs the porters+cores from its **own
registry** (`--registry`, default = the cyberware install it's in) after verifying those files match the
blessed hashes; it injects its vars via the **process environment**. `plan_sha = sha256(skill, perk,
sequence, wrapper, snippet_shas, skill_sha)` — both sides compute it identically.

## Discovery — the catalog (`GET /catalog`)

`/catalog` is **value-free** and **ungated** (like `/health`): an agent points at the server and learns
what it governs *before* claiming anything. Per skill it returns the **perks**, each perk's var **KEYS**
(required/optional, names only), the skill's `skill_sha`, and whether govd's own copy is `verified`
against its index — no values, no run data, no file bodies.

The agent's client cross-references this against its **own** registry by `skill_sha`
(`./govd-client --discover`, or `discover()` in the client), tagging each local skill:

| status | the agent's copy … | run it governed? |
|---|---|---|
| `verified` | matches the hash govd blessed | **yes** |
| `drift` | differs from the governed copy (or its local index drifted) | no — reconcile |
| `unverified` | isn't in govd's image at all — a **new** skill | no — add it + rebuild |
| `server_drift` | exists in govd but govd's own copy fails its index | no — fix the image |

So a skill the agent just authored is **visible but not yet governable** (a claim for it rejects as
`unknown_skill_perk`) until it's added to the image and the image is rebuilt. Crucially, the server
catalog and the agent's local view are built by the **same** `skill_index.catalog()` over their
respective registries, so the two can only differ by a real hash difference — never by drift in the
catalog code itself.

## Fleet discovery — the roster (`:8773/fleet/*`)

Where `/catalog` answers *what this node governs*, the **fleet plane** on `:8773` answers *which node to
ask*. It is a **default-on core service** (`infra/govern/fleetd.py`) that runs as a second listener beside
govd's `:5773`; with no fleet configured it reports just **itself** (graceful standalone), and a fleet-plane
failure never blocks `:5773`.

- `GET /fleet/find?skill=X` returns a **healthy node's `:5773` URL** that offers skill X — you then claim,
  govern, and execute on *that* node. The fleet plane indexes govd instances; it **never** governs or executes
  (a wrong routing answer costs only a retry, never an unauthorized action — govd stays the syscall boundary).
- `GET /fleet/nodes` is the full roster: each node's `url · arch · chip_sha · skills · exec_mode ·
  exod_attached · tier · healthy · last_seen`. A dead peer stays listed as `healthy:false` (never dropped).
- `GET /fleet/health` is the plane's own liveness only (**ungated**). `/fleet/nodes` and `/fleet/find` are
  **Bearer-gated against the same principals registry** as `/govern` — the aggregate roster discloses the whole
  fleet, so it is never served to an unauthenticated caller.

Each node builds the roster by **live-probing** its peers' ungated `:5773` `/health` + `/catalog`. There is no
registration or gossip write surface, so a node can only ever report what it itself scraped — no
roster-poisoning. The peer roster is supplied like `GOVD_PRINCIPALS`, never hardcoded and never in the repo:
`FLEETD_FLEET_URL` (a remote provider) > `FLEETD_FLEET` (a mounted file) > self-only. The plane binds the same
interface as govd — map it tailnet-only with `-p <tailnet-ip>:8773:8773`.

## Authenticity — the chip manifest + the per-skill index

The skills live on the **skillChip** (the cartridge — its own repo, vendored as the `skillChip/`
submodule), located by `infra/registry.py` (`registry.SKILLCHIP`, default `<repo>/skillChip`, overridable
with `$CYBERWARE_SKILLCHIP`). The chip is **self-describing**: `skillChip/index.json` is the **chip
manifest** — every skill with its `skill_sha`, plus a roll-up `chip_sha` — which cyberware retrieves to
discover + verify the whole chip as a unit before trusting any one skill.

Within it, each skill carries `skillChip/<ns>/<skill>/index.json`: the sha256 of every file + a roll-up
`skill_sha` (`python3 -m infra.tool.skill_index --all` to generate, `--check` to verify; CI gates on it).
It is the file-level authenticity reference both sides check against:

- **govd** won't bless a registry that doesn't match its index (`registry_drift` → reject), and pins the
  perk's closure hashes (from the index) in the plan.
- **the agent** verifies its own registry's perk files against those hashes before running; a mismatch
  refuses the run. So the agent runs *exactly the skill version govd blessed* — and only hashes ever cross
  the wire, never file bodies. Deploy = the same registry+index on both ends.
- **the image build** runs `skill_index --check --all` right after copying the registry, so a drifted index
  (a stripped file, an un-regenerated hash) **fails the build** — the container can never ship a registry
  that would reject every claim at runtime.

## Claim gates — VALIDATE / ACCESS-1 / ACCESS-2

`govern()` first **canonicalizes** the skill id — a bare claim becomes its `ns:name` when exactly one
namespace owns the leaf, and is rejected `ambiguous_skill_id` when two do (never first-source-wins). It then
runs **three independent, fail-closed gates** (each an AND; none self-approvable):

| gate | question | engine | reject ids |
|---|---|---|---|
| **VALIDATE** | do the skill's files match its committed index? | `verify_skill` | `registry_drift` |
| **ACCESS-1** | may this skill be reached *here at all*? | `skillacl.access_allows` (`access.json`) | `skill_remote_closed`, `skill_principal_denied`, `skill_tier_below_floor` |
| **ACCESS-2** | may *this principal* run this skill/perk/tier? | `principals.acl_allows` | `acl_skill_denied`, `acl_perk_denied`, `acl_tier_denied`, `acl_*` |

**ACCESS-1** is the skill's *own* policy (`skillChip/<ns>/<skill>/access.json`: `{remote, principals[],
min_tier}`), independent of who claims — **local-open / remote-closed**: a govd run for the local developer
(`--mode local`) or a principal flagged `local_dev` is always open, but when govd serves **others** a skill
must opt in (`"remote": true`). An undeclared skill stays remote-open until the operator flips
`skillacl_enforce`, then the secure default holds. **ACCESS-2** is the per-actor token ACL (`ns:name`, the
`ns:*` wildcard, the `*` super-wildcard, or a legacy bare leaf). All three gates re-run on every in-flight
step (`step_reauthorize`), so a revocation or a tightened policy binds a running multi-step run.

## Budget gate — the per-actor credit shutoff (opt-in)

A fourth, **pricing-stage** gate runs last when the operator sets `budget_enforce` (default **OFF** — see
[settlement.md](settlement.md)). After the three gates pass, `govern()` prices the claim (`credit_price`) and
checks the actor's CREDIT balance via the pure `budget_ok`: `insufficient_credits` → **403** when the balance
can't cover the run (a real shutoff, not `--approve`-able), `budget_unmetered` when an authenticated actor
under enforcement carries no allowance, `budget_unavailable` when the store can't be read (fail-closed). The
pre-check is a pure snapshot; the **authoritative** debit is a single atomic transaction in `do_POST` on
`allow`, so two concurrent same-actor claims can't both pass when only one fits. A value-free `cost` is
stamped on the verdict and record. Live levers, monitor-token-gated: `POST /budget/topup` (an operator grant)
and `POST /budget/recharge` (a Stripe purchase of credits, inert until a key is wired). `GET /budget`
(+ a JSON `/budget/state`) renders a per-actor gauge (green/yellow/red by % of allowance); the fleet
dashboard's `/accounting` + `/principal/<actor>` aggregate spend across nodes.

## WebSocket  `/oversight`  (per-run session, status only)

```
client -> {"type":"hello","run_id":…,"token":…}             <- {"type":"hello_ack","authorized":true|false}
client -> {"type":"step_request","step","plan_sha"}         <- {"type":"grant"|"refuse","reason"}
client -> {"type":"step_result","step","plan_sha","status","exit"}   <- {"type":"recorded","index"}
```

`hello` authenticates with the run's `session_token` and binds the session to that run. `grant` checks the
`plan_sha` matches the pinned one and every upstream step is recorded `ok`. `step_result` carries **status
only** — never command output. A refuse for an inconsistent `plan_sha` can include a text `diff` if the
client supplies its `plan_wrapper` for investigation.

## Monitor dashboard

govd serves a real-time monitoring dashboard at **`/`** (and `/dashboard`). A **left nav lists the runs**;
selecting one opens a **review panel** for that run — its decision, `plan_sha`, TLC result, var keys, the
step sequence with states, the **event timeline** (`granted` / `step_result` / `step_refused`), and the
blessed value-free plan. The **Overview** item shows the aggregate: decision counts, **tool usage**
(ok / error / granted per tool), **recent decisions** (the `reject`/`push_back` security signal — refused
secrets, bad keys, destructive perks awaiting approval), and a **live event feed**. It polls
`GET /monitor/state` (the run list + overview) every 1.5 s and `GET /monitor/run/<run_id>` for the
selected run; both are **value-free** (names, hashes, status — never values, secrets, or output) and
monitor-token gated. Runs restored from disk (a prior session) are tagged `restored`.

## Feed-stock acquisition — local vs cloud (`CLOUD_MODE`)

The container boots through **`chipfetch`** (acquire + validate), and govd starts only if the chip passes
the same authenticity gate as the build (every skill's `index.json` + the chip manifest). Two modes:

- **local** (default) — the chip baked into the image at build (`COPY skillChip/`), re-validated at boot.
- **cloud** (`CLOUD_MODE=1`) — clone the chip **live at boot** from `CLOUD_SOURCE` (default: the
  [skillChip repo](https://github.com/rhCat/skillChip)) at **`CLOUD_SOURCE_TAG`** (a branch, tag, or
  commit sha; default `main`). A **private** source authenticates with **`CLOUD_SOURCE_TOKEN`** — the
  token is passed to git only via a `GIT_ASKPASS` helper — never written into a URL, `.git/config`, the
  command line, an error message, the provenance, or govd's own environment; a failed clone leaves nothing
  on disk, and the boot-only `CLOUD_*` vars are dropped before govd starts. The clone is fresh each boot (`CLOUD_CHIP_DIR`, default
  `~/.cyberware/skillChip-cloud`); updating the chip = restart the container at the new ref.

```sh
docker run -p 5773:5773 cyberware-govd                                  # local: the baked chip
docker run -e CLOUD_MODE=1 -e CLOUD_SOURCE_TAG=v1.2 \
           -e CLOUD_SOURCE_TOKEN=ghp_... -p 5773:5773 cyberware-govd    # cloud: live chip at tag v1.2
```

A drifted chip (any skill failing its index, or the manifest failing its `chip_sha`) **refuses to boot** —
`chipfetch: REFUSED` with the drift list. `GET /health` attests which cartridge is being governed:
`chip_sha` plus the acquisition provenance (`local`, or `cloud source @ ref (commit)`); the boot banner
prints the same.

## Persistent ledger (mount it)

The provenance ledger lives under `record_root` (one dir per run). In the Docker image that's
**`/data/govd`**, declared as a `VOLUME` — **mount it to keep run records across restarts and review them
later**:

```sh
docker run -v cyberware-govd:/data/govd -p 5773:5773 cyberware-govd      # named volume
docker run -v "$PWD/govd-ledger:/data/govd" -p 5773:5773 cyberware-govd  # host dir
```

On startup the server **hydrates** from `record_root` — the most-recent run ledgers (up to `MAX_RUNS`) are
reloaded into the dashboard for review. Set `GOVD_RECORD_ROOT` (or `record_root` in the config) to point
elsewhere. Only `allow` runs are persisted (the executed ones); refusals are session-only in the feed.

### Backends — the chain + the queryable index

The ledger is two layers: the **chained-JSONL artifact-of-record** under `record_root` (above), and a
**derived, queryable index** built over a pluggable `StoreBackend`. Two backends are interchangeable behind
the same interface — **`SqliteWalBackend`** (the default: a local WAL sqlite, zero config) and
**`PsycopgBackend`** (Postgres, for a shared/HA deployment). The Postgres tier is **inert until a DSN is
wired** (`GOVD_STORE_DSN` / `GOVD_STORE_DSN_FILE`): with no DSN the server runs entirely on the sqlite index,
and the DSN is **never echoed** to logs. `make_backend` selects the backend from config. Both must pass the
**same six-property store contract** (conformance · round-trip · idempotent replay · reconcile-exact ·
torn-tail-safe · Postgres-inert), and a continuous reconciler proves the index equals the chain — see
[architecture.md](architecture.md). The chain is the source of truth; the index is rebuilt from it.

The snapshot endpoint is gated by a **monitor token** (separate from the per-run session tokens). The
default depends on the mode, so a network-exposed dashboard is never guessable:

- **local mode** → defaults to **`admin`** (friendly for dev): just open `http://127.0.0.1:<port>/?token=admin`.
- **remote mode** → defaults to a **strong random token** (printed in the boot log; `admin` is rejected).
- Override either with **`GOVD_MONITOR_TOKEN`** (env) or `monitor_token` in the config.

The boot log prints the ready-to-open URL:

```
dashboard:  http://127.0.0.1:5773/?token=admin   (default local token 'admin' — set GOVD_MONITOR_TOKEN to change)
```

In Docker (remote mode) read the token from the container log (`docker logs <name>`) or set
`GOVD_MONITOR_TOKEN` on `docker run`.

## Run it

The repo ships two launchers (`./govd`, `./govd-client`) that resolve the package from their own location,
so they run from **any directory** — no `-m` / `cwd` dance. Add the repo to `PATH` (or symlink them into
`~/bin`) to drop the `./`.

```sh
# local (dev) — rotates through 5773 / 4773 / 3773 / 6773, first free wins
./govd --mode local                       # ≡ python3 -m infra.govern.govd --mode local

# remote (the Docker default) — one fixed port, bound 0.0.0.0
docker build -t cyberware-govd .
docker run -v cyberware-govd:/data/govd -p 5773:5773 cyberware-govd

# drive it from the agent side (claim → value-free plan → run locally under live status oversight)
./govd-client --url http://127.0.0.1:5773 --ledger task-ledger.json
./govd-client --url http://127.0.0.1:5773 --ledger task-ledger.json --fetch-only
```

The agent's task-ledger keeps the var **values** (and `*_FILE` secret pointers) — those stay on the agent
side; `fetch` sends only the var **keys** to govd.

## Operational notes

- **Run remote mode over TLS.** Even though no secret value crosses to govd, put a control plane behind TLS.
- **Bounded under concurrency.** Threaded; the in-memory run table is capped (`MAX_RUNS`, oldest evicted,
  ledger retained on disk); the WS is a per-run session that can be held open or reconnected per step.
- **DoS guards.** `/govern` bodies capped (1 MiB), WebSocket frames capped (1 MiB), a read timeout drops
  stalled connections, only `allow` runs persist. A connection/rate limit in front of govd remains a
  deployment responsibility.
- **Cooperative mode.** In local mode govd does not execute — the agent runs the plan and self-reports
  status. The plan **hash** is monitored; binding the actual run to the blessed plan beyond the hash (e.g.
  signed attestation of the run environment) is a strict-mode extension.
- **Frame shape.** govd's WebSocket speaks the simple single-frame, client-masked JSON the bundled client
  uses; it does not reassemble fragmented frames.
