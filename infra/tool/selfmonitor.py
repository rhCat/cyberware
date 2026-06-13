#!/usr/bin/env python3
"""selfmonitor.py — the standing self-monitor: cyberware grades its own engine and enforces policy.

This is "building is running" made into a gate (plan meta-rule M5). Three checks, all redeemable
evidence rather than assertions, produced by the chip's own validator skills + engine tooling:

  1. blueprints  — every chip blueprint AND the engine's own pipeline blueprint is deadlock-free
                   (composer.structural: no non-terminal sink, all states reachable, a terminal reachable).
  2. authenticity — every skill + the chip manifest matches its committed hash (skill_index --check).
  3. mutation ratchet — cws-mutate over each enforcement-surface gate module vs a recorded floor
                   (infra/govern/selfmonitor_policy.json). The R3 target is 0.90; the floor is the current
                   measured coverage and may only RISE, so the gate protects the very tests that earn it.

  python3 -m infra.tool.selfmonitor                 # all checks (the CI self-monitor gate)
  python3 -m infra.tool.selfmonitor --no-mutation   # fast checks only (blueprints + authenticity)
"""
from __future__ import annotations
import argparse
import json
import os
import subprocess
import sys
import tempfile

from infra import registry
from infra.govern import composer
from infra.tool import skill_index as si

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
POLICY = os.path.join(ROOT, "infra", "govern", "selfmonitor_policy.json")
MUTATE_CORE = os.path.join(registry.SKILLCHIP, "cws-mutate", "perks", "mutate", "src", "cws_mutate.py")


def check_blueprints():
    """(count, bad): every chip blueprint + the engine's pipeline blueprint must be deadlock-free."""
    targets = [(s, os.path.join(si.SKILLS, s, "blueprint.json")) for s in si.all_skills()]
    pipe = os.path.join(ROOT, "infra", "document", "pipeline.blueprint.json")
    if os.path.isfile(pipe):
        targets.append(("<engine pipeline>", pipe))
    bad = [(name, composer.structural(json.load(open(p)))) for name, p in targets]
    return len(targets), [(n, iss) for n, iss in bad if iss]


def check_authenticity():
    r = subprocess.run([sys.executable, "-m", "infra.tool.skill_index", "--check"],
                       cwd=ROOT, capture_output=True, text=True)
    tail = (r.stdout.strip().splitlines() or [""])[-1]
    return r.returncode == 0, tail


def mutation_score(module, slice_, cap):
    """Drive the chip's cws-mutate core over `module` with `slice_` as the test; return its report dict."""
    rs = tempfile.mkdtemp(prefix="selfmon-mut-")
    env = {**os.environ, "PROJECT_DIR": ROOT, "TARGET": module,
           "TEST_CMD": f"python3 -m pytest {slice_} -q", "MAX_MUTANTS": str(cap), "THRESHOLD": "0",
           "RECORD_STORE": rs}
    subprocess.run([sys.executable, MUTATE_CORE], env=env, capture_output=True, text=True)
    rep = os.path.join(rs, "mutate.json")
    return json.load(open(rep)) if os.path.isfile(rep) else None


def check_mutation():
    """(rows, failures): each enforcement-surface module's score vs its ratchet floor."""
    policy = json.load(open(POLICY))
    rows, fail = [], []
    for e in policy["enforcement_surface"]:
        rep = mutation_score(e["module"], e["slice"], e.get("cap", 50))
        score = (rep or {}).get("mutation_score", 0.0)
        ok = rep is not None and score >= e["floor"]
        rows.append({"module": e["module"], "score": score, "floor": e["floor"],
                     "target": e.get("target", 0.90), "ok": ok, "survived": (rep or {}).get("survived", [])})
        if not ok:
            fail.append((e["module"], score, e["floor"]))
    return rows, fail


def main():
    ap = argparse.ArgumentParser(description="cyberware self-monitor — grade the engine, enforce policy")
    ap.add_argument("--no-mutation", action="store_true", help="skip the (slow) mutation ratchet")
    a = ap.parse_args()
    failed = False

    n, bad = check_blueprints()
    if bad:
        failed = True
        print(f"[FAIL] blueprints — {len(bad)} with deadlock/unreachable:")
        for name, issues in bad:
            print(f"         {name}: {issues}")
    else:
        print(f"[ ok ] blueprints — all {n} deadlock-free (chip + engine pipeline)")

    aok, adetail = check_authenticity()
    print(f"[ {'ok' if aok else 'FAIL'} ] authenticity — {adetail}")
    failed = failed or not aok

    if not a.no_mutation:
        rows, mfail = check_mutation()
        print("[ .. ] enforcement-surface mutation ratchet (R3 target 0.90):")
        for r in rows:
            print(f"         [{'ok' if r['ok'] else 'FAIL'}] {r['module']}: "
                  f"score={r['score']} floor={r['floor']} target={r['target']}"
                  + (f"  survivors={r['survived']}" if r["survived"] else ""))
        if mfail:
            failed = True
            print(f"       MUTATION REGRESSION below floor: {mfail}")

    print("selfmonitor: " + ("FAILED" if failed else "PASS — the engine grades clean"))
    sys.exit(1 if failed else 0)


if __name__ == "__main__":
    main()
