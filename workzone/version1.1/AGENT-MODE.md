# cyberware v1.1 — the agent-mode framework (a reframe of the remaining tail)

*Added 2026-06-22. A **reframe** (in the plan's disposition culture, §0): the canonical 90-task DAG and the
SV-1…SV-6 cones are unchanged; this doc re-reads what is **left** through the architecture cyberware was
always converging on — a **kernel for agents** — and shows that the remaining tail *is* that build-out.*

---

## 0. The realization

An LLM is **pure information** — tokens in, tokens out. **Thinking needs no limb.** A body-actor (a human, a
robot) cannot separate cognition from action: the hand is wired to the brain, so you can only constrain it
*after* arming it. An LLM's cognition is *already* separable — so you can sever it from the limb at **zero
cost**: the agent loses nothing it actually needs (it still *knows* everything), it just *acts* through a
kernel. The security then falls out of the substrate instead of being bolted on.

This is the inversion. The usual model **arms the cognition** with tools and hopes alignment holds. cyberware
**disarms the cognition entirely** — it holds only information — and puts *all* capability behind a governed
kernel. The worst a misaligned, prompt-injected, or compromised agent can do is **propose** the wrong thing;
the kernel refuses. The blast radius of "the LLM does something bad" is bounded to "the LLM *says* something
bad."

## 1. The OS model

| operating system | cyberware | built? |
|---|---|---|
| userspace process | **the agent / LLM** — the *cortex*. KNOWS and PROPOSES anything; DOES nothing directly | — |
| **kernel** | **govd** — the *nervous system*. Routes intent → action, gates the unsafe reflex, records everything. Never executes | ✅ |
| syscall | a **value-free claim** — intent as information → authenticated → blessed plan → faithful execution → information back | ✅ |
| privileged hardware / the hand | **exod** — the *limb*. Does the work under govd's command; reports back **signed proprioception** (the attested meter) the cortex cannot fake | ✅ |
| the machine | the **VPS** the agent lives on; **cws-neoclaw** is its handle to the kernel (the syscall interface) | ✅ |

The kernel-enforced boundary (bwrap/gVisor namespaces, signed capability grants, the **no-root** faithful
uid, the tamper-evident ledger) is **SV-3, closed**. The information-only return — *status only, never the
command output crosses to the control plane* — is `run_governed`, built. The whole SV ladder is closed:
**the kernel is hardened, reproducible, tamper-evident, and (the settlement core) formally proven.**

## 2. The deployment

To put an agent on a VPS you hand it exactly three things:

1. a **token** — its principal identity to govd (**P1-T08**). *Identity, not capability*: it says who is
   knocking; it does **not** hand over the worker's secrets.
2. an **endpoint** — the govd URL.
3. the **skill** — `cws-neoclaw` + `cyberware.md`: how to issue governed syscalls.

That is the entire install. The minimalism *is* a security property: the agent's whole attack surface becomes
"can POST claims to an authenticated endpoint." Across the wire, **only governed information** travels —
**intent out, attested status back** — never a secret, never raw command output on the control plane.

## 3. The one architectural shift this framework names — **govd-as-executor**

Today `run_governed` executes **client-side**: govd blesses + grants + records, exod attests, but the
executing process sits on the *caller's* side. For the deployment in §2 to be **literally** true — the agent
never runs anything, the **worker machine** executes, only governed information crosses — execution must move
**server-side**: the agent POSTs intent to govd, **govd fires exod on the worker**, and returns status.

This is **govd-as-executor**, and it is the *assembly* of primitives that already exist, not new ground:
`exod` as a remote daemon over mTLS (**P2-T02**), the executor-as-thin-client when `EXOD_URL` is set
(**P2-T11**, redeemed), `cws-neoclaw/run` forwarding a sub-claim to a node (built), gated by the two
keystones below. It is now a **tracked task — `P2-T12`** (validated_by `cws-redteam`, deps `P1-T08` + `P2-T05`
+ `P2-T11`) and the **gate of milestone `M7` — Agent-mode**, so `cws-pm` / `cws-observe` report the stage's
closure alongside the SV cones (first report: **M7 7/10, open**).

## 4. The remaining tail, re-grouped as the agent-mode roadmap

20 un-redeemed tasks (the canonical DAG/cones are untouched). Read by layer:

### A. The syscall boundary — identity + secrets (the keystone; locally buildable, no infra)
| task | layer | what it is in agent-mode |
|---|---|---|
| **P1-T08** | nervous system | **auth** — *which* cognition is calling (Bearer → principal → quota → TLS). The kernel must know who knocks. **The one thing preventing the deployment in §2.** |
| **P2-T05** | limb | **double-blind secrets** — the limb holds the credential, the cortex holds only its *name* (`sec_config.json`); `*_FILE` injected step-side; a scan proves the agent has **zero secret bytes**. "Agent leaks the secret" becomes structurally impossible. |
| P5-T03 *(dep on T08)* | nervous system | the multi-tenant capstone — org → principals → policy → quotas + SPIFFE identities + revocation scopes. |

### B. The limb on a Linux node — *unblocked because the node is Linux* (these are not "blocked," they were host-blocked)
| task | layer | unblock |
|---|---|---|
| **P2-T04** | limb | gVisor `runsc` isolation (community-tier; "manifest cannot request secrets"). gVisor's ptrace platform needs **no `/dev/kvm`** → runs on the VPS today. |
| **P5-T05** | nervous system | W3C traceparent claim→grant→exod + in-toto attestations — end-to-end trace of a remote run. Needs the exod plane → the node has it. |
| **P5-T01 / P5-T04** | the body's persistence | sqlite→**Postgres** store; active-passive HA (advisory-lock lease) → *"available no matter what the local box is doing"* — the Flathead availability requirement. |
| P3-T11 *(dep)* | nervous system | tier enforcement at grant (core→bwrap, community→microVM). |

### C. The work-pays-for-work loop, live on the node
**P6-T08** (exod-metered LLM settle + provider receipts — keys via the double-blind model), **P6-T14**
(Stripe fund/payout, key held double-blind), **P6-T03** (escrow `expires_at` / expiry-refund).

### D. Orthogonal — kernel hygiene / settlement-completeness (not agent-mode)
**P1-T06** (remove `--list` exec — hardens executor *faithfulness*, mildly relevant), **P4-T07** (emit_tla
mutation), **P6-T07** (code↔blueprint bisimulation — cheap now the settlement model exists), **P6-T15**
(banker's-rounding dust), **P6-T16** (single-writer group-commit), **P6-T20** (vulns-as-bounties — reuses the
P6-T10 markets), **P5-T02** (SSE dashboard — remote monitoring of the node), **P6-T09** (`skillChip/llm/`
declared-I/O contracts).

## 5. The critical path

```
  P1-T08  ──►  P2-T05  ──►  [ govd-as-executor : execution moves server-side ]  ──►  P5-T03
  (who is      (the limb        the agent posts intent, the worker executes,         (orgs / policy /
   calling)     holds the        only governed information crosses — §2 made          SPIFFE — federated
                secret)          literal)                                             identity)
        the node-side limb runs in parallel and makes the worker real:
        P2-T04 (isolation) · P5-T05 (provenance) · P5-T01 + P5-T04 (durable + always-available)
```

Build the keystone (**P1-T08 → P2-T05**), assemble **govd-as-executor**, and the deployment in §2 is no
longer a metaphor — it is the running system: a **cortex on a VPS that can think about anything and can only
*act* by asking the kernel, which holds every limb and every secret.**

## 6. Disposition — now a *tracked* stage

Began as a **reframe**; promoted to a **tracked stage** (2026-06-22). The change is **additive**: the swarm
gains exactly one new task, **`P2-T12` (govd-as-executor)**, and one new milestone, **`M7` — Agent-mode**
(gate `P2-T12`); the DAG goes **90 → 91**. The **M0–M6 cones, the done-ledger, and every existing task are
unchanged** — the keystone tasks `P1-T08` + `P2-T05` were already in the DAG; M7 just draws the cone around
them + the integration. `cws-pm` / `cws-observe` now report **M7** alongside the SV cones (first report:
**M7 7/10, open** — the 7 are the foundational primitives already redeemed; the 3 open are the keystone
`P1-T08` + `P2-T05` and the integration `P2-T12`). Generator: `generate_swarm.py` (single source). See
[`pm-report.md`](pm-report.md) / `runs/pm-agentmode-first/pm.md` for the board.
