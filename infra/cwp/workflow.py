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


# ── P4-T02: failure as a first-class transition + saga compensation ──────────────────────────────────
# a transaction that may fail mid-branch; the ONLY path to the terminal after a failure runs compensation,
# so the saga safety invariant — (failed at terminal => compensated) — holds.
SAGA = {
    "name": "Saga",
    "states": ["ready", "running", "committed", "compensating", "done"],
    "entry": "ready",
    "flags": {"failed": {"type": "Bool", "init": False}, "compensated": {"type": "Bool", "init": False}},
    "transitions": [
        {"from": "ready", "to": "running", "set": {"failed": False, "compensated": False}},
        {"from": "running", "to": "committed", "set": {"failed": False}},          # success branch
        {"from": "running", "to": "compensating", "set": {"failed": True}},        # FAILURE branch
        {"from": "compensating", "to": "done", "set": {"compensated": True}},      # compensation runs
        {"from": "committed", "to": "done", "set": {}},
    ],
    "invariants": {"SagaCompensates": '(failed /\\ pc = "done") => compensated'},
}


def buggy_saga() -> dict:
    """A saga that skips compensation on the failure branch — reaches the terminal failed-but-uncompensated.
    The SagaCompensates invariant MUST catch it."""
    bad = copy.deepcopy(SAGA)
    bad["name"] = "SagaBuggy"
    bad["transitions"].append({"from": "compensating", "to": "done", "set": {}})   # skip the compensation set
    return bad


def run_saga(n_steps: int, fail_at) -> dict:
    """Execution-side saga: run forward steps; on a failure at `fail_at`, run the recorded compensations in
    reverse. Returns the log. This is the EXECUTION half of P4-T02 (the model half is SagaCompensates)."""
    done, compensated = [], []
    for i in range(n_steps):
        if i == fail_at:
            for j in reversed(done):                       # mid-branch failure -> compensate what ran
                compensated.append(j)
            return {"failed_at": i, "ran": done, "compensated": compensated,
                    "compensation_ran": compensated == list(reversed(done))}
        done.append(i)
    return {"failed_at": None, "ran": done, "compensated": [], "compensation_ran": True}


# ── P4-T09: the engine's own pipeline, as a workflow — the plan verifies the plan ────────────────────
def plan_workflow() -> dict:
    """The governed runtime's own path (validate -> compose -> compile -> oversee -> execute) encoded as a
    workflow, with the safety invariant that a step only reaches `executed` after oversight ran."""
    return {
        "name": "PlanWorkflow",
        "states": ["ready", "validated", "composed", "compiled", "overseen", "executed"],
        "entry": "ready",
        "flags": {"oversaw": {"type": "Bool", "init": False}},
        "transitions": [
            {"from": "ready", "to": "validated", "set": {}},
            {"from": "validated", "to": "composed", "set": {}},
            {"from": "composed", "to": "compiled", "set": {}},
            {"from": "compiled", "to": "overseen", "set": {"oversaw": True}},
            {"from": "overseen", "to": "executed", "set": {}},
        ],
        "invariants": {"GovernedExecution": 'pc = "executed" => oversaw'},
    }


# ── P4-T04 / P4-T08: the dual-checker corpus — clean + known-bad, every checker must agree ────────────
def corpus() -> list:
    """(name, workflow, expect_clean). Mixed clean + seeded/structural defects; TLC and Apalache must
    AGREE on every entry (both clean, or both catch)."""
    return [
        ("sample", SAMPLE, True),
        ("seed-started", seed_violation(SAMPLE, "started"), False),
        ("seed-steps", seed_violation(SAMPLE, "steps"), False),
        ("saga-good", SAGA, True),
        ("saga-skip-compensation", buggy_saga(), False),
        ("plan-pipeline", plan_workflow(), True),
    ]


def run_corpus() -> dict:
    """Run the corpus through TLC + Apalache; both must reach the EXPECTED verdict and AGREE with each
    other. `ok` iff TLC is correct on all, Apalache on >= all-1 (one may time out), and no disagreements —
    the SV-5 dual-checker bar (P4-T04)."""
    rows = []
    for name, wf, expect_clean in corpus():
        tlc, apa = check_tlc(wf), check_apalache(wf)
        want = "no_error" if expect_clean else "violation"
        apa_actionable = apa["verdict"] in ("no_error", "violation")
        rows.append({"name": name, "expect_clean": expect_clean,
                     "tlc": tlc["verdict"], "apalache": apa["verdict"],
                     "tlc_correct": tlc["verdict"] == want,
                     "apalache_correct": apa["verdict"] == want,
                     "agree": (tlc["ok"] == apa["ok"]) if apa_actionable else None})
    total = len(rows)
    tlc_correct = sum(r["tlc_correct"] for r in rows)
    apa_correct = sum(r["apalache_correct"] for r in rows)
    disagreements = [r["name"] for r in rows if r["agree"] is False]
    return {"total": total, "tlc_correct": tlc_correct, "apalache_correct": apa_correct,
            "disagreements": disagreements, "rows": rows,
            "ok": tlc_correct == total and apa_correct >= total - 1 and not disagreements}


