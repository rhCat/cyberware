---
skill: cws-create
name: Cyberware skill create
perks: [evaluate, scaffold]
---

# cws-create — the on-ramp for new skills

Hand it a candidate skill (a name + a plain description of what it does) and it classifies it:

- **execution** — a deterministic tool/pathway (run, build, query, fetch, …). Fits cyberware directly.
- **design** — a taste/aesthetic skill (palette, typography, layout, …). **Not** the cyberware emphasis —
  the framework governs deterministic execution, not aesthetics. Keep it as guidance.
- **transformable** — mixes both; extract the execution core into a governed pathway, leave the taste as guidance.
- **unclear** — describe what it DOES (inputs → action → output) so it can be classified.

## What to look out for
`evaluate` emits the verdict + the signals it matched + a recommendation, to `evaluation.json`. The verdict
is a keyword heuristic — a recommendation, not a proof; the intelligence makes the call.

## Perks
- `evaluate` — classify a candidate + recommendation (read-only).
- `scaffold` — lay down the cyberware skeleton (blueprint + perks + contracts + snippet stubs) for a fitting
  skill, via `infra/tool/scaffold.py`.

## How to use it
1. `evaluate`: set `SKILL_NAME` + `SKILL_DESC` → the verdict.
2. If execution / transformable — `scaffold`: set `NEW_SKILL` + `NEW_NAME` + `PERKS`
   (space-separated `<pid>:<tool>[:<binary>]`) → the skeleton is created.
