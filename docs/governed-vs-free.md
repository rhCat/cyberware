# Governed loop vs. free loop — why cyberware governs at the gate

> A framework that makes the imaginable real — not a cage that limits imagination.
> The agent's loop stays free to explore; governance applies only at the moment of **commitment**.
> *Free up to the gate; accountable past it.*

This is the thesis behind cyberware, and the reason it is built the way it is. The public version lives on the
[homepage](https://cyberware.systems/); this is the longer argument for people reading the code.

## The shape everyone is converging on

The industry is settling on the same outline: a registry of composable **skills** plus an **agent loop** that
drives them. That outline is the cheap half. The hard half — and the half that decides whether you can hand an
agent something consequential — is the **governance substrate underneath the loop**: provenance (what ran, and
was it the blessed thing), determinism (same plan → same execution), refusal (a gate that says *no* before the
side effect), and auditability after the fact. Those are not features you bolt onto a free loop later. They are
load-bearing from the foundation or they are absent.

## Free for discovery, governed for commitment

The mistake is not that free loops exist — it is claiming the loop should be free *all the way through*. There
is a real phase where you do not yet know the shape of the task: research, exploration, "what even is this."
Schema and refusal there are friction with no payoff; nothing irreversible is at stake. Governance is for the
moment of **commitment** — when the agent is about to touch money, production, or another party's system.

cyberware does not try to govern discovery. It is the layer the discovery phase **hands off to** the instant it
wants to act: *figure it out freely, but you cannot commit except through the gate.* That seam — discovery free,
commitment governed — is more honest and more defensible than "govern everything."

## What "governed" concretely means here

Not a policy PDF — mechanisms, each checkable in this repo (see [architecture.md](architecture.md) and
[SPEC.md](SPEC.md)):

- **Value-free planning** — the governor (`govd`) blesses a plan that carries **no code and no secrets**; the
  agent runs the steps from its own verified registry. Nothing executable crosses the wire.
- **Authenticity chain** — every skill, file, and the whole chip are content-addressed (sha256), so what runs
  is provably what was blessed. A name-validated resolver and a whole-skill (untracked-aware) gate close the
  supply-chain seams.
- **Contracts + model-checked blueprints** — capabilities declare typed inputs/outputs; workflow blueprints are
  proven deadlock-free by three independent provers (TLC, Apalache, TLAPS).
- **A security ladder, SV-1 → SV-6** — protocol & canonical hashing → a tamper-evident hash-chained ledger → a
  kernel-enforced execution boundary (bubblewrap sandbox + a separate execution principal) → signed,
  transparency-logged releases & revocation → model-checking → a settlement layer.
- **The ouroboros** — the engine grades its *own* engine every build, and once a bug-class is caught it becomes
  a standing gate. *Building is running.*

## Why the platforms structurally under-build this

Not incompetence — incentive. A platform shipping a skill harness optimizes for adoption velocity: lowest
friction, broadest reach, quickest demo. The governance layer is a **tax on adoption** that pays off only in the
user's high-consequence cases, never in the platform's growth metrics. So the loop ships and the substrate is
under-invested — predictably. The "fundamental clues" are not secret; they are unrewarded at platform scale.
That is the opening for a project that carries the *consequence* rather than the adoption funnel.

## Overlay, not competitor

Because the chip is a **multi-source cartridge** (`cws/`, `general/`, and a dir per named upstream — see
[architecture.md](architecture.md)), cyberware can **ingest** another ecosystem's skills as a source and run
them governed. The pitch was never "our skills are better." It is **"your skills, accountable."** The
competitive set is not a skill catalog — it is "is there any way to run an agent that touches money or prod with
provenance and refusal," and there mostly is not, yet.

## The agent economy — why SaaS thrives, not dies

The dominant narrative treats the model as a software *substitute*: have the agent write the script. Read it as
a software *consumer* instead and the conclusion inverts — more agents means more software usage, because the
hard parts (correct solvers, threading, numerics, a decade of edge-case polish) are exactly what an agent cannot
improvise and must consume. The lever changes hands, from a human in a UI to a program under contract; the
machinery behind the lever does not go away.

So a vendor's **skillChip becomes a third product surface** — past the UI (for humans) and the API (for
developers): the *blessed, correct, metered* way an agent may use the software. Vendors will ship one not out of
generosity but self-interest:

- **Control** — an API is a surface an agent calls *wrong*; a skill is the vendor encoding the one correct way + the safety envelope. The API, but opinionated.
- **Monetization** — the skill is the metering point: bill the governed run, not the seat.
- **Liability** — when an agent misuses your software, "who's accountable?" becomes existential. A governed skill + ledger is a provable record of correct-usage-or-refusal — the price of entry in regulated domains.

Those three are precisely what the governance layer supplies — correct-by-construction usage (the value-free
plan), ledgerable traceback (the authenticity chain + ledger), and metered pricing (the settlement layer's
quote → meter → settle, billed on the meter the isolated principal signed, never the agent's stopwatch). No SaaS
vendor has all three today.

**Two go-to-market motions, and the gravity between them.** Enterprise buys a license bounded by runtimes (even a
swarm of agents hits the ceiling); a small business pays per use over MCP (access + compute) when it can't afford
to buy. These aren't a stable pair — the moment one agent saturates a per-seat license at machine speed, per-seat
pricing gets arbitraged and vendors migrate toward per-run metering. The license is the transition state; metered
usage is the end-state — and the settlement layer is built for the end-state.

**Professionals get *more* valuable, not less.** Democratizing skill *use* concentrates value in skill
*authorship*: whoever encodes the correct, validated way to run the solver becomes the scarce, paid party — paid
per use through skill lineage (a verified-tier publish pays its ancestor). Authorship becomes IP with a meter.

The honest edge: this is strongest where correctness is non-negotiable — regulated, high-consequence, heavy-compute
work (a statistics package accepted by regulators is not something an agent re-derives on the fly). The disposable
middle gets eaten by throwaway scripts; the proven core survives and gains an agent consumer. Same seam as before —
free for discovery, governed for commitment — drawn across the whole industry.

## Two honest pressure points

- **The capability counter-argument.** *"Smarter models won't need governance."* Capability ≠ accountability.
  A more capable model in a free loop is a more capable **unaccountable** actor — the blast radius of one
  confident-but-wrong commitment *grows* with capability. The better the model, the more you want the gate.
- **Durability.** The overlay value erodes the day a platform bolts on a "good enough" governance. What is hard
  to copy cheaply is not any one feature — it is that the discipline is architectural and cultural: value-free
  planning, the sha chain, contract-first, self-grading in CI. You cannot retrofit "no code crossed the wire"
  onto an in-process loop, and you cannot retrofit a schema-and-refusal culture by writing a doc.

## Honest status

cyberware is a research/build project — **v1.1, building in the open**, with an MIT-licensed chip — that
**dogfoods its own governance** (it builds itself through itself). The security ladder is closed except one
brick gated on hardware (the microVM perf budget needs `/dev/kvm`); the settlement plane and additional skill
sources are in progress. No users-served, throughput, or social-proof claims are made here; the architecture
and the thesis are the substance.

---
**See also:** the [homepage](https://cyberware.systems/) · [architecture.md](architecture.md) ·
[SPEC.md](SPEC.md) · the live [registry dashboard](https://cyberware.systems/dashboard.html).
