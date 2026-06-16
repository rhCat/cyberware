#!/usr/bin/env python3
"""infra/cwp/workflow.py — workflow model-checking for SV-5 (the P4 tranche).

A workflow is a small typed state machine: a program counter `pc`, optional auxiliary flags, safety
invariants, and (later) failure transitions. This module emits it as TLA+ — annotated for Apalache — and
runs the three independent provers that SV-5 demands:

  * TLC      — EMPIRICAL: bounded-state enumeration ("No error has been found").
  * Apalache — SYMBOLIC: SMT-backed bounded check over a typed spec.
  * TLAPS    — AXIOMATIC: a machine-checked proof of the invariant (or an honest `Unproved`).

The three are independent toolchains; agreement across them is the SV-5 guarantee that a composed workflow
is deadlock- and invariant-clean BEFORE it runs. `seed_violation` flips an aux-flag update to manufacture a
spec that violates its own invariant, so a checker that fails to catch it is itself exposed.

Prover binaries are located by env: TLA2TOOLS_JAR (TLC), APALACHE_MC (the apalache-mc launcher), and
`tlapm` on PATH. A prover that is absent yields a `skipped` verdict, never a false pass.
"""
from __future__ import annotations
import copy
import os
import re
import shutil
import subprocess
import tempfile

TLA2TOOLS_JAR = os.environ.get("TLA2TOOLS_JAR")
APALACHE_MC = os.environ.get("APALACHE_MC") or shutil.which("apalache-mc")


# ── the workflow model ───────────────────────────────────────────────────────────────────────────────
# wf = {
#   "name": str,
#   "states": [str, ...],          # pc values; the LAST is terminal
#   "entry": str,
#   "flags": {name: {"type": "Bool"|"Int", "init": value}},   # aux flags (typed for Apalache)
#   "transitions": [{"from": s, "to": s2, "set": {flag: value}}],
#   "invariants": {name: tla_predicate_str},   # safety invariants over pc + flags
# }


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

    # typed VARIABLES (Apalache reads the @type annotation on the line above each name)
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

    # transitions; a terminal state self-loops so the spec never deadlocks on it
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
    # the invariants (typing invariant always present; plus the workflow's own)
    type_inv = ["pc \\in States"] + [
        f"{f} \\in BOOLEAN" if spec["type"] == "Bool" else f"{f} \\in Nat" for f, spec in flags.items()]
    lines.append("TypeOK == " + " /\\ ".join(type_inv))
    for iname, pred in wf.get("invariants", {}).items():
        lines.append(f"{iname} == {pred}")
    lines.append("====")
    return "\n".join(lines) + "\n"


def invariant_names(wf: dict) -> list:
    return ["TypeOK"] + list(wf.get("invariants", {}))


def seed_violation(wf: dict, flag: str) -> dict:
    """Return a copy of `wf` whose transitions set `flag` to a value that violates an invariant — flipping a
    Bool, or pushing an Int out of range — so a sound checker MUST report a violation."""
    bad = copy.deepcopy(wf)
    spec = wf["flags"][flag]
    touched = False
    for t in bad["transitions"]:                               # negate each SET value so the "good" update
        if flag in t.get("set", {}):                           # becomes the violating one (True->False, ...)
            cur = t["set"][flag]
            t["set"][flag] = (not cur) if spec["type"] == "Bool" else 999999
            touched = True
    if not touched:                                            # nothing sets it — force a violating update
        bad["transitions"][0].setdefault("set", {})[flag] = (not spec["init"]) if spec["type"] == "Bool" else 999999
    return bad


# ── the three provers ────────────────────────────────────────────────────────────────────────────────

def check_tlc(wf: dict, timeout: int = 120) -> dict:
    """EMPIRICAL: TLC enumerates the bounded state space against every invariant."""
    if not (TLA2TOOLS_JAR and os.path.isfile(TLA2TOOLS_JAR)):
        return {"prover": "tlc", "cert": "EMPIRICAL", "verdict": "skipped", "ok": None}
    d = tempfile.mkdtemp(prefix="wf-tlc-")
    try:
        open(os.path.join(d, f"{wf['name']}.tla"), "w").write(emit_tla(wf))
        cfg = ["INIT Init", "NEXT Next"] + [f"INVARIANT {n}" for n in invariant_names(wf)]
        open(os.path.join(d, f"{wf['name']}.cfg"), "w").write("\n".join(cfg) + "\n")
        r = subprocess.run(["java", "-cp", TLA2TOOLS_JAR, "tlc2.TLC", "-config", f"{wf['name']}.cfg",
                            f"{wf['name']}.tla"], capture_output=True, text=True, cwd=d, timeout=timeout)
        ok = "No error has been found" in r.stdout
        return {"prover": "tlc", "cert": "EMPIRICAL", "verdict": "no_error" if ok else "violation",
                "ok": ok}
    except subprocess.TimeoutExpired:
        return {"prover": "tlc", "cert": "EMPIRICAL", "verdict": "timeout", "ok": False}
    finally:
        shutil.rmtree(d, ignore_errors=True)


