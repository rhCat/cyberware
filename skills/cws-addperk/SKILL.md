---
skill: cws-addperk
name: Cyberware add-perk
perks: [evaluate, apply]
---

# cws-addperk — add a perk to an existing skill, governed

Give it a target **skill** and a **perk** (id + description + the tool it runs). It runs the workflow as
a governed pipeline:

1. **evaluate** — does the perk *belong* to the skill? does it already *exist*? is it *generalizable*
   (a clear deterministic pathway)? Read-only; halts the chain if it shouldn't be added.
2. **apply** — `branch` (create `perk/<skill>-<perk>`) → `formulate` (scaffold the perk + compose to
   validate + commit) → `pr` (push + open a PR to the working branch, and notify you to merge through
   the agent once approved).

## What to look out for
`evaluate` emits the verdict (`ok | exists | out_of_scope | unclear | no_such_skill`) + the signals it
matched, to `perk_eval.json`. The verdict is a heuristic — the intelligence makes the call. `apply`
writes a real branch + PR; the merge is never automatic — you approve, the agent merges.

## How to use it
1. `evaluate`: set `SKILL` + `PERK` + `PERK_DESC` → the verdict.
2. If `ok` — `apply`: set `SKILL` + `PERK` + `PERK_DESC` + `TOOL` + `BINARY` (`bash` or `python3`)
   (+ optional `BASE`, default main) → branch, formulate, validate, and the PR.
