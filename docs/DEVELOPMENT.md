# cyberware — Development

> The authoritative dev-process summary for the cyberware repo. It replaces the archived
> `workzone/` swarm scaffolding. The machine-checkable record of what was built — the
> **91/91 done-ledger** (`docs/done-ledger-v2.json`) and the refreshed **pm-report**
> (`docs/pm-report.md`) — lives alongside this file; the full build history is archived
> privately (see [§ Provenance](#provenance)).

## What cyberware is

cyberware is a **governance kernel for AI agents**: an operating-system kernel where userspace may
*know* but every *action* is a governed syscall. Three privilege-separated roles, never collapsed
into one — the **LLM is the cortex** (information-only; it proposes plans and reads state but holds
no execution authority, no secret, no money); **govd is the kernel / governor** that authorizes the
claim against signed grants, enforces principal auth and rate limits, and *records* run status but
**never executes**; and **exod is the confined limb** — the only component that touches the work,
running sandboxed under uid 65534 (nobody), resolving only grant-authorized secrets, and signing the
attested result with Ed25519 so govd can verify what actually ran without having run it. An action is
a **governed syscall**: cortex proposes → govd authorizes → exod executes confined → exod signs →
govd records & settles. The thing that decides is never the thing that runs — that separation is the
load-bearing invariant of the whole system.

---

## v1.1 — Delivered (91/91)

v1.1 reframed cyberware as the *kernel for agents* and proved it rung by rung. Progress was
**redeemed, not asserted**: each task closed only when its validator skill emitted a signed `pass`
into a tamper-evident hash chain. The board closed at **91/91 tasks**, with the system having
paid for its own completion through its own settlement substrate. All **eight milestones (M0–M7)** and all
**six SV cones (SV-1…SV-6)** are closed; the live board reports `redeemed 91 · blocked 0 · failed 0`,
`done_ledger_chain: ok`.

### The milestone / SV-cone ladder

The ladder runs **SV-1 → SV-6** (six named security cones). SV-0 is the pre-existing baseline (CI
logs, in-skill self-tests), not a milestone. Each cone proves one security property and maps to a
**validator skill** that re-verifies it on demand. M0, M1, M2, M3, M4, M6 are **spine** (load-bearing
toward settlement); **M5 is compounding**, off the critical path. **M7 (Agent-mode)** was added when
the plan was reframed to the kernel-for-agents thesis, and closes on the same spine.

| Milestone | Cone | Path | Security property proven | Gate task(s) | Validator(s) |
|---|---|---|---|---|---|
| **M0** — the spine stands | (SV-0 baseline) | spine | Governed execution end-to-end, internal: claim → grant → exod step → chained ledger record (no value, no market) | `P6-T05` | — |
| **M1** | **SV-1** | spine | The protocol is real and portable — every hash canonical, reproduced byte-for-byte by an independent Go impl; the chip re-pins its own identity under JCS | `P0-T18` | `cws-conform` |
| **M2** | **SV-2** | spine | Evidence is tamper-evident — every record chained, signed, independently re-verifiable; a one-byte flip is caught and named | `P1-T09`, `P1-T10` | `cws-ledgercheck` (+`cws-mutate`) |
| **M3** ◀ **MVP** | **SV-3** | spine | Execution is a kernel-enforced boundary — agents run only attested, sandboxed, hash-pinned pathways; privilege enforced by the OS, not software trust; meters attested | `P2-T08`, `P2-T09` | `cws-redteam` + `cws-bench` |
| **M4** | **SV-4** | spine | Registry **and engine** publish and revoke themselves — signed, publicly logged, revocable network-wide in minutes; approval cryptographically human; code agrees with its declared blueprint (concordance) | `P3-T09`, `P3-T15` | `cws-release` + `alchemy` |
| **M5** | **SV-5** | compounding | Workflows **and the money's lifecycle** are model-checked free of deadlock and conservation violation *before* they run, across three independent checkers (EMPIRICAL / SYMBOLIC / AXIOMATIC) | `P4-T09` | `cws-modelcheck` |
| **M6** | **SV-6** | spine | The work pays for the work — validated work settles, intelligence priced per contract, value never minted only earned; the system paid for its own completion (the ladder closes) | `P6-T21` | `cws-settle-sim` |
| **M7** — Agent-mode | — | spine | The kernel runs the agent's *intent* — cognition holds no limb; agent posts intent, govd delegates, exod executes server-side and signs | `P2-T12` | `cws-redteam` |

(`cws-chaos` spans the V-CHAOS thread across P2/P5/P6, validating that isolation and settlement
survive injected fault conditions. `harden-pyenv` locks down the Python runtime that hosts govd.)

### Phase breakdown (P0–P6)

The plan was a **91-task DAG** (grown from 90 when agent-mode / `P2-T12` was added) organized into
seven phases. The `done-ledger-v2` chain records **81 redemptions** (seq 2→82) atop a genesis that
supersedes the v1 `done-ledger` (10 entries) — **81 + 10 = 91** redeemed tasks. All 81 v2 entries
carry `verdict: pass`.

| Phase | Redeemed (v2) | Theme | What it delivered |
|---|---|---|---|
| **P0** governance spine | 8 | the kernel exists | Canonical protocol, schema conformance, hardened runtime, govd config drift-free. |
| **P1** ledger | 10 | evidence is tamper-evident | Signed, chained, mutation-tested Ledger-v2; govd Bearer-principal auth + token-bucket (`P1-T08`) — *who* is calling the syscall boundary. |
| **P2** exec / isolation | 12 | execution is confined | bwrap / gVisor-class sandbox red-teamed; double-blind secrets (limb holds the credential, cortex only its name); real microVM cold/warm bench through `/dev/kvm` (`P2-T09`, closed SV-3 on hardware); **govd-as-executor** (`P2-T12`, the Agent-mode keystone). |
| **P3** supply chain | 16 | the registry self-governs | Signed, publicly-logged, revocable releases; the **alchemy** engine (over putrefactio/alembic) adversarially verifies that code matches its declared blueprint (concordance). |
| **P4** formal proof | 9 | proven before it runs | Workflow + settlement lifecycle model-checked (TLC + Apalache) free of deadlock and conservation violation; emit-mutation closes the proof's escape hatch (`P4-T07`). |
| **P5** ops / observability | 5 | it stays up | Store backends, observability surfaces benchmarked; **HA active-passive lease** (`P5-T04`) — exactly one active governor, failover without two kernels deciding at once. |
| **P6** money | 21 | the work pays for the work | Double-entry settlement, formally proven + bisimulated against spec; escrow with expiry / auto-refund; markets + reputation; effort-vs-work payment gate; dust account for penny-exact rounding (`P6-T15`). The ladder closes. |

### Key engineering decisions

- **The kernel-for-agents thesis (the reframe).** govd, exod, and the LLM are three privilege-separated
  roles, never one process. govd *decides and records but never runs*; exod *runs, fully confined, and
  signs what it did*; the cortex *only proposes*. This is enforced, not conventional.
- **govd → exod containment delegation** (the v1.1 keystone, `P2-T12`). govd authorizes the claim, then
  **delegates the limb to exod** rather than executing: exod resolves grant-authorized secrets
  server-side (double-blind — the cortex never sees them), runs the step as nobody/65534, and signs the
  attested result with Ed25519; govd verifies the attestation and records status. Decider and runner
  stay distinct end to end.
- **The skillChip is a cartridge, not a pile of files.** The root `index.json` + `chip_sha` define the
  **load set** — the exact, content-addressed bundle that mounts. One cartridge compiles to a single
  skill or a roster (`infra/tool/cartridge.py`). Because the chip is hash-pinned, what govd authorizes
  and what exod loads are provably the same artifact; bodies mount the verified gallery **read-only**
  and never clone.
- **Double-entry settlement.** Every run debits and credits balanced accounts — money and work
  cross-checked, never asserted. A `SettlementAdapter` seam exposes idempotent `fund`/`payout`/`status`
  over two backends (idempotency keyed on plan/run sha); the lifecycle is formally proven and
  **bisimulated** between spec and implementation. An effort-vs-work payment gate schema-validates and
  meters `llm/*` calls — you pay for attested work, not raw effort. A **dust account** absorbs sub-unit
  remainders at the adapter boundary, so splits and fees stay penny-exact and conservative (no money
  created or destroyed).
- **Tier → sandbox-backend wiring.** Governance tiers map to P2 sandbox profiles behind one driver
  (`bwrap` ↔ gVisor `runsc`), with the community tier enforcing a no-secrets floor — risk tier picks
  the actual confinement strength.
- **No local topology in the repo.** Deploy ships a generic `fleet-setup.sh` + template; real node
  names and tailnet IPs live only in `~/.cyberware/fleet.json`, never committed.

### Timeline (origin/main, v1.1 tail)

1. **Reframe to agent-mode** — plan adapted to the kernel-for-agents framework; added milestone **M7**
   and the keystone **P2-T12 (govd-as-executor)**.
2. **Settlement foundations** — settlement lifecycle formally proven; markets + reputation; escrow
   expiry / auto-refund; settlement **bisimulation**; attested settleable meters.
3. **Auth + agent mode close** — govd Bearer-principal auth + token-bucket; double-blind secrets +
   govd-as-executor → **M7 closed**.
4. **Containment delegation lands** — exod resolves grant-authorized secrets server-side; **govd
   delegates the limb to exod** (the architectural keystone).
5. **Hardening** — crash-atomic Store persistence; fail-closed remote auth; a self-bounty security
   program run *through cyberware's own ledger*.
6. **Deploy / fleet** — rootless confined body & edge anchor entirely under `$HOME`; generic fleet
   setup with no local topology in the repo; unified non-root body image (govd + exod), runsc-ready.
7. **R2 tail** — store backends, gVisor tier, payment gate, dust/rounding, tier→sandbox wiring, HA
   lease. Board reaches **91/91**.

---

## v1.2 — Roadmap

v1.1 proved each piece in isolation. **v1.2 wires them into one enforced floor**: tiered law on top of
a signed, monotone, never-root, server-executed base. The through-line — turn the *intended* kernel
into the *enforced* kernel: the agent can only **know**; every **act** is a governed syscall the node
cannot self-relax. The north-star userspace operator
([netrunner-flathead](https://github.com/rhCat/netrunner-flathead), its own private repo) becomes
safe-by-construction only once the kernel boundary below it actually holds.

### Theme 1 — Tiered governance (the centerpiece)

Model: **core hard-enforced / non-core local-law / discovery via API / high-risk human signoff.**
~2/3 of the substrate exists; v1.2 builds the missing third plus the invariant that makes it sound.

- **`core:` manifest tag** — branch govern on `core:true|false` instead of binary permitted-or-not.
- **Local-laws layer** — per-node / per-org tunable laws replace the single global `OVERSIGHT_RULE.json`;
  non-core dev skills are admitted via local law, not an `unknown_skill_perk` reject.
- **Floor-monotone invariant (the blocker).** Laws may only **tighten** — add denials, raise thresholds,
  shrink the roster — never loosen the floor `{chip-authentic load set} ∪ {non-approvable bans} ∪
  {never-root}`. Enforced and tested as a property; tiering is unsound without it.
- **Move the floor off the node.** Today the node is both subject and judge. Fold
  `nonapprovable_set_hash + chip_sha + policy_sha` into the **signed grant path** so a node that edits
  its own rules cannot mint a grant the issuer key honors.
- **`delegated` by default for non-core** — exod's signed result is authoritative; the node can't
  self-report "ok". `policy_sha` surfaced on `/health` and every provenance record (drift detectable).
- **Principal-filtered `/catalog`**, **high-risk-must-be-core**, **real dual-control signoff** (approver
  is a *different* high-risk principal + a second factor), and wiring the built-but-uncalled `orgs.py`
  into the request path for per-org isolation.
  - **Per-actor token ACL** — the first piece of this, designed in full: a per-token skill+tier+secret
    capability scope, with an operator-signed attestation + client token-possession proof so a compromised
    govd node can neither widen a token nor misattribute a run. See
    [per-actor-acl-design.md](per-actor-acl-design.md) (M0 base ACL → M1 attestation → M2 binding).

### Theme 2 — Real-money settlement (Stripe rail)

The settle-time rail is built and proved one live test-mode charge (transparent split as metadata).
v1.2 productionizes it: **auto-collect at settle** (govd fires `collect_run_tax` server-side — the
agent never calls Stripe), **meter mode** for sub-cent micro-tax, **Stripe Connect** multi-party
payout (real split, not metadata-only), a hardened **live-key guard** (idempotency = `plan_sha`,
card-only, refuse `sk_live_` until explicitly enabled), and the gated **live-mode cutover**.

### Theme 3 — Server-side fleet execution (the kernel proper)

Make "the agent can only know, never act" the *enforced* default. **Default govd→exod dispatch** (flip
from agent-executes to server-side delegated); **fix the confined-step regression** (post-reboot
`apparmor_restrict_unprivileged_userns=1` breaks bwrap and rootless runsc — operator clears it and
re-validates the sweep); **validate the gVisor `runsc` path** fail-closed; **uniform govd+exod bodies**
with a net-free confined limb; **govern acts not throughput** (meter syscalls, not cycles); and the
first **netrunner-flathead** spike once the boundary holds.

### Theme 4 — Source distribution

One gated source, every body reads the same verified commit. **NAS-updater chip refresh**
(`skill_index --check` gate → ff-only → revert-on-drift), **updater HA / monitoring**, and
**read-only body mount discipline** (mount the gallery at `CW_SRC`, never clone; record_root off the NAS).

### Security invariants (cross-cutting — gate every theme)

Not tasks to schedule but properties every v1.2 change must preserve; each gets a property test or
review gate.

- **exec-never-root** — execution faithful under the user's uid or a scoped assumed-role, never ambient
  root. The CI `CYBERWARE_ALLOW_ROOT=1` escape is host-env-only (the agent can't set it) and print-only,
  never a ledger event.
- **no privileged path** — privilege stays *out* of the kernel; host ops (install, `systemctl`, `/etc`)
  are out-of-band, owned by the operator or a separate privileged agent outside the trust boundary.
- **deny-by-default tailnet ACLs** — tailnet membership is L3 reachability, not authorization; exod is a
  local unix socket, never on the overlay; the CI runner reaches nothing on the tailnet.
- **floor is monotone & off-node** — local law may only tighten; the floor lives in the signed grant
  path, not node-owned files.
- **value-free + closure-pinned everywhere** — discovery, provenance, and signed results carry
  `var_keys` / `snippet_shas` only, never secret values.
- **review-before-merge on enforcement surfaces** — every change to govern / exod / settle / tier runs
  the multi-agent adversarial review *after commit, before merge* (it caught a real RCE blocker that
  green gates missed); merge only on a fully-green gauntlet.

### Sequenced critical path

1. Unbreak confined bodies + refresh the chip (fleet must execute before anything else is real).
2. Monotone floor in the signed grant path (the blocker — tiering is unsound without it).
3. Default server-side dispatch (flips "can only know" from intended to enforced).
4. Core tag, local laws, delegated default (the tiered model proper).
5. Auto-collect tax + real dual-control signoff (money + human-in-loop for high-risk).
6. First netrunner-flathead operator, once the boundary holds.

---

## Provenance

cyberware v1.1 was built by a **task swarm**: a DAG of self-contained task files, each redeemed by a
driver script that ran the work through cyberware's own governed channel and recorded a signed `pass`
into the hash chain. That full scaffolding — the swarm task files, the per-task redeem drivers, the
playbook, and the gitignored run-evidence — has been moved out of this repo and archived privately at
**[github.com/rhCat/cyberware-dev-archive](https://github.com/rhCat/cyberware-dev-archive)**. It is
preserved for audit but is not part of the shipping engine.

What stays here, in `docs/`, is the **authoritative, machine-checkable record**:

- **[`done-ledger-v2.json`](done-ledger-v2.json)** — the 91/91 done-ledger. Schema 2, chain head
  `done-ledger-v2`: a genesis (superseding the v1 `done-ledger`, 10 entries) plus **81 signed,
  prev-hash-chained `pass` entries** (seq 2→82). Re-verifiable end to end — a one-byte edit is caught.
- **[`pm-report.md`](pm-report.md)** — the refreshed program report (91/91, all 8 milestones closed),
  the human-readable twin of the ledger's roll-up.

To re-verify the program closed honestly, from the repo root:

```sh
# chain-verified milestone picture — re-verifies the done-ledger prev-hash chain
python3 -m infra.tool.skilltest --skill cws-observe --perk status
```