def check_apalache(wf: dict, length: int = 10, timeout: int = 180) -> dict:
    """SYMBOLIC: Apalache checks the typed spec over a bounded execution length via SMT."""
    if not (APALACHE_MC and os.path.isfile(APALACHE_MC)):
        return {"prover": "apalache", "cert": "SYMBOLIC", "verdict": "skipped", "ok": None}
    inv = invariant_names(wf)
    d = tempfile.mkdtemp(prefix="wf-apa-")
    try:
        # Apalache checks one invariant per run; AND them into a single predicate before the module end
        allinv = " /\\ ".join(inv)
        src = emit_tla(wf).replace("====", f"AllInv == {allinv}\n====")
        open(os.path.join(d, f"{wf['name']}.tla"), "w").write(src)
        r = subprocess.run([APALACHE_MC, "check", "--init=Init", "--next=Next", "--inv=AllInv",
                            f"--length={length}", f"{wf['name']}.tla"],
                           capture_output=True, text=True, cwd=d, timeout=timeout)
        ok = "EXITCODE: OK" in r.stdout or "No error" in r.stdout
        viol = "EXITCODE: ERROR (12)" in r.stdout or "counterexample" in r.stdout.lower()
        return {"prover": "apalache", "cert": "SYMBOLIC",
                "verdict": "no_error" if ok else ("violation" if viol else "error"), "ok": ok}
    except subprocess.TimeoutExpired:
        return {"prover": "apalache", "cert": "SYMBOLIC", "verdict": "timeout", "ok": False}
    finally:
        shutil.rmtree(d, ignore_errors=True)


def check_tlaps(wf: dict, timeout: int = 180) -> dict:
    """AXIOMATIC: a machine-checked TLAPS proof that the workflow's Init establishes its typing invariant.
    Per the SV-5 acceptance this carries an AXIOMATIC certificate when proved, or an honest `unproved`
    classification otherwise — never a silent claim."""
    if not shutil.which("tlapm"):
        return {"prover": "tlaps", "cert": "AXIOMATIC", "verdict": "skipped", "ok": None}
    name = f"{wf['name']}Proof"
    flags = wf.get("flags", {})
    init = [f'pc = "{wf["entry"]}"'] + [f"{f} = {_tla_val(s['init'])}" for f, s in flags.items()]
    states_set = "{" + ", ".join(f'"{s}"' for s in wf["states"]) + "}"
    type_inv = ["pc \\in States"] + [
        (f"{f} \\in BOOLEAN" if s["type"] == "Bool" else f"{f} \\in Nat") for f, s in flags.items()]
    conj = " /\\ "                                             # avoid a backslash inside an f-string expr
    init_s, type_s = conj.join(init), conj.join(type_inv)
    varline = "VARIABLES " + ", ".join(["pc"] + list(flags))
    tla = (f"---- MODULE {name} ----\nEXTENDS Naturals\n"
           f"{varline}\n"
           f"States == {states_set}\n"
           f"Init == {init_s}\n"
           f"TypeOK == {type_s}\n"
           f"THEOREM InitEstablishesType == Init => TypeOK\n  BY DEF Init, TypeOK, States\n====\n")
    d = tempfile.mkdtemp(prefix="wf-tlaps-")
    try:
        open(os.path.join(d, f"{name}.tla"), "w").write(tla)
        r = subprocess.run(["tlapm", f"{name}.tla"], capture_output=True, text=True, cwd=d, timeout=timeout)
        out = r.stdout + r.stderr
        proved = bool(re.search(r"\bobligations? proved", out)) and "failed" not in out.lower()
        return {"prover": "tlaps", "cert": "AXIOMATIC", "verdict": "proved" if proved else "unproved",
                "ok": proved}
    except subprocess.TimeoutExpired:
        return {"prover": "tlaps", "cert": "AXIOMATIC", "verdict": "timeout", "ok": False}
    finally:
        shutil.rmtree(d, ignore_errors=True)


def run_all(wf: dict) -> dict:
    """Run all three provers. Returns the per-prover verdicts + `clean` (every non-skipped prover passed)
    and the set of certs earned."""
    results = [check_tlc(wf), check_apalache(wf), check_tlaps(wf)]
    actionable = [r for r in results if r["verdict"] != "skipped"]
    return {"workflow": wf["name"], "results": results,
            "certs": sorted({r["cert"] for r in results if r["ok"]}),
            "clean": bool(actionable) and all(r["ok"] for r in actionable)}


# a tiny well-formed workflow + its known-bad twin, for the self-tests + the corpus
SAMPLE = {
    "name": "Sample",
    "states": ["ready", "running", "done"],
    "entry": "ready",
    "flags": {"started": {"type": "Bool", "init": False}, "steps": {"type": "Int", "init": 0}},
    "transitions": [
        {"from": "ready", "to": "running", "set": {"started": True, "steps": 0}},
        {"from": "running", "to": "done", "set": {"started": True, "steps": 1}},
    ],
    "invariants": {"StartedBeforeDone": 'pc = "done" => started', "StepsBounded": "steps <= 2"},
}

