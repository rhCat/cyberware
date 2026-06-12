#!/usr/bin/env python3
"""composer.py — compose the L++ blueprint (blueprint + ledger) and check it for abstract deadlock.

Emits the skill's state machine as TLA+ and runs TLC, which checks for deadlock by default — a
non-terminal state with no enabled transition is a logical dead-end. Terminal states get a self-loop
so they are not flagged. A pure-Python structural check (non-terminal sinks, reachability from entry,
a reachable terminal) always runs, so the check is meaningful even without a JRE / tla2tools
(`TLA2TOOLS_JAR`). Read-only.

  composer.py --ledger task-ledger.json [--tla-out task.tla]
"""
from __future__ import annotations
import argparse, json, os, shutil, subprocess, sys, tempfile

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def load(p): return json.load(open(p))


def adjacency(bp):
    adj = {}
    for t in bp["transitions"]:
        adj.setdefault(t["from"], []).append(t["to"])
    return adj


def structural(bp):
    states, terms, adj = list(bp["states"]), set(bp.get("terminal_states", {})), adjacency(bp)
    issues = []
    for s in states:
        if s not in terms and not adj.get(s):
            issues.append(f"deadlock: non-terminal state '{s}' has no outgoing transition")
    seen, stack = set(), [bp["entry_state"]]
    while stack:
        s = stack.pop()
        if s in seen:
            continue
        seen.add(s)
        stack += adj.get(s, [])
    for s in states:
        if s not in seen:
            issues.append(f"unreachable: '{s}' not reachable from entry")
    if not (seen & terms):
        issues.append("no terminal state reachable from entry")
    return issues


def emit_tla(bp, name="task"):
    states, terms, adj = list(bp["states"]), set(bp.get("terminal_states", {})), adjacency(bp)
    disj = []
    for s in states:
        if s in terms:
            disj.append(f'(pc = "{s}" /\\ pc\' = "{s}")')        # terminal self-loop — not a deadlock
        for to in adj.get(s, []):
            disj.append(f'(pc = "{s}" /\\ pc\' = "{to}")')
    body = [
        f"---- MODULE {name} ----", "VARIABLE pc", "",
        f'Init == pc = "{bp["entry_state"]}"',
        "Next ==\n  \\/ " + "\n  \\/ ".join(disj),
        "Spec == Init /\\ [][Next]_pc", "===="]
    return "\n".join(body) + "\n"


def run_tlc(tla, name):
    jar = os.environ.get("TLA2TOOLS_JAR")
    if not jar or not os.path.isfile(jar) or not shutil.which("java"):
        return None, "TLC skipped (set TLA2TOOLS_JAR + java for the abstract check)"
    d = tempfile.mkdtemp(prefix="cyberware-tlc-")
    open(os.path.join(d, f"{name}.tla"), "w").write(tla)
    open(os.path.join(d, f"{name}.cfg"), "w").write("SPECIFICATION Spec\n")
    try:
        r = subprocess.run(["java", "-cp", jar, "tlc2.TLC", f"{name}.tla"],
                           cwd=d, capture_output=True, text=True, timeout=120)
        out = r.stdout + r.stderr
        ok = "No error has been found" in out   # TLC's success line; deadlock/violation prints an Error: instead
        return ok, ("no deadlock (TLC)" if ok else "TLC found a deadlock / error")
    except Exception as e:
        return None, f"TLC error: {e}"


def main():
    ap = argparse.ArgumentParser(description="compose the blueprint + TLC deadlock check")
    ap.add_argument("--ledger", required=True)
    ap.add_argument("--tla-out", default=None)
    a = ap.parse_args()
    L = load(a.ledger)
    bp = load(os.path.join(ROOT, "skills", L["skill"], "blueprint.json"))
    print(f"composer · skill={L['skill']} perk={L['perk']}  ({len(bp['states'])} states, {len(bp['transitions'])} transitions)")

    issues = structural(bp)
    for i in issues:
        print(f"  [STRUCT] {i}")
    if not issues:
        print("  [struct] no non-terminal sinks · all states reachable · terminal reachable")

    tla = emit_tla(bp)
    if a.tla_out:
        open(a.tla_out, "w").write(tla)
    ok, msg = run_tlc(tla, "task")
    print(f"  [tlc] {msg}")

    bad = bool(issues) or ok is False
    print(f"composer: {'DEADLOCK/ISSUE' if bad else 'OK — no logical deadlock'}")
    sys.exit(1 if bad else 0)


if __name__ == "__main__":
    main()
