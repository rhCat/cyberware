# cyberware — In-flight semantics (`spec/inflight.md`)

> Disposition of grill finding **M9**: the transitions that occur *while a run is in flight* — revocation
> mid-run, initiator cancel, metered escrow, schema evolution, and WebSocket resume — were undefined in
> v1.0. This spec decides them. **Five decisions, each one normative sentence**; everything else here is
> the rationale around them.

This document is normative for the governance plane (`govd`), the privilege boundary (`exod`), and the
settlement plane. It is referenced by P2 (revocation drill, partition/crash recovery), P5 (failover
resume), and P6 (cancel + escrow settlement).

## 1. Revocation mid-run

A revocation that arrives mid-run **MUST** halt at the next step boundary — the running step completes
atomically, and every subsequent `step_request` is refused with reason `revoked` — except that a
revocation carrying `severity: critical` **MUST** instead kill the sandbox immediately, without waiting
for the running step to complete.

*Rationale.* Boundary-halt keeps the ledger consistent (no half-recorded step) for the ordinary case;
the `critical` escalation exists for compromise, where letting the current step finish is itself the risk.

## 2. Initiator cancel

Initiator cancel is a lifecycle transition that **MUST** be legal at any time until the run reaches
`DELIVERED`: on cancel, the completed steps' metered and pass-through costs and the `govd` fee settle, and
the remainder of the escrow refunds.

*Rationale.* Cancel is not an error path; it is a first-class outcome. The initiator pays for work already
done and for the governance that oversaw it, and recovers the rest — conservation holds across a cancel.

## 3. Metered escrow

Metered escrow **MUST** fund the declared cap, and any surplus over actual metered cost **MUST**
auto-release to the initiator at settlement; estimate-plus-top-up escrow is ROADMAP, not v1.1.

*Rationale.* Funding the cap bounds the initiator's exposure up front and guarantees the provider can be
paid up to the cap; auto-release of the surplus is the liveness property that money never gets stuck above
what the meter actually justified.

## 4. Schema evolution

A ledger chain **MUST** verify under the schema major recorded in its genesis, and verifiers **MUST**
support majors N and N−1; a schema migration **MUST** be expressed as a *new* chain carrying a
cross-reference record to the old one — never an in-place rewrite of an existing chain.

*Rationale.* Immutability is the whole point of the audit substrate; "migrate by rewrite" would forge
history. A cross-referenced new chain evolves the schema while leaving every prior record exactly as it
was signed.

## 5. WebSocket resume

A dropped session **MUST** resume by `(run_id, token)`; a replayed `grant` **MUST** be idempotent, and a
`step_result` **MUST** be idempotent by `(run_id, step)` — a duplicate delivery of either changes nothing.

*Rationale.* Networks drop sockets; resume must not double-grant or double-record. Idempotency keyed on
the run and the step makes a redelivered message a no-op, so a flaky transport cannot corrupt the chain.

---

*These five decisions are the closure of M9. Each is enforced by a criterion in the plan — revocation by
P2-V11 / P3 revocation drill, cancel by P6-V14, escrow by P6-V12, schema by P1-V (genesis non-transplant),
resume by P2-V11 / P5-V07 — and exercised by `cws-chaos` once that validator exists.*
