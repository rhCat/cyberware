#!/usr/bin/env python3
"""infra/cwp/tla_emit.py — the workflow -> TLA+ emitter (P4-T07 mutation target).

Extracted from workflow.py as a prose-clean executable core so its mutation coverage is meaningful: a
golden-output pin (tests/test_tla_emit.py) compares emit_tla against an exact expected module, so any
single-token mutation — a flipped operator in the code OR a changed token in the emitted TLA+ — changes the
output and is killed. workflow.py re-exports these names; behaviour is identical.
"""
from __future__ import annotations


def _tla_val(v):
    if isinstance(v, bool):
        return "TRUE" if v else "FALSE"
    return str(v)


def emit_tla(wf: dict) -> str:
    """Emit the workflow as a TLA+ module with Apalache @type annotations + INVARIANT-bearing predicates."""
    name = wf["name"]
    flags = wf.get("flags", {})
    varnames = ["pc"] + list(flags)
    lines = [f"---- MODULE {name} ----", "EXTENDS Naturals, TLC", ""]

    lines.append("VARIABLES")
    decls = [("pc", "Str")] + [(f, spec["type"]) for f, spec in flags.items()]
    for i, (v, ty) in enumerate(decls):
        lines.append(f"  \\* @type: {ty};")
        lines.append(f"  {v}" + ("," if i < len(decls) - 1 else ""))
    lines.append("")

    states_set = "{" + ", ".join(f'"{s}"' for s in wf["states"]) + "}"
    lines.append(f"States == {states_set}")
    init = [f'pc = "{wf["entry"]}"'] + [f"{f} = {_tla_val(spec['init'])}" for f, spec in flags.items()]
    lines.append("Init ==\n  /\\ " + "\n  /\\ ".join(init))

    disj = []
    for t in wf["transitions"]:
        conj = [f'pc = "{t["from"]}"', f'pc\' = "{t["to"]}"']
        sets = t.get("set", {})
        for f in flags:
            conj.append(f"{f}' = {_tla_val(sets[f])}" if f in sets else f"UNCHANGED {f}")
        disj.append("(" + " /\\ ".join(conj) + ")")
    terminal = wf["states"][-1]
    keep = " /\\ ".join([f'pc = "{terminal}"', "UNCHANGED pc"] + [f"UNCHANGED {f}" for f in flags])
    disj.append("(" + keep + ")")
    lines.append("Next ==\n  \\/ " + "\n  \\/ ".join(disj))

    unchanged = "<<" + ", ".join(varnames) + ">>"
    lines.append(f"Spec == Init /\\ [][Next]_{unchanged}")
    lines.append("")
    type_inv = ["pc \\in States"] + [
        f"{f} \\in BOOLEAN" if spec["type"] == "Bool" else f"{f} \\in Nat" for f, spec in flags.items()]
    lines.append("TypeOK == " + " /\\ ".join(type_inv))
    for iname, pred in wf.get("invariants", {}).items():
        lines.append(f"{iname} == {pred}")
    lines.append("====")
    return "\n".join(lines) + "\n"
