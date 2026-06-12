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
GET  /health                          -> {status, mode, host, port, registry, runs}
GET  /catalog                         -> value-free discovery: skills · perks · var-KEYS · skill_sha · verified
POST /govern  {skill, perk, var_keys, approve?}
       -> 200 allow      {run_id, decision, plan, plan_sha, session_token, ws}     plan = sequence+wrapper+hashes
          409 push_back  {run_id, decision, needs_approve, ...}                    destructive perk → approve
          403 reject     {run_id, decision, problems, ...}                         (bad key / secret key / missing input)
GET  /ledger/<run_id>?token=…          -> the server-side provenance chain (requires the run's token)
```

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

## Authenticity — the chip manifest + the per-skill index

The skills live on the **skillChip** (the cartridge — its own repo, vendored as the `skillChip/`
submodule), located by `infra/registry.py` (`registry.SKILLCHIP`, default `<repo>/skillChip`, overridable
with `$CYBERWARE_SKILLCHIP`). The chip is **self-describing**: `skillChip/index.json` is the **chip
manifest** — every skill with its `skill_sha`, plus a roll-up `chip_sha` — which cyberware retrieves to
discover + verify the whole chip as a unit before trusting any one skill.

Within it, each skill carries `skillChip/<skill>/index.json`: the sha256 of every file + a roll-up
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
