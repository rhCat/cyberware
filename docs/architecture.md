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

The chip is a **multi-source cartridge** and skills are **namespaced**: a skill is addressed
`<namespace>:<name>`, the namespace being its **source-group** dir — cyberware's own `cws-*` skills in `cws/`,
the rest in `general/`, an upstream's in its own dir (`nvidia/`, `claude/`, …). The same leaf can exist under
two namespaces (`general:search` ≠ `magnumopus:search`). `registry.parse_skill_id` splits an id;
`registry.skill_dir` resolves `ns:name` directly to `<chip>/<ns>/<name>` (a flat `<chip>/<name>` compiled
single-skill cartridge still resolves bare). A **bare** claim is a back-compat shim — `registry.canonicalize`
rewrites it to `ns:name` when **exactly one** namespace owns the leaf, and returns the `AMBIGUOUS` sentinel
(→ govd rejects `ambiguous_skill_id`) when **≥2** do, never first-source-wins. The **v2 manifest is the
authoritative load set** (keyed on `ns:name`), never a directory scan; each per-skill `index.json` keeps the
bare leaf + a placement-invariant `skill_sha`, so a skill composes verbatim across chips.

**Composing a chip from sources.** `python3 -m infra.tool.compose --out <dir> --source <pathA> --source
<pathB>:<namespace>` merges several source chips into one served chip, each skill placed by namespace; an exact
`ns:name` duplicate across sources is a **hard error** (exit 2, manual reconciliation — never first-source-wins),
while a shared leaf under different namespaces coexists. The composed chip re-pins its v2 manifest and is built
atomically (temp dir + swap); `chipfetch` then serves it exactly like a baked chip.

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
upon. `skillChip/<ns>/<skill>/`:

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

## The three govern gates

Before govd blesses a claim, `govern()` runs **three independent, fail-closed gates** — each an AND (any one
failure rejects; none is self-approvable by `--approve`):

1. **VALIDATE** — authenticity. The skill's files must match its committed `index.json` (`verify_skill`); a
   drifted or server-drifted skill is refused. govd never blesses code it cannot vouch for.
2. **ACCESS-1** — the skill's **own** access policy (`skillChip/<ns>/<skill>/access.json`, enforced by
   `infra/govern/skillacl.py`): is this skill reachable *here at all*? A skill is **local-open /
   remote-closed** — served on a govd run for the local developer (`--mode local`), or to a principal flagged
   `local_dev`, but it must opt in (`{"remote": true, "principals": [...], "min_tier": "..."}`) to be reachable
   when govd serves **others**. An undeclared skill stays remote-open until the operator flips
   `skillacl_enforce`, then the secure default takes hold. Independent of *who* claims.
3. **ACCESS-2** — the **per-actor** token ACL (`principals.acl_allows`): may *this* principal run this
   skill/perk/tier? Entries match by exact `ns:name`, a per-namespace `ns:*` wildcard, the `*` super-wildcard,
   or a legacy bare leaf (back-compat). Independent of the skill's own policy.

All three re-run on every in-flight step (`step_reauthorize`), so a revocation, a tightened ACL, or a tightened
`access.json` binds a running multi-step run — not just the claim.

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

## Crypto custody — the KeyStore seam

Key custody sits behind **one adapter seam** (`infra/cwp/keystore.py`) so the backend can evolve — a file
today, an HSM tomorrow — without touching the signing surface. The abstract `KeyStore` defines the whole
custody contract: `generate` a key under an id, expose its 32-byte raw public key and its resolvable cwp
`keyid` (`sign.keyid`), `sign` with it, and answer `has` / `list_keys`. The contract is deliberately
narrow on one axis: **where the private key lives is the backend's secret**, never part of this surface.

Two backends ship, and both pass the **same** `contract_suite`:

- **`FileKeyStore`** — exportable custody: keys persist as raw private bytes on disk at mode `0600`
  (`os.open(..., O_CREAT, 0o600)`), so a fresh instance over the same directory finds them again. This
  proves the seam is *real* persistence, not in-memory bookkeeping.
- **`SoftPkcs11KeyStore`** — an HSM-shaped backend: private keys live in an in-process `_token` dict and
  **never leave it**. There is deliberately **no** export method — signing happens "in the token"
  (`self._token[key_id].sign(...)`). It stands in for a real PKCS#11 adapter and proves the seam supports a
  **non-exportable-key** backend behind the *identical* contract.

