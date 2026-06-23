# Architecture

cyberware is a **verifiable governance runtime for skill execution** — a subset of the Cyberware
Alchemistry at a different angle, and the local instance of the
[Zero Trust Framework](https://github.com/rhCat/trust-model-reflection)'s delegation pillars: the
intelligence *proposes*, the framework *validates / composes / compiles / oversees*, and is the only
channel that *executes*. Blueprints are [L++](https://github.com/rhCat/lpp); Python is the glue.

## Two sides

cyberware is the **engine**; the skills are a separate **cartridge** — the [**skillChip**](https://github.com/rhCat/skillChip), its own git repo vendored here as the `skillChip/` submodule (the "feed-stock cartridge"). The engine reads every skill from the chip; the chip carries no governance of its own.

| side | what | where |
|---|---|---|
| **skillChip** | the cartridge — the skills, each a self-contained, verifiable **package** (context · lifecycle · pathways · contracts · authenticity · proof). A separate repo, vendored as a submodule. | `skillChip/<source>/<skill>/` |
| **governance** | the engine — the infrastructure that validates · composes · compiles · oversees · executes — and governs/audits as a service | `infra/` |

The chip is located by `infra/registry.py` (`registry.SKILLCHIP`): the hardcoded default `<repo>/skillChip`, overridable with **`$CYBERWARE_SKILLCHIP`**. The chip is **self-describing** — `skillChip/index.json` is its **manifest**: every skill with its `skill_sha`, plus a roll-up `chip_sha`, which cyberware retrieves to discover + verify the whole chip as a unit (each skill keeps its own `index.json` for file-level authenticity). Swap the chip — point `$CYBERWARE_SKILLCHIP` elsewhere — and the same engine governs a different feed-stock, unchanged.

The chip is a **multi-source cartridge**: skills live under a **source group** — cyberware's own `cws-*` skills in `cws/`, the rest in `general/`, and skills merged from a named upstream in their own dir (e.g. future `nvidia/`, `claude/`). Names are unique across sources; `registry.skill_dir(name)` resolves a skill NAME to its directory whatever the layout — flat (`<chip>/<skill>`, e.g. a compiled single-skill cartridge) or source-grouped (`<chip>/<source>/<skill>`). The **manifest is the authoritative load set**, never a directory scan; a porter never assumes its depth in the chip (enforced by the `check_porter_path_hygiene` ouroboros gate), so a skill stays relocatable across sources and cartridges.

`infra/` is a Python package, invoked as `python3 -m infra.<pkg>.<module>`:

- **`infra/govern/`** — the pipeline (`validator`, `composer`, `compiler`, `oversight`, `executor`,
  `runlog`) **and the service plane** (`govd`, `govd_client`).
- **`infra/exec/`** — the **kernel-enforced execution boundary** (SV-3): signed capability `grants`, the
  `exod` daemon (a separate principal whose signature is the only status the ledger trusts), the bwrap
  `sandbox` SandboxProfile, the `capmanifest` capability-manifest check, exod-attested `meters`, and the
  `redteam` / `bench` adversarial + overhead corpora. See [the section below](#the-kernel-enforced-execution-boundary-sv-3).
- **`infra/cwp/`** — the wire/cryptographic primitives: RFC-8785 `canonical`ization, Ed25519/DSSE `sign`,
  the Ledger-v2 `chainverify` chain, `cosign` interop.
- **`infra/tool/`** — registry tooling: `visualize` (blueprint → drawio/SVG), `skill_index`
  (authenticity), `skilltest` (in-skill self-tests), `scaffold` (new skills), `selfmonitor` (the standing
  self-validation gate — the ouroboros).
- **`infra/document/`** — the framework's own formal artifacts (the pipeline blueprint, the rule files).

## A skill is a package

A skill is **not a prose description you trust** — it is a self-contained unit you can verify and build
upon. `skillChip/<skill>/`:

```
SKILL.md            context: what it does, what to watch, which logs to check
blueprint.json      the L++ lifecycle (ready → prepared → verified → executed)
perks.json          the proven pathways (id · summary · tools · destructive?)
ledger.json         the form the agent fills → task-ledger.json
index.json          per-file sha256 + a roll-up skill_sha — the authenticity manifest
perks/<perk>/
  metadata.json       rules · usage · limitation · minimal_example
  manifesto.json      the ${VAR} template: tool sequence · env · requires
  src/contracts.json  the tool's I/O + checks
  src/<tool>.sh       the entry point (a Python core sits behind a thin .sh porter)
  test/case.json      the perk's OWN governed self-test (+ a fixture/ dir)
```

Six mechanically-connected blocks, each verifiable rather than asserted: the **blueprint** is
model-checked (TLC), the **contract** is enforced at execution, the **index** pins every file, the
**test** proves the perk through the real channel. Add or change any block and the skill's `skill_sha`
changes — a skill's identity *is* the hash of its parts.

## Two execution planes

The same governance runs two ways, sharing `validator` / `composer` / `compiler` / `oversight` /
`executor`:

**1 · Local pipeline** (in-process) — the agent runs the stages itself, end to end:

```
SKILL.md ─► LLM fills the form → task-ledger.json
            │
   validator.py   claims real? — record_store writable, runtime + required binaries reachable,
            │                    contract's required inputs present, host reachable (soft)
   composer.py    L++ → TLA+ → TLC — no abstract deadlock (non-terminal sink); structural fallback
            │                        (reachability / terminal-reachable) when no JRE/tla2tools
   compiler.py    blueprint + manifesto + contracts + snippets → ONE step-wise bash + run.{drawio,svg}
            │                        (the diagram annotated with this task's tool sequence)
   oversight.py   OVERSIGHT_RULE over the script — destructive/dangerous patterns push back; approvable
            │                        rules waived only by an explicit, logged --approve (pre-flight view)
   executor.py    THE channel — .bk tamper-check, IN-CHANNEL oversight scan (refuses on violations;
                                 waivers ledger-recorded), upstream gate, run-ledger provenance, EXECUTOR_RULE
```

**2 · govd — the service plane** (`infra/govern/govd.py`, a control/audit plane). **No data crosses the
boundary.** The agent authenticates with its **principal Bearer token** (a hardened/remote govd carrying a
principals registry requires it — `401` without; the client reads it from a `*_FILE`/env pointer like a
secret, never argv) and sends a **claim** (skill, perk, var **KEYS** — never values, files, or secrets);
govd checks it against its **own** trusted registry, runs compose + TLC, and blesses a **value-free,
code-free PLAN** (tool sequence + each snippet's sha256 + a `${VAR}` wrapper), pinning the plan's sha256.
The agent binds its vars **locally**, runs the porters+cores **from its own registry**, and reports
**status** over a per-run WebSocket; govd owns the provenance ledger and monitors the plan **hash**.
Secrets are never plaintext — a `*_FILE` pointer is read at runtime via `cat`. Full detail:
[`governance-service.md`](governance-service.md).

The govd **container boots through `infra/govern/chipfetch.py`** — acquire + validate, *then* exec govd —
so it serves only a chip that passes the same gate as the build (every skill's `index.json` + the chip
manifest); a drifted chip **refuses to boot**. The chip is acquired **local** (the baked submodule,
re-validated) or, with `CLOUD_MODE=1`, **live-cloned** from `CLOUD_SOURCE` at `CLOUD_SOURCE_TAG` (private
via `CLOUD_SOURCE_TOKEN`, token-safe). `/health` then attests *which* cartridge is governed — `chip_sha`
plus acquisition provenance (`local`, or `cloud source @ ref`).

> This pipeline is itself captured as a formal **L++ blueprint** —
> [`infra/document/pipeline.blueprint.json`](../infra/document/pipeline.blueprint.json) — so the framework
> is described in its own formalism (the **ouroboros**); the dashboard renders it.

## The governance model

`executor.py` is the chokepoint. The agent channels **all** work through it:

1. **Tamper-check** — the script is snapshotted to `.<script>.bk` on first run; if it later drifts
   (an agent editing a compiled step to slip past a contract), the run is **refused**.
2. **In-channel oversight** — the same `OVERSIGHT_RULE` scan runs inside the executor before any step;
   unwaived violations are **refused** (exit 7) and recorded. Skipping the `oversight.py` pre-flight
   does not skip the gate; `--approve` waivers are explicit and ledger-recorded.
3. **Upstream gate** — a step cannot run unless its predecessors are recorded as run.
4. **Provenance ledger** — every run (ts, step, exit, duration, output hash, output tail) is appended
   to `run-ledger.json` under the record_store. Out-of-band runs leave a hole in the chain.
5. **EXECUTOR_RULE** — timeout and other call-boundary limits.

The runtime *is* the rule: you cannot bypass governance without leaving a visible gap (an unrecorded
run, a `.bk` mismatch, a missing upstream step). govd extends the same idea across a boundary — the
per-run session token gates the WebSocket and the ledger read; a `step_result` is recorded only after a
`grant` for that exact step with the blessed `plan_sha`.

## The kernel-enforced execution boundary (SV-3)

`executor.py` enforces the boundary **in software** — a static scan plus a tamper-check. The security
ladder's SV-3 rung makes the boundary **kernel-enforced**: the same governed step runs inside an OS sandbox
under a *separate principal*, so the refusals hold **with the in-process scan disabled** — the boundary is
the Linux kernel and a signature, not a scanner. This is `infra/exec/`:

- **Signed grants** (`grants.py` / `grantverify.py`) — a capability token is an Ed25519/DSSE envelope over
  `{run_id, plan_sha, snippet_shas, capabilities, credentials, nbf, exp, nonce}`. It is verified **offline**
  and is **bound to the request**: a grant minted for one run/plan authorizes *only* that run/plan, carries
  exactly the capabilities it names, is single-use (nonce), and expires (±60 s skew). One grant can never be
  laundered into authority over a different step or command.

- **exod** (`exod.py` / `exodverify.py`) — the **execution daemon, a separate OS principal** (a UDS
  listener with its own Ed25519 identity). It verifies a grant against the request, runs the step inside the
  sandbox, and returns a step-result **signed by exod**. The run-ledger trusts a status **only** if exod's
  signature verifies — a forged self-report (any status not on exod's channel) is refused **and recorded**.
  This *replaces the executor's own "ok"/"error" self-report*: the spine no longer believes the executor
  about its own exit code. The signed result is bound to the grant nonce, so a replayed grant is detected at
  the ledger even across a daemon restart.

- **SandboxProfile** (`sandbox.py`) — the bwrap (bubblewrap) core profile: every namespace unshared
  (user / pid / net / ipc / uts / cgroup), a read-only system tree, **one** writable workspace, the step
  dropped to an unprivileged uid, `/proc/sys` masked read-only and the live-kernel files shadowed (the runc
  `maskedPaths` doctrine). There is **no content inspection** in the path — confinement is purely the
  kernel, so "kernel-enforced" is literal.

- **Capability manifests** (`capmanifest.py`) — a manifest is the *declared* grant of a sandbox; the
  sandbox must **materialize it exactly** (the bwrap command mounts the declared binds, no more and no
  fewer). An ungranted bind, a dropped bind, or a flipped network **refuses** — a tampered profile cannot
  silently widen a step's reach.

- **Attested meters** (`exod` `meter_of`) — exod measures each step's wall time and **signs it** into the
  result. The meter the (future) settlement plane bills is the one the isolated principal attested, never
  the agent's stopwatch.

Two chip validators grade this boundary, and redeem the P2 cone on the cryptographic done-ledger:

- **`cws-redteam`** (V-RED, the M3 gate) — a ≥12-behaviour **expected-refusal** corpus. Each perk mounts a
  real attack (filesystem escape, network egress, mount, sysrq reboot, a forged status, a replayed/expired/
  cross-run/tampered grant, a capability-manifest mismatch, …) **through exod**, with the software scan off,
  and exits `0` **iff the boundary held** — the attack was refused *and* a benign-control oracle was
  accepted (so a silently no-op gate fails the corpus instead of passing it).
- **`cws-bench`** (V-BENCH) — the overhead meter, read from exod's attested meters: per-step bwrap
  `p95 ≤ 100 ms`.

**Platform.** The boundary is the Linux kernel, so `infra/exec/sandbox.py`, the cws-redteam corpus, and
their tests need **Linux + bubblewrap**; they SKIP on a non-Linux host and run in the exec image
(`infra/exec/Dockerfile.exec`, `docker run --privileged` so the sandbox host can drop each step into an
*unprivileged* namespace). The grant/exod/meter/capability layers are platform-agnostic and unit-tested
anywhere. The microVM tier of the sandbox (Firecracker / cloud-hypervisor) needs `/dev/kvm`; where that is
absent it is reported skipped, never faked (see `workzone/version1.1/KNOWN-BLOCKERS.md`).

## The provenance ledger (Ledger-v2, SV-2)

Evidence is **tamper-evident**, not merely trusted. A Ledger-v2 chain (`infra/cwp/ledger.py` +
`chainverify.py`) is a prev-hash chain: a **genesis** entry binds the chain to its origin (`run_id`,
`plan_sha`); each later record's `prev` is the RFC-8785 digest of the prior link, and `verify_chain`
recomputes every `prev` under the schema major — a flipped field or a transplanted genesis breaks the
recompute and the offending record is named. An independent **Go cold-verifier** (`verifiers/go/chain.go`)
reproduces the verdict from the same canonical bytes, so the chain is externally anchored, not
self-attesting. The write path is **crash-safe** (`durable_append`: one `flock` across read-tip → heal a
torn tail → append → fsync; atomic snapshots via tmp + `os.replace` + dir-fsync), so N concurrent writers
serialize into a single valid chain. Two capabilities sit on top:

- **Crypto-shredding** (`shred.py`, P1-T07) — a record's *subject* fields are sealed with a per-record
  AES-256-GCM DEK (dek-id bound as AAD); the ledger stores only ciphertext, so the chain covers the
  ciphertext and **still verifies after a key is destroyed**. Dropping a record's DEK makes that subject
  permanently unrecoverable while every other record is untouched — the right-to-erasure made
  cryptographic: *shred the key, not the chain.*
- **Merkle checkpoints** (`checkpoint.py`, P1-T03) — a checkpoint entry every `interval` records carries a
  Merkle root over its window. **Cold-verify** trusts the last audited checkpoint and re-links only the
  tail after it — **O(tail), not O(chain)** — so verifying a million-entry chain from its last checkpoint
  is window-bounded (≤ 2 s); a **periodic audit** recomputes every checkpoint's root and catches a forged
  one.

`cws-ledgercheck` grades all of it (`verify` · `anchor` (Go cross-check) · `torture` (concurrency) ·
`erasure` · `checkpoint`); `cws-observe/redeem` is the only writer of the prev-hash-chained **done-ledger**.

## The wire protocol (CWP)

The claim / plan / grant / step / verdict messages between the agent and govd are the **Cyberware
Protocol** (`docs/SPEC.md`, `spec/cwp-core.md`): every message is a `{cwp, type, body, sig}` envelope over a
closed, signed message set. The protocol is **machine-checkable** — `spec/schemas/` carries a JSON Schema
(2020-12) per message type, encoding invariants like *value-free body* (a value smuggled into a claim body
fails its schema) and the closed error-reason enum; `cws-conform/schemas` validates a conformance corpus
against them (every valid instance passes, every negative is rejected).

## Authenticity — the skill's identity

Each skill's `index.json` pins the sha256 of every file in that skill plus a roll-up `skill_sha`
(`infra/tool/skill_index`), and the chip's own `skillChip/index.json` manifest rolls those up again into a
`chip_sha` over the whole cartridge. It is the reference both planes verify against, so a skill's version —
and the chip as a unit — is checkable **without passing files back and forth**; only hashes cross the wire:

- **build-time gate** — the Docker image runs `skill_index --check --all` right after copying the
  registry, so a drifted index (a stripped file, an un-regenerated hash) **fails the build**.
- **govd** won't bless a registry that doesn't match its index, and pins the perk's closure hashes in
  the plan; **the agent** verifies its own registry against those hashes before running.
- **discovery** — `GET /catalog` is value-free (skills · perks · var-KEYS · `skill_sha` · verified).
  The agent's client (`govd_client.discover`) compares its local `skill_sha` to govd's and tags each
  skill **verified** (matches the blessed image), **drift** (diverged), or **unverified** (a *new* skill
  the image has never seen — visible but not governable until added and the image rebuilt).

## Self-proof — each skill carries its own test

A perk's `test/case.json` is a **declarative** case — `vars`, a `fixture/` dir, `requires`, and an
`expect` block (`exit` / `outputs` / `nonempty` / `contains` / `json`) — run through the **same governed
channel the agent uses** (`infra/tool/skilltest`: compile → executor → assert). Because the `test/` files
are pinned in `index.json`, the proof is **part of the skill's tamper-evident identity** and cannot drift
from the tool. `tests/test_skill_selftests.py` discovers every case, runs it, and enforces the invariant
that **every skill self-proves**; non-hermetic perks (network, live service, repo-mutating) ship a `skip`
case so the skill still carries — and documents — its proof.

Beyond per-skill proof, the engine grades **itself** — the **ouroboros** (`infra/tool/selfmonitor.py`, a
standing CI gate). Three checks, all redeemable evidence: every chip blueprint **and** the engine's own
pipeline blueprint is deadlock-free; every skill + the chip manifest is authentic (`skill_index --check`);
and an **enforcement-surface mutation ratchet** runs `cws-mutate` over each gate module against a recorded
`floor` (`infra/govern/selfmonitor_policy.json`) that may only *rise* — so the gate protects the very tests
that earn it. The ratchet covers the governed-channel gates (govd / oversight / executor) and the
prose-clean verify cores of the whole ladder: `chainverify` (SV-2 chain), `snippetverify` (SV-2 TOCTOU),
`grantverify` and `exodverify` (SV-3). "Building is running" turned on the framework itself.

## The blueprint (L++)

Every tool skill shares one **perk-agnostic lifecycle**:

```
ready → prepared → verified → executed        (executed = terminal)
```

The terminal is **executed**, not "recorded" — recording is part of *executing*: the executor writes
each step to the run-ledger **as it runs**, not in a separate phase after. `safety_invariants` encode
this — chiefly **`governed_execution_only`** (a task reaches `executed` only through `executor.py`) and
**`record_during_execution`**, plus the skill's own guardrails. Perks are *optional* in the blueprint:
the blueprint says what to watch and which logs to check; a perk supplies the concrete, contract-bound
*how*. The governance pipeline above is itself captured as a blueprint.

Blueprints render as flowcharts (`infra/tool/visualize.py` → drawio + SVG): **state** = rectangle,
**transition** = line, **gate** = diamond (with its `✓ pass` / `✗ fail → exit·log` branches), **action**
= the predefined-process shape showing its `compute_unit`. The **govd monitor dashboard** draws them in a
cyberpunk theme; its **Flow** tab renders the **task** blueprint — the perk's actual gated sequence,
value-free (while the [Pages catalog](https://cyberware.systems/) shows the shared lifecycle plus
each perk's step sequence).

## The agent contract

The loadable entry skill is the root [`SKILL.md`](../SKILL.md): the five-step loop an agent follows —
**discover** what's governed (`/catalog`) → emit the **claim** (its only output; never the commands) →
govd blesses → **run** the blessed plan from the agent's own registry → **review** the verdict. The
agent authors no commands; the skill code is the registry's, blessed by hash.

## Relationship to the rest

cyberware is **not Athenor** (the hosted service that powers the whole Cyberware Alchemistry
workflow). It is the standalone, local enforcement layer — the same verifiable infrastructure
(L++ blueprints, contracts, compiled bash, audit ledgers, authenticity indexes, in-skill proofs),
pointed at general skill execution.
