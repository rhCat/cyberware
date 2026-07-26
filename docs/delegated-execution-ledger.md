# Delegated execution ledger — exod-sealed records submitted to govd

Design note. Companion to [`pg-provenance-ledger.md`](pg-provenance-ledger.md), which covers the **input**
side (per-step `var_values`, tier-2, encrypted at rest). This covers the **output** side: the execution record
exod produces, and how it reaches govd and outlives the container it ran in.

Written 2026-07-25 after tracing why a governed agent's runs show `pending` with no values in the fleet
monitor. Decisions marked **[RH]** are the operator's.

## The problem, stated precisely

For a verdict-only claim (`hermes:toolgate/read|write|exec|…`) the agent's gate POSTs `/govern`, reads the
verdict, and executes the tool **in its own process**. Measured on the live node:

```
run 1ca4fa6560924b18   decision=allow   seq=['hermes_claim']   events=[]   workspace=NONE
/opt/data/proof.txt    19 bytes, written
```

The file exists; cyberware materialized no workspace, ran no step, recorded no event. `progress 0/1` is
therefore **accurate** — it counts the *plan's* steps, not the agent's action. The ledger records that
permission was granted. It never observes what happened. An `allow` for an action that was never performed is
byte-identical to one that wrote 19 bytes.

That gap closes only when exod does the work. Everything below is what that requires.

## Where the output goes today

A delegated step writes to `rec/` (the RECORD_STORE) inside the workspace govd provisions at
`record_root/_work/<run_id>` (`govd.py:1557`). Observed on the anchor:

```
0ef1a8e7  selftest      ok     -> rec/selftest.json
3898171c  putrefactio   ok     -> rec/mechanical_claims.json (911 KB), rec/transmutation.marble.json
341bb218  putrefactio   error  -> rec/ (empty)
```

Three properties, all consequential:

1. **It is not dropped.** No pruning path exists — the only `rmtree` calls in `infra/` are composer's TLC
   scratch and chipfetch's clone staging.
2. **It is plaintext, mode 644.** The encrypt-at-rest decision covers inputs; outputs get none of it.
3. **It is never surfaced** — not in the chain, not on the wire, not in fleetdash. The chain's `step_result`
   carries only `status`/`exit`/`authority`/`exod_keyid`/`meter`/`result_nonce`/`values_sha`.

Today this is 2.2 MB across 3 workspaces because delegation is rare. Under Phase 2 **every agent tool call
becomes a delegated run**, so this becomes the dominant data on the node.

## Decisions

