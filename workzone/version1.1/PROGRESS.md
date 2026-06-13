# cyberware v1.1 — progress report (for review)

*Snapshot: 2026-06-13.* A point-in-time review of the v1.1 build. Every claim below is checkable — the
"verify it yourself" section runs the same gates the work is held to. Nothing here is asserted that the
machinery cannot redeem.

## 1. Where we are, in one paragraph

The platform now **grades and builds itself against the plan**. Five validator skills live in the chip,
a standing self-monitor gate runs them in CI, the project observer tracks progress *by redemption* in a
tamper-evident done-ledger, and the first execution tranche — the six P0 specification documents — has
been authored and **redeemed through the governed channel**. The CWP conformance primitives
(canonicalization + signing) exist, with an independent Go implementation reproducing the canonicalizer
byte-for-byte as the external anchor. The honest frontier: 6 of 90 tasks redeemed, the SV-1 (protocol)
rung substantially in hand, and the load-bearing spine (exod / Ledger-v2 / settlement) still ahead.

## 2. What has been built

| component | what it is | status |
|---|---|---|
| `cws-mutate` | mutation-tests a gate (V-MUT) — proves a gate actually gates | built · self-proving |
| `cws-ledgercheck` | verifies a run-ledger is a sound chain (SV-2 precursor) | built · self-proving |
| `cws-conform` (`repin`, `doclint`) | re-pins chip authenticity (SV-1) + structural spec lint (P0-V10) | built · self-proving |
| `cws-modelcheck` (`check`, `corpus`) | deadlock-checks a blueprint (structural + TLC) + catches known-bad | built · self-proving |
| `cws-observe` (`status`, `redeem`) | tracks DAG progress by redemption + writes the done-ledger | built · self-proving |
| `infra/tool/selfmonitor.py` | the standing gate: blueprints deadlock-free · chip authentic · enforcement-surface mutation ratchet | built · **runs green in CI** (7m26s) |
| `infra/cwp/canonical.py` | RFC 8785 JCS — the single canonical-bytes path; correct ES6 number formatting | built · 22 tests |
| `infra/cwp/sign.py` | DSSE / Ed25519 signing over canonical bytes | **in review (PR #15)** |
| `verifiers/go/` + `spec/vectors/` | an independent Go JCS impl + a 246-vector corpus + the cross-language diff | built · **anchors canonical.py byte-for-byte in CI** |

Every validator's in-skill self-test runs through the *real* governed channel (compile → executor →
assert); each was adversarially reviewed and its self-test hardened to prove detection, not just
execution (see `tests/test_cws_validators.py`).

## 3. What has been redeemed

A task is **redeemed** only when a governed validator run passed and was recorded in the prev-hash-chained
done-ledger — never asserted. As of this snapshot, **6 of 90 tasks** are redeemed (the full P0 spec set):

| task | deliverable | grill finding |
|---|---|---|
| P0-T01 | `spec/cwp-core.md` | the protocol envelope + message set + error model |
| P0-T06 | `spec/lpp-semantics.md` | L++ semantics, composition, the abstraction↔data-plane refinement |
| P0-T09 | `spec/keys.md` | M2 — key lifecycle |
| P0-T10 | `spec/privacy.md` | M5 — crypto-shredding |
| P0-T11 | `spec/time.md` | M8 — time authority |
| P0-T12 | `spec/inflight.md` | M9 — the five in-flight transitions |

The live ledger is [`cyberware-swarm-v1.1/done-ledger.json`](cyberware-swarm-v1.1/done-ledger.json); the
worked example of one redemption (claim → governed evidence → verdict) is in [`conform/`](conform/); the
current task-by-task picture and the M0–M6 milestone closures are in
[`observe/observe.json`](observe/observe.json) (`6 redeemed · 10 ready · 22 blocked:deps · 52
blocked:validator`).

## 4. The operating model

```
cws-observe/status  →  author the deliverable  →  cws-conform / -modelcheck / -ledgercheck / -mutate
   (what's next)         (spec / code / skill)       (validate THROUGH the governed channel)
        ▲                                                          │
        └──────────  cws-observe/redeem  ←───────────────────────┘
                     (passing run-ledger → done-ledger entry)
```

- **Redeem, don't assert.** Progress is denominated in verifiable artifacts; `cws-observe/status` derives
  done-state from the chained ledger, not from a task's `status` field.
- **Self-monitoring is on (SV-1/SV-2 level).** `selfmonitor` gates every push; the first improvement loop
  closed on real engine code (`govd.py` mutation 0.75 → 1.0 after tightening `test_govd.py`), and the
  mutation ratchet now protects those tests.
- **External anchors (meta-rule M3).** Canonicalization is anchored by an *independent* Go implementation
  reproducing `canonical.py` byte-for-byte; blueprints by TLC; gates by mutation survival.

## 5. In flight

- **PR #14 — Go JCS verifier + cross-language anchor.** Merged to main (codeqc + selfmonitor green in CI).
- **PR #15 — `sign.py` (DSSE/Ed25519).** CI green + mergeable; merge pending (it touches
  `.github/workflows/codeqc.yml` to install the new dep, which needs `workflow` token scope). Introduces
  the first external dependency (pyca/cryptography, plan T02) via `requirements.txt`.
- **PR #16 — this progress report** (docs only).

## 6. Honest status — what is NOT yet redeemed

- **P0-T02 / P0-T07 / P0-T08** (the JCS canonicalizer, the ≥250-vector corpus, the Go verifier) are
  **built and cross-impl-verified for canonicalization + digests**, but their full acceptance also needs
  **signature** vectors/verdicts (unblocked now by `sign.py`, PR #15) and — for P0-T02 — the published es6
  number corpus (an external download). They remain un-redeemed until that integration lands. *This is the
  discipline working: real evidence, no overclaim.*
- `cwp-core.md` / `lpp-semantics.md` were authored as **as-built / as-planned** specs grounded in the real
  code + plan (the v1.0 source they were "carried" from is absent from the repo) — a deliberate, recorded
  choice, not a recovery.
- **The spine is still ahead:** exod (the kernel boundary, P2 → SV-3, the MVP), Ledger-v2 (P1 → SV-2),
  the settlement plane (P6 → SV-6). The validators for those (`cws-redteam`/`-bench`/`-chaos`/
  `-settle-sim`) and `alchemy` (blocked on the import + the concordance ontology question, see the plan
  review) cannot be authored honestly until their subjects exist.

## 7. Next steps

1. Merge PR #15 (signing).
2. Wire **signature vectors** into the corpus + **sig verdicts** into the Go verifier → redeem
   P0-T02/T07/T08 through the loop.
3. Then the spine: **Ledger-v2** (completes `cws-ledgercheck` → SV-2), then **exod** (→ `cws-redteam`/
   `-bench` → SV-3, the first externally-credible demo).

## 8. Verify it yourself

```sh
python3 -m pytest                         # the full suite (344 passed, 14 skipped at this snapshot)
python3 -m infra.tool.selfmonitor         # the platform grades its own engine (blueprints · authenticity · mutation ratchet)
cd verifiers/go && go test ./...          # the independent Go JCS impl, on its own
python3 -m pytest tests/test_crosslang.py # Go reproduces canonical.py byte-for-byte across the corpus
```
Then read [`README.md`](README.md) for the layout, and run `cws-observe/status` against
`cyberware-swarm-v1.1/` for the live redemption picture.
