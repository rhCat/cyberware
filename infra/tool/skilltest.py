#!/usr/bin/env python3
"""skilltest.py — run a skill's OWN, in-skill test through the governed channel.

A skill proves itself: each perk carries `perks/<perk>/test/case.json` (input vars + an optional
`fixture/` dir + a `setup` to build fixtures + declared `expect`ations). This runner builds a hermetic
work dir, compiles the perk and runs it through `executor.py` (the SAME governed pipeline the agent
uses — oversight scan, contract check, run-ledger), then checks the declared expectations. The test is
DATA pinned in the skill's index, not prose — so the proof can't drift from the skill.

  case.json:
    { "vars": {"K":"v", "DIR":"${FIXTURE}"},   # ${FIXTURE} = the fixture dir, ${RECORD} = the run dir
      "requires": ["sqlite3"],                 # skip the test if any of these binaries is absent
      "skip": "needs a live Postgres",         # OR: always skip (a perk that can't run hermetically)
      "setup": ["sqlite3 demo.db 'CREATE …'"], # optional shell lines, run with cwd = the fixture dir
      "approve": ["rm_rf"],                    # optional: --approve <rule_id> passed to the executor
      "expect": {
        "exit": 0,                             # executor exit (default 0)
        "outputs": ["query_result.txt"],       # files that must EXIST (RECORD-relative, or ${FIXTURE}/${VAR})
        "nonempty": ["archive.tar.gz"],         # files that must exist AND be non-empty
        "contains": {"query_result.txt": "2"}, # path -> substring (or list of substrings)
        "json": {"report.json": {"status":"ok"}} # path -> subset that must be present in the JSON
      } }

  python3 -m infra.tool.skilltest --skill sqlite --perk query     # one perk
  python3 -m infra.tool.skilltest --all                           # every perk that ships a test
"""
from __future__ import annotations
import argparse, json, os, shutil, subprocess, sys, tempfile
from infra import registry
from infra.tool import skill_index

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
SKILLS = os.path.join(registry.SKILLCHIP)


def case_path(skill, perk):
    return os.path.join(registry.skill_dir(skill), "perks", perk, "test", "case.json")


def has_test(skill, perk):
    return os.path.isfile(case_path(skill, perk))


def _resolve(val, env):
    if isinstance(val, str):
        for k, v in env.items():
            val = val.replace("${" + k + "}", v)
    return val


def _subset(want, got):
    """True if `want` is recursively contained in `got` (dict keys/values, exact for scalars)."""
    if isinstance(want, dict):
        return isinstance(got, dict) and all(k in got and _subset(v, got[k]) for k, v in want.items())
    if isinstance(want, list):
        return isinstance(got, list) and len(got) >= len(want) and all(_subset(w, g) for w, g in zip(want, got))
    return want == got


