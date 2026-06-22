"""P4-T07 — the workflow->TLA+ emitter (infra/cwp/tla_emit.py).

A golden-output pin: emit_tla over a fixed workflow must equal an EXACT expected module. Any single-token
mutation of the emitter (a flipped operator, or a changed token in the emitted TLA+) changes the output and
fails this test — which is what gives cws-mutate a >=0.90 emitter_mutation_score (P4-V04)."""
from __future__ import annotations

import json

from infra.cwp.tla_emit import emit_tla

WF = {
    "name": "Demo",
    "states": ["s0", "s1", "s2"],
    "entry": "s0",
    "flags": {"started": {"type": "Bool", "init": False}, "steps": {"type": "Int", "init": 0}},
    "transitions": [{"from": "s0", "to": "s1", "set": {"started": True}},
                    {"from": "s1", "to": "s2", "set": {"steps": 1}}],
    "invariants": {"Inv": 'pc = "s2" => started'},
}

GOLDEN = json.loads(r'''"---- MODULE Demo ----\nEXTENDS Naturals, TLC\n\nVARIABLES\n  \\* @type: Str;\n  pc,\n  \\* @type: Bool;\n  started,\n  \\* @type: Int;\n  steps\n\nStates == {\"s0\", \"s1\", \"s2\"}\nInit ==\n  /\\ pc = \"s0\"\n  /\\ started = FALSE\n  /\\ steps = 0\nNext ==\n  \\/ (pc = \"s0\" /\\ pc' = \"s1\" /\\ started' = TRUE /\\ UNCHANGED steps)\n  \\/ (pc = \"s1\" /\\ pc' = \"s2\" /\\ UNCHANGED started /\\ steps' = 1)\n  \\/ (pc = \"s2\" /\\ UNCHANGED pc /\\ UNCHANGED started /\\ UNCHANGED steps)\nSpec == Init /\\ [][Next]_<<pc, started, steps>>\n\nTypeOK == pc \\in States /\\ started \\in BOOLEAN /\\ steps \\in Nat\nInv == pc = \"s2\" => started\n====\n"''')


def test_emit_tla_matches_golden_module():
    assert emit_tla(WF) == GOLDEN


def test_emit_tla_reexported_from_workflow():
    from infra.cwp import workflow as W
    assert W.emit_tla(WF) == GOLDEN     # the workflow.py re-export is identical