`contract_suite(ks)` is the single suite every backend must satisfy: the keyid resolves
(`ed25519:`-prefixed, 24 chars), `has`/`list_keys`/`missing_is_absent` are correct, a signature is 64 bytes,
verifies over its own message, and **rejects a wrong message**. `keystore_drill` then asserts the seam-level
properties: both backends pass the suite, the file backend persists across a fresh instance, and the HSM
backend exposes none of `export_private` / `private_bytes` / `private_key` — non-exportability checked by
construction, not by promise. So a future PKCS#11 or cloud-KMS adapter is a drop-in: pass the same suite and
the signing surface above never learns the difference.

## Supply-chain attestation — what runs is what was published

The release path binds **the chip** and **the live engine** into signed, offline-verifiable artifacts, all
anchored to a **pinned publisher root** committed in the repo at `spec/tuf/publisher-root.pub` (TUF-style:
the root travels with the repo, the private key never does).

**Blob attestation (in-toto).** `cosign.attest_blob` (`infra/cwp/cosign.py`) hashes a blob to its sha256,
binds that digest as the `subject` of an **in-toto v0.1 Statement** (`intoto_statement` → `_type`,
`predicateType`, `subject[].digest.sha256`, `predicate`), and Ed25519ph-signs the statement's canonical
(JCS) bytes into a DSSE envelope a cosign `verify-attestation` consumer accepts. The cwp native signatures
stay pure Ed25519; this adapter bridges the one algorithm gap (sigstore's Ed25519ph) through the OpenSSL CLI
(`>= 3.4`), so envelopes interop in both directions.

**The engine mutual handshake** (`infra/cwp/engineattest.py`). The engine is a reproducibly-built anchor; at
release time the publisher signs an **engine attestation** — a DSSE over `{engine_digest, version}` where
`engine_digest = sha256(engine bytes)`. Before two principals run together (engine ↔ govd/chip), each side
both **verifies the other's attestation under the pinned root** *and* **re-measures the other's live binary**,
requiring the live digest to equal the signed digest (`attest_live`). `mutual_handshake` succeeds only if
**both** sides are `attested`; a **one-byte tamper on either side** changes the live measurement, the digests
diverge, and the handshake fails **closed** to `engine_unattested`. An unsigned/forged attestation also fails
here, because it never verifies under the pinned root.

**The dual-signed release receipt.** Two distinct receipt objects exist, both DSSE/Ed25519ph:

- `engineattest.release_receipt` binds the **chip release** (`release.sign_release`, the chip's `chip_sha`
  plus every skill's `skill_sha` from the chip `index.json`) and the **engine attestation** into one object,
  so `health_matches_signed_release` is checkable: the live engine must measure to the published
  `engine_digest` *and* the chip release must verify — all under the pinned root.
- `receipts.py` is the run-level receipt: **two independent** Ed25519-DSSE signatures over the **same**
  in-toto Statement (e.g. the executor that ran a step and the approver that blessed it). `verify_receipt`
  requires both signatures to verify under **two distinct keyids** *and* the payload to be a consumable
  in-toto Statement. A single signature is **not** dual-signed; a tampered statement fails; and two
  signatures from the **same** key (different keyid labels) do not pass as dual-signed against two distinct
  public keys.

The capstone is `publish.governed_release` (`infra/cwp/publish.py`): one receipt carrying the chip release,
the engine attestation, **and** an offline transparency-log inclusion proof. `verify_governed_release`
checks all three legs offline under the pinned root — re-verify the release signature, re-measure the live
engine, replay the inclusion proof. `release.tri_layer_check` models the **tri-layer refusal** the design
calls for: it runs the release verification and carries that one verdict to **all three named entry points**
(chipfetch acquire, govd boot, exod run), so an unsigned or tampered release is refused at every layer rather
than at one bypassable gate. This is a pure verification function — the published verification surface — not
yet a live call wired into the `chipfetch`/`govd`/`exod` daemons themselves. Each module ships a hermetic
selftest that tampers each leg in turn and confirms the receipt fails closed.

## The store backend contract — a derived index every adapter must earn

The chained JSONL (`infra/store/chainstore.py`) is the **artifact of record**; a `StoreBackend`
(`infra/store/backend.py`) is a **derived, fully re-derivable** queryable index over it — what makes the
provenance store queryable (and, on Postgres, durable + shared). Two backends ship behind one interface:

- **`SqliteWalBackend`** — the default/free tier: local sqlite in WAL mode, always `configured`, no server.
  The shared connection (`check_same_thread=False`) is serialized through an `RLock` so each statement and
  each `BEGIN IMMEDIATE…COMMIT` lease transaction is atomic per-connection.
- **`PsycopgBackend`** — the durable tier (psycopg3 / Postgres-15). It is **inert until a DSN is wired**:
  `configured()` is `False` until `store.dsn_file`/`dsn` is set server-side, every op returns
  `"unconfigured"`, and `psycopg` is imported **lazily inside the methods**, so the default tier and the
  hermetic selftest never require psycopg or a live Postgres. The DSN is read at connect time and **never
  echoed** — even the error path returns only the exception class + message (truncated), never the DSN.

`make_backend(root, config)` selects: Postgres **iff** `store.dsn_file`/`dsn` is set, else local sqlite-WAL
at `<root>/index.sqlite` — mirroring the inert-until-keyed posture of the settlement Stripe rail.
`index_record` is an **insert-or-skip on `(run_id, seq)`** (`INSERT OR IGNORE` / `ON CONFLICT DO NOTHING`),
so a crash that re-mirrors the chain tail can never double-write.

`store_selftest` is the **six-property hermetic contract** every adapter must pass:

1. **interface_conformance** — every method is callable on **both** backends (a convention probe, not
   `abc.ABCMeta`).
2. **round_trip** — index rows fold back to exactly the chain's non-genesis records (by `seq` and `fields`).
3. **idempotent_replay** — re-mirroring the whole chain returns all `"duplicate"` and the index is
   unchanged.
4. **reconcile_exact** — each row's `link_digest` equals an **independent recompute straight from the chain
   file** via `chainverify` (the artifact of record is the oracle, not the index).
5. **torn_tail_safe** — a crash-torn final chain line is tolerated; the index ends exactly where the chain
   validly ends.
6. **backend_inert_until_configured** — `PsycopgBackend({})` is unconfigured and its ops are graceful
   no-ops (`status == "unconfigured"`).

So the Postgres tier never needs a live database to be *proven correct against the contract*, and a future
adapter is admissible only when it passes the identical suite.

## SV-3, enriched — a second sandbox backend that provably cannot weaken the boundary

The community/SV-3 tier adds a **second** confinement backend behind the **same** value-free
`SandboxProfile` (`infra/exec/sandbox.py`): gVisor (`runsc`) renders the profile as an **OCI runtime spec**
(`oci_config`) — readonly rootfs, every capability dropped, `noNewPrivileges`, the network namespace
unshared unless granted, the masked `/proc` paths, the read-only system binds + the one read-write
workspace, the step dropped to `nobody` (uid/gid `65534`). The `SandboxProfile` is the single source of
truth; each backend *realizes* it.

The proof that the second backend cannot **weaken** the boundary is `confinement(profile, backend)`: it
extracts the **full** security boundary from the **actual rendered output** (the bwrap argv or the OCI
spec), **not** re-derived from the profile. The dict is **total** over the boundary's properties — the
capability binds, the **full** namespace set (pid / ipc / uts / cgroup / user / mount + network), the
nobody uid/gid, dropped caps, no-new-privileges, the readonly root, **and** the masked `/proc` surfaces.
Two backends are **seam-equivalent iff their `confinement()` dicts are dict-equal**, and
`community_tier_selftest` asserts exactly that for the core, a network-granted, and a custom-bind profile
(`seam_parity = all(confinement(p, "bwrap") == confinement(p, "runsc") ...)`). Because the dict is total, a
coarser equality would be vacuous: a dropped pid namespace or an un-masked `/proc` file would slip through —
here it breaks parity and fails the selftest. The grant's sandbox **tier** selects the backend as a
**monotone floor** (`backend_for_tier` / `strongest`): an untrusted `community` perk ratchets up to `runsc`,
an unknown tier fails safe to `runsc`, and a trusted perk on a `runsc`-floored host is never silently
downgraded.