**[RH] Cargo is a docker mount.** A named volume, agent-side at its work path, node-side at
`/cyberware_cargo`, bound into the confined step per-claim (`ro`/`rw`, already ACL-gated, #214/#215).

**[RH] Work/self split.** Only the *work* subtree is shared. Agent state — `auth.json`, `config.yaml`,
`sessions/` — stays private and is unreachable from any governed step.

**[RH] The execution ledger is SUBMITTED to govd through an endpoint, not left on a mount.** govd keeps full
control of the record, and there is no mount write→read window to lose a record in. A mount is a side channel
with no acknowledgement; an endpoint submission is acknowledged or retried.

**[RH] exod seals; only a govd decrypts.** exod encrypts the value/output ledger to the recipient public keys
it is handed and submits the ciphertext. Private keys live with the govds. Asymmetric, in the card-network
sense: the party that produces the data cannot read back what it has sealed, and only a designated recipient
can open it. *(Which govds are recipients is set per run — see the two decisions below. "Only govd decrypts"
means the executor and the agent never can, not that a single govd is privileged.)*

**[RH] The record's destination follows the request's ORIGIN.** There are two govds — the node's **local** govd
and the **mothership** central govd — and the handshake between them already establishes tier
(`mothership > edge > subagent`). So:

| the run was requested by | exod reports to |
|---|---|
| the mothership (a central command down to a local exod) | **both** local and central |
| the local node itself | **local only** |

A local run is not silently exported upward, and a mothership-commanded run is never only local. Origin is a
property of the request, so it is known before the grant is minted — which is what makes the next point work.

**[RH] Every tool call writes a value report.** Not only delegated runs, and not only destructive ones. A
governed tool call that produces no viewable record is the defect this whole note exists to fix — so the report
is the default, and the question is only *who can read it*.

**[RH] Each party sees its own work by right; anything further needs a two-sided handshake.**

- The **originator** of a request can always read that work's report — *"at the mothership I should be able to
  oversee whatever I am doing."*
- The **executor** can always read what it ran — *"remote actions should be able to view their own works as
  well."* A node is never blind to its own machine.
- For a mothership-commanded run on a remote node, **both** have a legitimate claim and both are recipients
  from the start. No handover is involved; neither is reading the other's private work.
- For a node's **own local** work, the mothership is **not** a recipient. Access requires
  **request + accept**: the mothership asks, and the node grants. The node may decline.

This is a real sovereignty guarantee, not a policy setting: a mothership cannot unilaterally decrypt a node's
local work, because it was never a recipient of that blob and the node's private key never leaves the node.
Handover is an act the node performs, and it is per-record.

> Resolves the open question this note previously left: a local-only run is **unreadable**, not invisible. The
> value-free tier-1 chain row still federates, so the mothership retains full oversight of *what* ran
> everywhere — it simply cannot read the values of work it neither commanded nor executed without asking.

### Consequence: decide the recipient set at seal time, not by handing over a key

Because origin is known at mint time, the grant can carry the recipient set the blob is sealed to:

```
mothership-commanded  ->  value_recipients = [local_pub, mothership_pub]   # both participated
node-local            ->  value_recipients = [local_pub]                   # the node's own work
```

exod seals once, to the parties with a claim. **No key is handed over in either case** — each recipient
decrypts with its own private key, offline, from the blob alone.

### Handover: request + accept, then rewrap

For the mothership to read a **node-local** record, the node must grant it. Two-sided, per record:

```
mothership  --request(run_id, reason)-->  node        # asks; recorded
node        --accept | decline-->         mothership  # the node's call, recorded
  on accept: blob = valuecrypt.rewrap(blob, node_sk, [mothership_pub])   # +a few bytes, no re-encryption
```

The node recovers that blob's DEK with its own key and wraps it to the mothership's public key. Nothing else
is exposed: not the node's private key, not any other record, not future records. **Declining is a normal
outcome, not an error** — and both the request and the answer belong in the chain, so an unanswered or refused
request is as auditable as a granted one.

Symmetric by construction: the same request/accept flow lets a node ask the mothership for a record it did not
execute. The protocol does not privilege the mothership; tier decides *scope of command*, not *right to read*.

> **Do not share the node's private key.** "Local presents the mothership the decryption key" must mean *the
> per-blob DEK, rewrapped* — not the node's X25519 private key. Handing over the private key grants every blob
> the node has ever sealed or ever will, retroactively and prospectively, and cannot be revoked without
> rekeying and re-encrypting everything. `rewrap` grants exactly one record, and revocation is simply not
> rewrapping the next one.

## Why the asymmetry is a real gain, not ceremony

Current tier-2 flow: agent → `var_values` → **govd** (plaintext, transiently) → seals → stores. Hence
valuecrypt's honest limit: a compromised live govd reads them regardless.

Output flow under this design: exod produces → **seals to govd's pubkey** → submits ciphertext → govd stores.
govd never holds output plaintext except when an authorized reveal decrypts it on demand. The at-rest surface
(backups, replicas, an over-granted DB role, a mirrored subagent volume) yields nothing, and so does the
*transit* surface — which matters precisely because this design lets exod be somewhere else.

Note this does **not** change the input side. govd necessarily sees `var_values` — it forwards them to exod.
Inputs stay as designed in `pg-provenance-ledger.md`; only outputs gain the stronger property.

## Mechanism — what already exists

`infra/store/valuecrypt.py` provides the whole envelope, no new dependency:

- `generate_node_key(path)` — X25519 private key, chmod 600; returns the raw public key. govd already
  creates/loads this at boot (`govd.py:392–420`, `self.value_recipients`).
- `_wrap_kek(recipient_pub)` — ephemeral-static X25519 + HKDF-SHA256 per recipient.
- `canon(values)` / `commit(salt, pt)` — canonical bytes and the **salted** tier-1 commitment. Salted so a
  low-entropy value cannot be recovered from the chain by preimage search.
- `rewrap` — add a recipient (mothership oversight at fleet join) by rewrapping the DEK only; the sealed data
  is untouched.

So exod needs one thing it does not have today: **govd's recipient public key**. It travels the same way
`exod_pub` travels the other direction — in the grant. `delegate.py:115` already binds `acl_sha`, `cargo`,
`workspace`, `argv` into the minted grant; a `value_recipients` field is the same shape.

## Delta

| where | change |
|---|---|
| **fleet handshake** (`fleetd.py`) | **exchange X25519 recipient pubkeys alongside the tier.** Today it carries `exec_mode`/`exod_attached`/tier and **no** recipient key — this is the one genuinely missing primitive. Without it a local govd cannot seal to the mothership. |
| origin marker | record which govd/actor requested the run. `principal` already distinguishes a mothership-initiated claim and is on every decision row, so this may need no new field — but note `idx_origin` is **not** it (that table is `(run_id, plan_sha)`, plan pinning for tamper detection). |
| `delegate.py` mint_grant | carry `value_recipients` (raw X25519 pubkeys) into the grant — `[local]` or `[local, mothership]` per origin |
| `infra/exec/exod.py` | after the step: `canon` the record, `commit` a salted `output_sha`, seal to the grant's recipients, attach the blob to the signed envelope (or POST it, below) |
| govd | endpoint `POST /record/<run_id>/<step>` — accepts a sealed blob + `output_sha`, verifies exod's Ed25519 signature over both, stores tier-2, binds `output_sha` into the tier-1 chain event |
| `infra/store/` | `run_records` alongside `run_values` — same shape (`run_id, step, ts, sha, blob`) |
| `_work/<run_id>/rec` | prune once the submission is acknowledged; retain on failure for debugging |
| fleetdash | reveal for outputs, mirroring the existing values reveal |

**Transport.** exod is AF_UNIX-local to govd today, so the sealed blob can ride the existing envelope response
— no new network surface, and the endpoint is unnecessary for a co-located exod. Build the endpoint anyway:
it is what makes a *remote* exod (an agent-side executor in a subagent container) possible without changing
the record path, and it is the acknowledged channel the operator asked for. Same discipline either way: sealed
before it leaves exod, verified on arrival, committed into the chain.

## The approval channel — authorizing actions, not just reading records

The request/accept flow above governs **reading a record**. The same seeing-vs-acting split exists one layer
down, for **authorizing an action**, and it is currently unresolved: the mothership can see every pending
approval and answer none of them.

**Measured 2026-07-25.** Across the whole fleet, 11 destructive claims have ever been approved — 9 of them
from a test harness that injected `request_tool_approval -> {"approved": True}`, and the other two from an
operator using `govd-client --approve` directly. **Hermes' human gate has never once been answered by a
person.** On `maria-dev-mac`: 45 push_backs, 9 approvals, all synthetic. Before the 403/409 transport fix
those push_backs never even reached the gate — they died a layer earlier as `govd HTTP 409`.

The cause is structural. `resolve_gateway_approval()` is the resolver, and every caller is a **chat-platform
adapter** (Discord / Telegram / Feishu / Teams) or a CLI TTY prompt. Maria's cage permits egress to exactly
two destinations — `maria-govd` and `llm-proxy` — so none of them is reachable, and there is no TTY. The
legacy `submit_pending` branch stores the request in an in-process dict **nothing in this deployment reads**.

### govd is the rendezvous

The approval channel needs **no new egress hole**: govd is already the one thing Maria can reach through the
cage, and already where the push_back is recorded. That is strictly better than opening a third hole beside
`llm-proxy` for a chat adapter.

Three parts, of which only the first is built:

1. **The operator can answer** — `POST /approve` on fleetdash re-submits the claim carrying the approve
   token. *(Built; see below.)*
2. **govd records who answered** — the approval decision becomes a chain event
   (`{approved_by, run_id, ts, reason}`). Otherwise the approval moves out of the agent and into a UI without
   the audit moving with it — the same gap as the unaudited reveal endpoint.
3. **The agent waits** — on `push_back`, `_resolve_push_back` must block-and-poll govd for an operator
   decision instead of failing closed in 0.3s, with a timeout that still fails closed. **A button is useless
   if nobody is listening when it is pressed.** Until this lands, approving authorizes the CLAIM and does not
   resume an agent that already gave up.

### What was built, and its security posture

`fleetdash` gains `POST /approve {node, run_id}` and an **approve** button in the `/risk` queue. The dashboard
has **no app-auth** and its monitor tokens are read-only by contract, so the write is gated deliberately:

- **A separate credential.** `approve_token_file` per node (or `GOVD_APPROVE_TOKEN_<NAME>`) — a *principal*
  token the operator provisions on purpose. The monitor token is never reused. **Absent by default**, in which
  case no button is rendered and the read-only posture is exactly as before.
- **CSRF.** Requires `X-Fleetdash-Approve: 1`, a custom header a cross-origin page cannot set without a
  preflight the server never answers — so a hostile site cannot drive-by POST at `127.0.0.1`.
- **Never approve blind.** The run must exist in the mirror and actually be a `push_back`; the claim's own
  `skill`/`perk`/`var_keys` are replayed from the mirrored record, so the UI cannot widen a claim into
  something the agent never made. `--no-mirror` refuses outright.
- **Loopback default** is unchanged — a non-loopback bind still fails closed without `FLEETDASH_ALLOW_OPEN=1`.

**Still open:** the monitor token is one shared secret per node, not a person, so the chain cannot name *who*
approved. Per-operator principals on the monitor plane fix this **and** the reveal-endpoint gap — one change
serving both, and it should land before this button is used anywhere but loopback.

## Implementation constraint the playbook surfaced

**exod must seal and submit from the DAEMON, not from inside the sandbox.** The governed gate includes
`cws:cws-redteam/rt-net-egress`, which asserts a confined step cannot reach the network. If the sealing or the
`POST` happened inside the confined step, that invariant would break — and it is one of the invariants that
makes confinement meaningful. Sequence must be: step runs confined with no network → exits → **exod the
daemon** reads `rec/`, seals, and submits. The sandbox never gains egress.

## Baseline — measured 2026-07-25, before any code

Live PM pass over the governed gate, central node, `mac-coop`, run `e8b68d4f243c4904`: **11 validators passed.**
Four results worth carrying forward:

- **`cws:cws-modelcheck/prove` — TLC 6/6 but Apalache 0/6, cert `EMPIRICAL`.** The formal backend is not
  proving in this image, so proofs degrade to empirical model checking. Pre-existing; know it before claiming
  this feature is "proven".
- **`cws:cws-redteam-sw/rt-tamper-script` — registry mismatch: `rt_tamper_script.py does not match the blessed
  hash`** in `/app/skillChip`. Real drift in the shipped chip copy, flagged by the authenticity index doing its
  job. Resolve before trusting that perk as a gate.
- **`general:py_qc/test` and both `cws-mutate` perks fail with "No module named pytest"** — the body image
  ships no dev environment, so `PROJECT_DIR=/app` tasks are liveness pokes, not evidence. Dropped from the
  gate; run them where a dev environment exists.
- **`redeem: true` failed as "no such task in swarm"** for every step — redemption needs pre-declared swarm
  tasks. Set `false` until `SWARM_DIR` is seeded.

## Open — decide before implementing

1. **Reveal is still unaudited.** `/monitor/values/<run_id>` decrypts and returns plaintext and **records
   nothing** (`govd.py:1024`). Adding outputs multiplies what a silent reveal exposes. The decrypt should
   itself append a signed chain event (`{type: values_revealed, run_id, principal, ts}`), and the monitor
   token — one shared secret per node — should become per-auditor principals.
2. **Retention.** Sealed outputs still grow without bound; encryption is not a retention policy.
3. **Size.** A 911 KB record sealed per step is fine; an agent's `terminal` output could be far larger. Cap,
   or store a digest plus a truncated head, and say which in the record.
4. **Tension with `pg-provenance-ledger.md`.** That design federates node→mothership by **logical
   replication**, with the mothership initiating the subscribe as the admission gate. Origin-routed submission
   is a second path upward, and the two disagree about *what* crosses: replication moves everything a node
   has; origin routing deliberately keeps local-only runs local. That difference is the point of the design,
   so it is the replication path that needs revisiting — decide whether replication is scoped to
   mothership-originated runs, or dropped in favour of submission. Do not ship both by accident.

5. ~~Does a local-only run stay invisible or only unreadable?~~ **DECIDED [RH]: unreadable, not invisible.**
   The value-free tier-1 row federates for every run, so the mothership always sees *what* ran fleet-wide;
   reading the values of work it neither commanded nor executed requires request + accept. See above.

6. **Where does the request/accept flow live?** It is a new two-sided exchange with no home yet — `fleetd`
   carries health and tier, `govd :5773` carries claims. It needs somewhere to sit, and both sides of it
   (the ask and the answer) need to reach the chain, or "the node declined" becomes unauditable hearsay.

7. **What does a decline look like to the operator?** If the mothership UI shows a locked record with no
   affordance to ask, the feature is invisible; if a decline is rendered as an error, operators will route
   around it. It should read as a normal state with a visible history.