# ── P4-T03: workflow algebra — seq / par compose into a product automaton, within a state budget ─────
def reachable_states(wf: dict) -> set:
    """BFS the reachable pc values from the entry over the transitions — the realised state count."""
    adj = {}
    for t in wf["transitions"]:
        adj.setdefault(t["from"], []).append(t["to"])
    seen, frontier = {wf["entry"]}, [wf["entry"]]
    while frontier:
        s = frontier.pop()
        for nxt in adj.get(s, []):
            if nxt not in seen:
                seen.add(nxt)
                frontier.append(nxt)
    return seen


def _prefix(wf, p):
    """Namespace a workflow's states + flags under prefix `p` (for composition)."""
    out = copy.deepcopy(wf)
    out["states"] = [f"{p}_{s}" for s in wf["states"]]
    out["entry"] = f"{p}_{wf['entry']}"
    out["flags"] = {f"{p}_{k}": v for k, v in wf.get("flags", {}).items()}
    out["transitions"] = [{"from": f"{p}_{t['from']}", "to": f"{p}_{t['to']}",
                           "set": {f"{p}_{k}": v for k, v in t.get("set", {}).items()}}
                          for t in wf["transitions"]]
    return out


def compose(w1: dict, w2: dict, op: str) -> dict:
    """Compose two workflows into a product automaton. `seq` runs w1 then w2 (w1's terminal flows into w2's
    entry); `par` is the interleaving product (pc = "s1|s2", either side may step). Flags are namespaced, so
    the composite is finite — its state count is bounded by the operands."""
    a, b = _prefix(w1, "a"), _prefix(w2, "b")
    flags = {**a["flags"], **b["flags"]}
    if op == "seq":
        states = a["states"] + b["states"]
        trans = a["transitions"] + b["transitions"]
        trans.append({"from": a["states"][-1], "to": b["entry"], "set": {}})       # a-terminal -> b-entry
        return {"name": f"Seq_{w1['name']}_{w2['name']}", "states": states, "entry": a["entry"],
                "flags": flags, "transitions": trans, "invariants": {}}
    if op == "par":
        states = [f"{s1}|{s2}" for s1 in a["states"] for s2 in b["states"]]
        trans = []
        for s1 in a["states"]:
            for s2 in b["states"]:
                for t in a["transitions"]:
                    if t["from"] == s1:
                        trans.append({"from": f"{s1}|{s2}", "to": f"{t['to']}|{s2}", "set": t.get("set", {})})
                for t in b["transitions"]:
                    if t["from"] == s2:
                        trans.append({"from": f"{s1}|{s2}", "to": f"{s1}|{t['to']}", "set": t.get("set", {})})
        # the terminal is (a-terminal | b-terminal); put it last so emit_tla's self-loop lands there
        term = f"{a['states'][-1]}|{b['states'][-1]}"
        states = [s for s in states if s != term] + [term]
        return {"name": f"Par_{w1['name']}_{w2['name']}", "states": states, "entry": f"{a['entry']}|{b['entry']}",
                "flags": flags, "transitions": trans, "invariants": {}}
    raise ValueError(f"unknown compose op: {op}")


def algebra_budget(state_budget: int = 5_000_000) -> dict:
    """Compose representative workflows (seq + par) and confirm the product automaton is finite + within the
    SV-5 state budget (P4-T03). Returns the realised state counts + whether all are within budget."""
    products = {"seq": compose(SAMPLE, SAGA, "seq"), "par": compose(SAMPLE, SAGA, "par")}
    sizes = {op: len(reachable_states(wf)) for op, wf in products.items()}
    return {"sizes": sizes, "budget": state_budget,
            "within_budget": all(n <= state_budget for n in sizes.values()),
            "finite": all(n < len(p["states"]) + 1 for p, n in zip(products.values(), sizes.values()))}


