#!/usr/bin/env python3
"""scaffold.py — generate a new skill skeleton in the registry.

Creates `skills/<id>/` with the standard perk-agnostic L++ lifecycle blueprint, `perks.json`,
`ledger.json`, `SKILL.md`, and per perk a `metadata.json` / `manifesto.json` / `src/contracts.json`
plus a snippet STUB (the structured-JSON output pattern + a TODO). The skeleton already validates +
composes out of the box; you fill in each perk's vars and the proven-pathway snippet.

  scaffold.py --skill myskill --name "My Skill" [--desc "..."] \
      --perk fetch:my_fetch:curl --perk store:my_store:python3
  # --perk  <perk_id>:<tool>[:<binary>]   (binary defaults to <tool>)
"""
from __future__ import annotations
import argparse, json, os, stat, sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def wj(p, o):
    os.makedirs(os.path.dirname(p), exist_ok=True)
    open(p, "w").write(json.dumps(o, indent=2) + "\n")


def wsh(p, t):
    os.makedirs(os.path.dirname(p), exist_ok=True)
    open(p, "w").write(t)
    os.chmod(p, os.stat(p).st_mode | stat.S_IEXEC | stat.S_IXGRP | stat.S_IXOTH)


def blueprint(sid, name, desc):
    """The standard perk-agnostic lifecycle every tool skill shares."""
    return {
        "$schema": "lpp/v0.2.0", "id": sid, "name": name,
        "description": desc + " Perk-agnostic lifecycle (ready → prepared → verified → executed); the perk supplies the concrete, contract-bound how. LOOK OUT FOR each tool's structured JSON; LOGS TO CHECK: the per-tool output + the executor run-ledger.",
        "entry_state": "ready",
        "states": {
            "ready":    {"description": "task-ledger submitted, nothing run"},
            "prepared": {"description": "inputs validated — required vars present, runtime + store reachable"},
            "verified": {"description": "the plan is contract-bound — the perk's tool sequence resolves and its contract (I/O + checks) is in place"},
            "executed": {"description": "the perk's tool sequence ran ONLY via executor.py — each step is recorded to the run-ledger AS it runs (recording is part of execution, not a step after)"},
        },
        "terminal_states": {"executed": {}},
        "gates": {
            "g_prepared": {"type": "expression", "expression": "inputs_present /\\ store_writable", "description": "inputs + store validated"},
            "g_verified": {"type": "expression", "expression": "sequence_resolved /\\ contracts_present", "description": "the task is contract-bound"},
            "g_governed": {"type": "expression", "expression": "governed_run /\\ contract_checks_pass", "description": "ran ONLY through executor.py; contract enforced"},
        },
        "actions": {
            "a_prepare": {"type": "compute", "compute_unit": "validator:check_inputs", "description": "validator confirms required vars + writable record_store + reachable runtime"},
            "a_verify":  {"type": "compute", "compute_unit": "validator:check_contract", "description": "confirm the perk's sequence + contracts are bound"},
            "a_execute": {"type": "compute", "compute_unit": "perk:sequence", "description": "run the perk's tool sequence via executor.py — recording each step to the run-ledger as it runs"},
        },
        "transitions": [
            {"from": "ready",    "to": "prepared", "trigger": "PREPARE", "action": "a_prepare", "gate": "g_prepared"},
            {"from": "prepared", "to": "verified", "trigger": "VERIFY",  "action": "a_verify",  "gate": "g_verified"},
            {"from": "verified", "to": "executed", "trigger": "EXECUTE", "action": "a_execute", "gate": "g_governed"},
        ],
        "safety_invariants": [
            {"name": "governed_execution_only", "expression": "state /= 'executed' \\/ governed_run", "description": "GUARDRAIL: a task reaches 'executed' ONLY through executor.py — the single governed channel; the runtime is the enforcement."},
            {"name": "record_during_execution", "expression": "state /= 'executed' \\/ recorded_each_step", "description": "GUARDRAIL: recording is PART of executing — each step is written to the run-ledger as it runs, not in a separate phase after."},
            {"name": "verify_before_execute", "expression": "state /= 'executed' \\/ contract_bound", "description": "GUARDRAIL: nothing executes until its tool sequence + contract are bound."},
            {"name": "oversight_clears_script", "expression": "TRUE", "description": "GUARDRAIL: the compiled script must clear OVERSIGHT_RULE (destructive/dangerous patterns push back unless explicitly approved)."},
        ],
    }


def snippet_stub(tool):
    return (f"#!/usr/bin/env bash\n"
            f"# {tool} — TODO: the proven pathway. Emit deterministic structured JSON (audit/debug log).\n"
            "set -euo pipefail\n"
            ': "${INPUT:?}" "${RECORD_STORE:?}"\n'
            f'OUT="${{RECORD_STORE%/}}/{tool}.out"\n'
            "# TODO: the real command using $INPUT, writing results to $OUT\n"
            f'echo "TODO: implement {tool}" > "$OUT"\n'
            f'printf \'{{"tool":"{tool}","status":"ok","out":"%s"}}\\n\' "$OUT"\n')


