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
import concurrent.futures
import json
import os
import re
import subprocess
import sys
import tempfile

from infra import registry
from infra.govern import composer
from infra.tool import skill_index as si

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
POLICY = os.path.join(ROOT, "infra", "govern", "selfmonitor_policy.json")
MUTATE_CORE = os.path.join(registry.skill_dir("cws-mutate"), "perks", "mutate", "src", "cws_mutate.py")


def check_blueprints():
    """(count, bad): every chip blueprint + the engine's pipeline blueprint must be deadlock-free."""
    targets = [(s, os.path.join(registry.skill_dir(s), "blueprint.json")) for s in si.all_skills()]
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


def check_no_stubs():
    """(ok, offenders): no PERMITTED skill ships scaffold-default placeholder metadata — a blueprint
    description still reading 'TODO describe what this skill does', or a perks.json summary literally 'TODO'.
    These slip in from `scaffold.py` and contradict the real SKILL.md; this gate is the root-cause guard so
    they can't recur. (Scans the data files only — `cws-addperk`'s own scaffold-template code is not a skill
    blueprint, so its intentional TODO markers are not flagged.)"""
    offenders = []
    for s in si.all_skills():
        bp = os.path.join(registry.skill_dir(s), "blueprint.json")
        if os.path.isfile(bp) and "TODO describe what this skill does" in json.load(open(bp)).get("description", ""):
            offenders.append(f"{s}/blueprint.json: placeholder description")
        pj = os.path.join(registry.skill_dir(s), "perks.json")
        if os.path.isfile(pj):
            for p in (json.load(open(pj)) or {}).get("perks", []):
                if (p.get("summary") or "").strip() == "TODO":
                    offenders.append(f"{s}/perks.json: perk '{p.get('id')}' summary is TODO")
    return not offenders, offenders


# A porter sits at <skill>/perks/<perk>/src/. Reaching its OWN skill root is `../../..` (3 up) — stable, the
# skill's internal shape never changes. Reaching 4+ levels ESCAPES the skill (to the chip / a source group /
# the repo), and doing that by COUNTING `..` is what the source-subfolder migration silently broke. The seam
# is: CYBERWARE_ROOT / CYBERWARE_SKILLCHIP, an upward marker-search, or registry.skill_dir — never depth.
_FRAGILE_PARENT = re.compile(r"\.\.(?:/\.\.){3,}")                      # raw  ../../../..  (>= 4 `..` SEGMENTS)
_FRAGILE_PARENT_PY = re.compile(r"""(?:["']\.\.["']\s*,\s*){3,}["']\.\.["']""")  # os.path.join(..,"..","..","..","..")
_HARDCODED_CHIP = re.compile(r"skillChip/\S")                           # a literal path INTO the chip


def check_porter_path_hygiene():
    """(ok, offenders): no porter may reach the repo/chip root by a FIXED-DEPTH `..` walk (>=4 levels escapes
    its own skill) or HARDCODE a `skillChip/<...>` path. A skill must be RELOCATABLE — the cartridge model's
    promise (swap / move / compile skills freely) only holds if no skill assumes where it sits. This is the
    root-cause guard for the cws/<skill> source-subfolder migration's regression: the added directory level
    shifted every porter's depth by one and silently broke the fixed-depth walkers. Scans porter source only
    (perks/*/src, .py + .sh), skipping test fixtures."""
    offenders = []
    for s in si.all_skills():
        for dp, dirs, files in os.walk(os.path.join(registry.skill_dir(s), "perks")):
            dirs[:] = [d for d in dirs if d not in ("__pycache__", "test")]
            if "src" not in dp.split(os.sep):
                continue
            for f in files:
                if not f.endswith((".py", ".sh")):
                    continue
                ap = os.path.join(dp, f)
                rel = os.path.relpath(ap, registry.SKILLCHIP)
                for i, line in enumerate(open(ap, encoding="utf-8", errors="ignore").read().splitlines(), 1):
                    if _FRAGILE_PARENT.search(line) or _FRAGILE_PARENT_PY.search(line):
                        offenders.append(f"{rel}:{i}: fixed-depth `..` walk — resolve the root via a marker-search / CYBERWARE_ROOT")
                    if _HARDCODED_CHIP.search(line):
                        offenders.append(f"{rel}:{i}: hardcoded skillChip/ path — use registry.skill_dir")
    return not offenders, offenders


def mutation_score(module, slice_, cap):
    """Drive the chip's cws-mutate core over `module` with `slice_` as the test; return its report dict."""
    rs = tempfile.mkdtemp(prefix="selfmon-mut-")
    # -x stops at the first failing test (a mutant is killed the moment ONE test fails — no need to run the
    # rest of the slice); -p no:cacheprovider skips the unused .pytest_cache. Both leave the score identical,
    # they just make each of the ~90 per-mutant runs return as soon as the verdict is known.
    env = {**os.environ, "PROJECT_DIR": ROOT, "TARGET": module,
           "TEST_CMD": f"python3 -m pytest {slice_} -q -x -p no:cacheprovider", "MAX_MUTANTS": str(cap),
           "THRESHOLD": "0", "RECORD_STORE": rs}
    subprocess.run([sys.executable, MUTATE_CORE], env=env, capture_output=True, text=True)
    rep = os.path.join(rs, "mutate.json")
    return json.load(open(rep)) if os.path.isfile(rep) else None


def check_mutation():
    """(rows, failures): each enforcement-surface module's score vs its ratchet floor.

    The modules are independent — each mutation campaign runs in its own sandbox + record store — so they
    run CONCURRENTLY (wall-clock = the slowest module, not the sum). subprocess work releases the GIL, so a
    thread pool suffices; results are collected in policy order so the report is deterministic."""
    policy = json.load(open(POLICY))
    surface = policy["enforcement_surface"]
    with concurrent.futures.ThreadPoolExecutor(max_workers=max(1, len(surface))) as ex:
        reps = list(ex.map(lambda e: mutation_score(e["module"], e["slice"], e.get("cap", 50)), surface))
    rows, fail = [], []
    for e, rep in zip(surface, reps):
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

    sok, stubs = check_no_stubs()
    print(f"[ {'ok' if sok else 'FAIL'} ] no scaffold stubs — "
          + ("none" if sok else f"{len(stubs)} placeholder(s): {stubs[:5]}"))
    failed = failed or not sok

    pok, frag = check_porter_path_hygiene()
    print(f"[ {'ok' if pok else 'FAIL'} ] porter path hygiene — "
          + ("no fixed-depth `..` walks / hardcoded chip paths" if pok else f"{len(frag)} fragile: {frag[:5]}"))
    failed = failed or not pok

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