def run(skill, perk, root=ROOT):
    """Returns (status, detail): status in {'pass','fail','skip'}; detail is the reason on skip/fail."""
    case = json.load(open(case_path(skill, perk)))
    if case.get("skip"):                         # a perk that can't run hermetically (live service / network)
        return "skip", str(case["skip"])         #   still ships a case (documents fixture + expectation)
    missing = [b for b in case.get("requires", []) if shutil.which(b) is None]
    if missing:
        return "skip", f"requires absent: {', '.join(missing)}"
    for cmd in case.get("requires_cmd", []):                  # capability probes (e.g. openssl ed25519ph):
        if subprocess.run(cmd, shell=True, capture_output=True).returncode != 0:  # skip (not fail) when the
            return "skip", f"capability probe failed: {cmd}"  #   toolchain present can't do what the perk needs

    work = tempfile.mkdtemp(prefix=f"cwtest-{skill.replace(':', '_')}-{perk}-")  # ':' is unsafe in a path segment
    try:
        fixture = os.path.join(work, "fixture")
        os.makedirs(fixture, exist_ok=True)
        src_fix = os.path.join(registry.skill_dir(skill), "perks", perk, "test", "fixture")
        if os.path.isdir(src_fix):
            shutil.copytree(src_fix, fixture, dirs_exist_ok=True)
        record = os.path.join(work, "out")
        env = {"FIXTURE": fixture, "RECORD": record}

        for cmd in case.get("setup", []):
            s = subprocess.run(_resolve(cmd, env), shell=True, cwd=fixture, capture_output=True, text=True)
            if s.returncode != 0:
                return "fail", f"setup failed: {cmd}\n{s.stderr}"

        vars_ = {k: _resolve(v, env) for k, v in case.get("vars", {}).items()}
        ledger = {"skill": skill, "perk": perk, "record_store": record, "vars": vars_}
        lp = os.path.join(work, "ledger.json")
        open(lp, "w").write(json.dumps(ledger))

        c = subprocess.run([sys.executable, "-m", "infra.govern.compiler", "--ledger", lp],
                           cwd=root, capture_output=True, text=True)
        if c.returncode != 0:
            return "fail", f"compile failed:\n{c.stdout}{c.stderr}"
        run_sh = os.path.join(record, "run.sh")
        approve = [x for a in case.get("approve", []) for x in ("--approve", a)]
        x = subprocess.run([sys.executable, "-m", "infra.govern.executor", "--script", run_sh, "--all", *approve],
                           cwd=root, capture_output=True, text=True)

        exp = case.get("expect", {})
        env = {"FIXTURE": fixture, "RECORD": record, **vars_}   # so ${VAR} in expect paths resolves (deliverables)
        fails = []
        if x.returncode != exp.get("exit", 0):
            fails.append(f"exit {x.returncode} != {exp.get('exit', 0)}\n{x.stdout}{x.stderr}")
        for rel in exp.get("outputs", []):          # must EXIST (a silent-success tool may write an empty file)
            if not os.path.isfile(_abspath(rel, record, env)):
                fails.append(f"missing output: {rel}")
        for rel in exp.get("nonempty", []):          # must exist AND be non-empty (e.g. an archive)
            p = _abspath(rel, record, env)
            if not os.path.isfile(p):
                fails.append(f"missing output: {rel}")
            elif os.path.getsize(p) == 0:
                fails.append(f"empty output: {rel}")
        for rel, subs in exp.get("contains", {}).items():
            p = _abspath(rel, record, env)
            body = open(p).read() if os.path.isfile(p) else ""
            for sub in ([subs] if isinstance(subs, str) else subs):
                if sub not in body:
                    fails.append(f"{rel} does not contain {sub!r}")
        for rel, want in exp.get("json", {}).items():
            p = _abspath(rel, record, env)
            try:
                got = json.load(open(p))
            except Exception as e:
                fails.append(f"{rel} not valid JSON: {e}"); continue
            if not _subset(want, got):
                fails.append(f"{rel} JSON missing subset {want}")
        return ("fail", "; ".join(fails)) if fails else ("pass", "")
    finally:
        shutil.rmtree(work, ignore_errors=True)


def _abspath(rel, record, env):
    r = _resolve(rel, env)
    return r if os.path.isabs(r) else os.path.join(record, r)


def all_cases():
    out = []
    for sk in skill_index.all_skills(SKILLS):            # manifest-authoritative: only PERMITTED skills, no dir scan
        pj = os.path.join(registry.skill_dir(sk), "perks.json")
        if not os.path.isfile(pj):
            continue
        for p in json.load(open(pj)).get("perks", []):
            if has_test(sk, p["id"]):
                out.append((sk, p["id"]))
    return out


def main():
    ap = argparse.ArgumentParser(description="run a skill's in-skill test through the governed channel")
    ap.add_argument("--skill")
    ap.add_argument("--perk")
    ap.add_argument("--all", action="store_true")
    a = ap.parse_args()
    if a.all:
        cases = all_cases()
    elif a.skill and not a.perk:                              # --skill X alone -> every perk of X
        cases = [(sk, pk) for sk, pk in all_cases() if sk == a.skill]
    else:
        cases = [(a.skill, a.perk)]
    bad = 0
    for sk, pk in cases:
        if not has_test(sk, pk):
            print(f"  [no-test] {sk}/{pk}"); continue
        status, detail = run(sk, pk)
        mark = {"pass": "ok", "skip": "skip", "fail": "FAIL"}[status]
        print(f"  [{mark}] {sk}/{pk}" + (f" — {detail}" if detail else ""))
        bad += status == "fail"
    print(f"skilltest: {'all passed' if not bad else f'{bad} failed'}")
    sys.exit(1 if bad else 0)


if __name__ == "__main__":
    main()