def py_stub(tool):
    """Python-core stub — the logic lives here; a thin .sh porter execs it (easy to inspect/lint/test)."""
    return (f"#!/usr/bin/env python3\n"
            f'"""{tool} — TODO: the proven pathway. Reads INPUT + RECORD_STORE from env; emits structured JSON."""\n'
            "from __future__ import annotations\n"
            "import json\nimport os\nimport sys\n\n\n"
            "def main() -> int:\n"
            '    """TODO: implement."""\n'
            '    inp = os.environ["INPUT"]\n'
            '    store = os.environ["RECORD_STORE"].rstrip("/")\n'
            f'    out = os.path.join(store, "{tool}.out")\n'
            "    # TODO: the real logic using `inp`, writing results to `out`\n"
            f'    open(out, "w").write("TODO: implement {tool}\\n")\n'
            f'    print(json.dumps({{"tool": "{tool}", "status": "ok", "out": out}}))\n'
            "    return 0\n\n\n"
            'if __name__ == "__main__":\n'
            "    sys.exit(main())\n")


def porter_stub(tool):
    """A thin .sh that runs the Python core, which reads its inputs from the (exported) environment."""
    return (f"#!/usr/bin/env bash\n"
            f"# {tool} — porter: runs the Python core ({tool}.py), which reads its inputs from the environment.\n"
            "set -euo pipefail\n"
            'HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"\n'
            f'exec python3 "$HERE/{tool}.py"\n')


def skill_md(sid, name, perks):
    rows = "\n".join(f"| `{pid}` | `{p['tool']}` | TODO |" for pid, p in perks.items())
    plist = ", ".join(perks)
    return (f"---\nskill: {sid}\nname: {name}\nperks: [{plist}]\n---\n\n"
            f"# {sid} — {name}\n\n"
            "TODO: context for the intelligence — what this skill does, what to look out for, which logs to check.\n\n"
            "## How to use it\n"
            "1. Pick a perk, copy `ledger.json` → `task-ledger.json`, fill the `${...}` vars + `record_store`.\n"
            "2. validate → compose → compile → oversight → executor (see the top-level README).\n\n"
            "## Perks\n| perk | tool | destructive? |\n|---|---|---|\n" + rows + "\n\n"
            "> Scaffolded by `infra/scaffold.py` — fill the snippets (`perks/<perk>/src/<tool>.sh`), the\n"
            "> contracts (vars/outputs), and this file.\n")


def main():
    ap = argparse.ArgumentParser(description="scaffold a new skill skeleton")
    ap.add_argument("--skill", required=True)
    ap.add_argument("--name", required=True)
    ap.add_argument("--desc", default="")
    ap.add_argument("--perk", action="append", required=True, help="<perk_id>:<tool>[:<binary>]")
    ap.add_argument("--force", action="store_true")
    a = ap.parse_args()
    sid = a.skill
    S = os.path.join(ROOT, "skills", sid)
    if os.path.exists(S) and not a.force:
        sys.exit(f"skills/{sid} already exists (use --force to overwrite)")

    perks = {}
    for spec in a.perk:
        parts = spec.split(":")
        if len(parts) < 2:
            sys.exit(f"--perk must be <perk_id>:<tool>[:<binary>], got: {spec}")
        pid, tool = parts[0], parts[1]
        perks[pid] = {"tool": tool, "binary": parts[2] if len(parts) > 2 else tool}

    wj(f"{S}/blueprint.json", blueprint(sid, a.name, a.desc or f"{a.name} — TODO describe what this skill does."))
    wj(f"{S}/perks.json", {"skill": sid, "perks": [
        {"id": pid, "summary": "TODO", "destructive": False, "tools": [p["tool"]]} for pid, p in perks.items()]})
    first = next(iter(perks))
    wj(f"{S}/ledger.json", {
        "_schema": f"task-ledger TEMPLATE for {sid} — set perk, fill record_store + the vars the perk's manifesto declares.",
        "skill": sid, "perk": first, "record_store": "<absolute dir for outputs + run-ledger>", "vars": {"INPUT": "<value>"}})
    open(f"{S}/SKILL.md", "w").write(skill_md(sid, a.name, perks))

    for pid, p in perks.items():
        P = f"{S}/perks/{pid}"
        tool, binary = p["tool"], p["binary"]
        out = "${RECORD_STORE}/" + tool + ".out"
        wj(f"{P}/metadata.json", {"perk": pid, "skill": sid, "description": "TODO", "rules": ["TODO"],
                                  "usage": "TODO", "limitation": "TODO",
                                  "minimal_example": {"perk": pid, "vars": {"INPUT": "<...>"}}})
        wj(f"{P}/manifesto.json", {"_perk": pid, "sequence": [tool],
                                   "tools": {tool: {"binary": binary, "params": {"INPUT": "${INPUT}"}}},
                                   "env": {"INPUT": "${INPUT}", "RECORD_STORE": "${record_store}"}, "requires": [binary]})
        wj(f"{P}/src/contracts.json", {"tool": tool, "inputs": {"INPUT": {"type": "string", "required": True}},
                                       "outputs": {tool + "_out": {"path": out, "type": "file"}},
                                       "checks": {"exit_zero": True, "output_exists": out}})
        if binary == "python3":          # python-core: standalone .py + a thin .sh porter (inspect/lint/test the .py directly)
            wsh(f"{P}/src/{tool}.py", py_stub(tool))
            wsh(f"{P}/src/{tool}.sh", porter_stub(tool))
        else:                            # the .sh is the tool itself (psql, curl, tar, git, …)
            wsh(f"{P}/src/{tool}.sh", snippet_stub(tool))

    print(f"scaffolded skills/{sid} · perks: {', '.join(perks)}")
    print("  next: fill the snippets (perks/<perk>/src/<tool>.sh), the vars (manifesto+contracts), SKILL.md")
    print(f"  then: python3 infra/composer.py --ledger skills/{sid}/ledger.json   (structure already composes)")


if __name__ == "__main__":
    main()
