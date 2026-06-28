# Roadmap

cyberware is a research build climbing in the open. What ships today is on the
[security ladder](architecture.md) and mapped in the [intent atlas](atlas.html); this page is what is
**deliberately deferred** — honestly, so a reader can tell shipped from planned.

## Org / tenant isolation — built, not yet wired

`infra/govern/orgs.py` implements per-org read/claim isolation (`authorize` / `can_access`, SPIFFE-style
identities, an org-nested `resolve_scope` hook), but the claim path (`do_POST`) does **not** yet dispatch to
it — so there is no *shipped* per-org isolation, and no doc claims there is. Wiring it — org-nested scope
resolution on the govern + WS step paths, plus per-org ledger read isolation — is the next multi-tenancy
step. Today the per-actor ACL bounds a **token**; org isolation bounds a **tenant**, and is a deliberate
Phase-2 (it carries the usual review-before-merge discipline for a kernel change).

## Fleet discovery — pull shipped, gossip deferred

`infra/govern/fleetd.py` ships the `:8773` discovery plane (default-on, beside govd's `:5773`): each node
live-probes its roster peers' `:5773` and answers *which node runs skill X* (`GET /fleet/find`). This is the
**stateless pull** design — smallest correct surface, no shared written state, no roster-poisoning, graceful
self-only when there is no fleet. The **gossip/registry** tier (each node converges a local roster and answers
routing from memory with no per-query fan-out) is deferred until the fleet outgrows the pull design's
`N × probe` cost — and it deliberately adds a node-identity signing step, so it is a reviewed kernel change,
not a drop-in.

## Per-actor ACL — the Phase B flip

The ACL ships in **Phase A**: scoped principals are enforced deny-by-default; unscoped principals are
allowed. **Phase B** (`acl_strict` — deny-by-default for unscoped tokens too, and exod's enforce-vs-audit
mode) is an operator-chosen, coordinated fleet flip, made once every actor a node serves carries a scope.
Mechanics + the milestone history are in [per-actor-acl-design.md](per-actor-acl-design.md).

## Settlement — research-stage

The economic layer ([settlement.md](settlement.md)) is exercised mostly by in-module selftests rather than a
live deployment, and the payment rail is **inert until an operator wires a key**. Production hardening — live
rails, dispute operations, FMV seeding, the credit tier at scale — is future work and a specialist's call;
the correctness floor (exact-decimal money, conservation-checked double-entry, funded-escrow admission) is
the part that ships.

## SV-3 — the microVM performance tier

The kernel-enforced execution boundary is **9/10**. The one open brick is the microVM performance tier,
which reports `skipped` where `/dev/kvm` is absent (never faked) — a deployment/hardware step, not a code
gap. The boundary itself (bwrap / gVisor, non-root, signed status) is closed.