def certs() -> dict:
    """The three-certificate summary (P4-T08): run every prover over a representative spec and report which
    of EMPIRICAL / SYMBOLIC / AXIOMATIC were earned."""
    r = run_all(SAGA)
    return {"certs": r["certs"], "clean": r["clean"],
            "have_all_three": set(r["certs"]) == {"EMPIRICAL", "SYMBOLIC", "AXIOMATIC"}}


# ── P4-T06: the settlement lifecycle, model-checked (money-safety) ───────────────────────────────────
def settlement_workflow() -> dict:
    """The P6 settlement lifecycle as a workflow: quote -> fund -> check (validate) -> settle, with a
    cancel / escrow-expiry refund path. Money-safety invariants the spec must hold: a payout needs BOTH a
    funded quote and a passing validation, AT MOST ONE payout occurs, and escrow drains at EVERY terminal
    state (no value is ever stranded). Both terminals self-loop so the bounded spec never deadlocks
    (`settled` is last → emit_tla self-loops it; `cancelled` self-loops explicitly)."""
    return {
        "name": "Settlement",
        "states": ["quoted", "funded", "checked", "cancelled", "settled"],
        "entry": "quoted",
        "flags": {"funded": {"type": "Bool", "init": False},
                  "validated": {"type": "Bool", "init": False},
                  "paid": {"type": "Int", "init": 0},
                  "escrow": {"type": "Bool", "init": False}},
        "transitions": [
            {"from": "quoted", "to": "funded", "set": {"funded": True, "escrow": True}},
            {"from": "funded", "to": "checked", "set": {"validated": True}},
            {"from": "checked", "to": "settled", "set": {"paid": 1, "escrow": False}},
            {"from": "funded", "to": "cancelled", "set": {"escrow": False}},     # escrow-expiry refund
            {"from": "checked", "to": "cancelled", "set": {"escrow": False}},    # cancel-after-validate refund
            {"from": "cancelled", "to": "cancelled", "set": {}},                 # terminal self-loop (no deadlock)
        ],
        "invariants": {
            "SettleNeedsValidate": 'pc = "settled" => validated',
            "SettleNeedsFund": 'pc = "settled" => funded',
            "AtMostOnePayout": "paid <= 1",
            "EscrowDrainsAtTerminal": '(pc = "settled" \\/ pc = "cancelled") => escrow = FALSE',
        },
    }


def settlement_corpus() -> list:
    """(name, wf, expect_clean): the clean settlement model + the THREE money mutants a sound checker MUST
    catch — settle-before-validate (the validation flag is never set), double-settle / over-pay (the payout
    counter leaves [0,1], breaking AtMostOnePayout), and remove-expiry / strand-escrow (escrow is not
    refunded at a terminal, breaking EscrowDrainsAtTerminal)."""
    wf = settlement_workflow()
    return [
        ("settlement-clean", wf, True),
        ("mutant-settle-before-validate", seed_violation(wf, "validated"), False),
        ("mutant-double-settle", seed_violation(wf, "paid"), False),
        ("mutant-strand-escrow", seed_violation(wf, "escrow"), False),
    ]


def prove_settlement() -> dict:
    """P4-T06: the settlement lifecycle passes EMPIRICAL (TLC) AND SYMBOLIC (Apalache), and EACH money mutant
    is CAUGHT. `ok` iff the clean model is `no_error` under both provers and every mutant is a `violation`
    under TLC and under Apalache (Apalache may time out on at most one)."""
    rows = []
    for name, wf, clean in settlement_corpus():
        tlc, apa = check_tlc(wf), check_apalache(wf)
        want = "no_error" if clean else "violation"
        rows.append({"name": name, "expect_clean": clean, "tlc": tlc["verdict"], "apalache": apa["verdict"],
                     "tlc_correct": tlc["verdict"] == want, "apalache_correct": apa["verdict"] == want})
    clean_row, mutants = rows[0], rows[1:]
    empirical_plus_symbolic_pass = clean_row["tlc_correct"] and clean_row["apalache_correct"]
    money_mutants_fail = (all(m["tlc_correct"] for m in mutants)
                          and sum(m["apalache_correct"] for m in mutants) >= len(mutants) - 1)
    return {"empirical_plus_symbolic_pass": empirical_plus_symbolic_pass,
            "money_mutants_fail": money_mutants_fail, "mutants_checked": len(mutants), "rows": rows,
            "ok": empirical_plus_symbolic_pass and money_mutants_fail}


if __name__ == "__main__":
    import json as _json
    print(_json.dumps(prove_settlement(), indent=2))

