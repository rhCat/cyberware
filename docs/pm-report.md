# cyberware v1.1 — pm report

*Snapshot: 2026-06-25.* Progress is **redeemed, not asserted** — every line below traces to a `pass`
entry in the signed done-ledger (`docs/done-ledger-v2.json`), re-verifiable by chain. See §7.

## 1. Roll-up

**Status: closed — 91/91.**

**Program:** 91 of 91 DAG tasks redeemed — `████████████████████` 100%

`91 redeemed · 0 blocked · 0 dry`

Done-ledger (`done-ledger-v2`, schema 2): **81 `pass` entries** (seq 2→82) atop a genesis that supersedes
the v1 `done-ledger` (schema 1, 10 entries) — **81 + 10 = 91** redeemed tasks across the program. Chain
head `done-ledger-v2`; every entry signed, chained, independently re-verifiable.

## 2. Milestones

| milestone | rung | closure | gate | status |
|---|---|---|---|---|
| **M0** — the spine stands — governed execution end to end (internal) | — | 15/15 | `P6-T05` | **closed** |
| **M1** — SV-1 — the protocol is real and portable | SV-1 | 7/7 | `P0-T18` | **closed** |
| **M2** — SV-2 — evidence becomes tamper-evident | SV-2 | 8/8 | `P1-T09, P1-T10` | **closed** |
| **M3** — SV-3 — execution becomes a kernel-enforced boundary ◀ MVP | SV-3 | 10/10 | `P2-T08, P2-T09` | **closed** |
| **M4** — SV-4 — the registry and the engine publish and revoke themselves | SV-4 | 9/9 | `P3-T09, P3-T15` | **closed** |
| **M5** — SV-5 — workflows and the money's lifecycle are model-checked | SV-5 | 8/8 | `P4-T09` | **closed** |
| **M6** — SV-6 — the work pays for the work (the ladder closes) | SV-6 | 21/21 | `P6-T21` | **closed** |
| **M7** — Agent-mode — the kernel runs the agent's intent (cognition holds no limb) | AGENT | 10/10 | `P2-T12` | **closed** |

_Closure is the transitive dependency cone of each milestone's gate task(s), redeemed against the
done-ledger — the same roll-up `cws-observe/status` computes._

## 3. Per-phase redemption (81 entries in done-ledger-v2)

| phase | redeemed | primary validators |
|---|---|---|
| **P0** governance spine | 8 | `cws-conform`, `harden-pyenv` |
| **P1** ledger | 10 | `cws-ledgercheck`, `cws-mutate` |
| **P2** exec / isolation | 12 | `cws-redteam`, `cws-bench`, `cws-chaos` |
| **P3** supply chain | 16 | `cws-release`, `alchemy` |
| **P4** formal proof | 9 | `cws-modelcheck`, `cws-mutate` |
| **P5** ops / observability | 5 | `cws-bench`, `cws-chaos` |
| **P6** money | 21 | `cws-settle-sim`, `cws-modelcheck`, `alchemy` |

## 4. Blocked

_None._ Every locally-doable and node-dependent task closed; the prior `/dev/kvm` and confined-step
ceilings were cleared on real hardware (P2-T09 microVM bench; fleet live-validated).

## 5. Honest status

The program is complete at the v1.1 scope. v1.1 **proved each property in isolation**; the work of
**wiring them into one enforced floor** (tiered law, server-side dispatch by default, live-money rail)
is v1.2 — see `docs/DEVELOPMENT.md` § *v1.2 — Roadmap*.

## 6. Verify it yourself

```sh
# the chain-verified milestone picture (re-verifies the done-ledger prev-hash chain)
python3 -m infra.tool.skilltest --skill cws-observe --perk status
# re-render this board without firing
PLAYBOOK=<playbook> SWARM_DIR=<swarm> DRY_RUN=1 RECORD_STORE=<dir> python3 cws_pm.py
```

`pm.json` is the machine-readable twin of this report — same data, asserted by the self-test.
