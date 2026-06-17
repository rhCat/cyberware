# cyberware v1.1 — known blockers (honest residuals)

Tasks that cannot be honestly redeemed in the current environment. Each is a *real* ceiling, not a
software gap, and is left explicitly unmet rather than faked (meta-rule: building is running).

## B1 — microVM perf budgets (P2-T09 / cws-bench) — needs /dev/kvm

**Status:** blocked on hardware. M3 / SV-3 sits at **9/10** because of this.

**What:** P2-T09's acceptance includes microVM budgets — `microvm_cold_ms ≤ 1500`, `microvm_warm_ms ≤ 250`
— which require a microVM backend (Firecracker / cloud-hypervisor) and therefore `/dev/kvm` + nested
virtualization.

**Why blocked:** the only Linux kernel available here is Docker Desktop's LinuxKit VM on macOS, which exposes
**no `/dev/kvm` (0 virt-capable CPUs)** — confirmed:
```
$ docker run --rm --privileged python:3.12-slim bash -lc 'ls /dev/kvm; grep -cE "vmx|svm" /proc/cpuinfo'
ls: cannot access '/dev/kvm': No such file or directory
0
```
So there is no microVM to cold/warm-boot and time. `infra/exec/bench.bench_microvm()` returns
`{"skipped": "no /dev/kvm ...", "within": null}` — the budget is left **unmet, never fabricated**.

**What IS done:** the bwrap branch of P2-T09 is built and measured — `cws-bench/bwrap-overhead` reads exod's
attested meters (P2-T07) and proves per-step **p95 ≈ 3.5 ms ≤ 100 ms**. P2-T07 is redeemed; the rest of the
M3 cone (P2-T01/T02/T03/T08) is redeemed via cws-redteam.

**To unblock:** run on a **KVM-capable Linux host** (bare metal or a VM with nested virt). There, build the
microVM `SandboxProfile` variant (a Firecracker/cloud-hypervisor driver behind the same interface as the
bwrap profile — P2-T04 is the same seam), time a cold boot + a warm reuse, and redeem P2-T09 → M3 = 10/10.
The crypto/channel/meter layers (grants, exod, attested meters, cws-bench) are backend-agnostic and ready.

## B2 — kernel cws-redteam / sandbox tests are Linux-only

Not a blocker, a platform note: the bwrap boundary (`infra/exec/sandbox.py`, the cws-redteam corpus,
`tests/test_sandbox.py` / `test_redteam.py`) needs **Linux + bubblewrap**. It SKIPS on the macOS dev box and
the plain compute CI image, and RUNS in the exec image (`infra/exec/Dockerfile.exec`, `docker run
--privileged`). All such tests are green there (67/67 last certified). This is by design, not a gap.

## B3 — concordance (alchemy, P3-T08) — NOT a blocker; engines exist, wrapper pending

**Status:** the v1.1 plan review flagged "concordance ontology" as the one true blocker. It is **resolved as
a build dependency**: the concordance engines were built in the **putrefactio phase** and are present locally
— `~/hunyuan/alembic` (declared-blueprint engine + `cargo alembic --synthesize` L++ emitter, plus the
`citrinitas-phase2` binary that backs P3-T09) and `~/hunyuan/putrefactio` (the analysis layer + `laws/`).
P3-T08's deliverable is explicit: *wraps pinned alembic + putrefactio in **file-mode** (no warehouse dep)*.

The four perks map to confirmed file-mode tool runs: **extract** (`python -m python_typestate_extractor
<dir>` → NDJSON L++ blueprint per fn — proven), **conserve** (leaf-map classify → acquire/release imbalance
vs `putrefactio/laws/` → `unexplained_defects`), **classify** (leaf-family naming → `unnamed`), **concord**
(extracted CFG ⊆ alembic declared blueprint + stored diff). Remaining build work: author `skillChip/alchemy/`
with the four perks, pin alembic+putrefactio+laws commits in `deps.lock`, add a CI **skip-guard** (the two
repos are not in CI — gate on a local-only binary, as the bwrap/tlapm/apalache perks do), redeem P3-T08, then
wire **P3-T09 Citrinitas** (the `citrinitas-phase2` binary) into cws-release to close **SV-4 → 14/14**. This
is a focused integration session, not a hardware ceiling. See the `alchemy-reuse-path` memory.
