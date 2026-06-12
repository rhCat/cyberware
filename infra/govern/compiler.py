#!/usr/bin/env python3
"""compiler.py — task-ledger + blueprint + contracts + snippets → ONE step-wise bash script.

Reads the chosen perk's manifesto (the `${VAR}` template + the tool `sequence`), substitutes the
task-ledger's `vars` and `record_store`, and emits a single bash executable in which each tool is a
gated step (`--step N`), each followed by its contract checks. The script is meant to be run *only*
through `executor.py`. The compiler touches nothing — it returns a string.

  compiler.py --ledger task-ledger.json [-o run.sh]
"""
from __future__ import annotations
import argparse, hashlib, json, os, re, shlex, sys

from infra.govern.runlog import run_dir

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def load(p): return json.load(open(p))


def build_script(L):
    """Compile a task-ledger dict into (bash text, tool sequence). Pure — touches nothing on disk."""
    skill, perk, store, vars = L["skill"], L["perk"], run_dir(L), dict(L.get("vars", {}))
    pdir = os.path.join(ROOT, "skills", skill, "perks", perk)
    manifesto = load(os.path.join(pdir, "manifesto.json"))
    contract = load(os.path.join(pdir, "src", "contracts.json"))
    snip = os.path.join(pdir, "src")

    # the exported environment: the ledger vars + RECORD_STORE (the snippets read these)
    env = dict(vars)
    env["RECORD_STORE"] = store
    exports = " ".join(f"{k}={shlex.quote(str(v))}" for k, v in env.items())

    out = [
        "#!/usr/bin/env bash",
        f"# COMPILED by cyberware · skill={skill} perk={perk}",
        "# Run ONLY through executor.py — it is the governed channel. Proven-pathway snippets live in the registry.",
        "set -uo pipefail",
        f"export {exports}",
        'mkdir -p "$RECORD_STORE"',
        f"SNIP={shlex.quote(snip)}",
        "",
    ]
    seq = manifesto.get("sequence", [])
    for i, tool in enumerate(seq, 1):
        out.append(f"step{i}() {{   # {tool}")
        out.append(f'  echo "[step {i}] {tool}"')
        out.append(f'  bash "$SNIP/{tool}.sh"')
        # contract checks (output_exists → file present; the snippet itself set -e handles exit_zero)
        oe = contract.get("checks", {}).get("output_exists")
        if oe and tool == seq[-1]:   # the contract's declared output is the perk's final artifact
            out.append(f'  test -f "{oe}" || {{ echo "CONTRACT FAIL step {i}: missing {oe}" >&2; exit 3; }}')
        out.append("}")
        out.append("")

    listing = "\\n".join(f"{i}\\t{t}" for i, t in enumerate(seq, 1))
    out += [
        'case "${1:-}" in',
        f'  --list) printf "{listing}\\n" ;;',
        '  --step) shift; "step${1:?step number}" ;;',
        "  --all) " + " && ".join(f"step{i}" for i in range(1, len(seq) + 1)) + " ;;",
        '  *) echo "usage: $0 --list | --step <N> | --all" >&2; exit 2 ;;',
        "esac",
        "",
    ]
    return "\n".join(out), seq


def build_plan(skill, perk):
    """The VALUE-FREE execution plan for a perk — the structure govd blesses and hashes, with NO task
    data in it. Returns a dict: the tool sequence, the wrapper bash (placeholders, no `export` of values),
    each snippet's full sha256, and the snippet texts (so a remote agent can assemble the run locally).
    The agent prepends its own `export` line (its vars, incl. `${SNIP}`/`${RECORD_STORE}`) before running.
    govd never sees a value; the plan hash is stable regardless of the vars the agent later binds."""
    pdir = os.path.join(ROOT, "skills", skill, "perks", perk)
    manifesto = load(os.path.join(pdir, "manifesto.json"))
    contract = load(os.path.join(pdir, "src", "contracts.json"))
    seq = manifesto.get("sequence", [])
    snippets, snippet_shas = {}, {}
    for tool in seq:
        body = open(os.path.join(pdir, "src", f"{tool}.sh"), "rb").read()
        snippets[tool] = body.decode()
        snippet_shas[tool] = hashlib.sha256(body).hexdigest()

    wrap = [
        "#!/usr/bin/env bash",
        f"# cyberware plan · skill={skill} perk={perk} · value-free; the caller exports SNIP/RECORD_STORE/vars",
        "set -uo pipefail",
        ': "${SNIP:?SNIP must point at the perk snippet dir}" "${RECORD_STORE:?}"',
        'mkdir -p "$RECORD_STORE"',
        "",
    ]
    for i, tool in enumerate(seq, 1):
        wrap.append(f"step{i}() {{   # {tool}")
        wrap.append(f'  echo "[step {i}] {tool}"')
        wrap.append(f'  bash "$SNIP/{tool}.sh"')
        oe = contract.get("checks", {}).get("output_exists")
        if oe and tool == seq[-1]:
            wrap.append(f'  test -f "{oe}" || {{ echo "CONTRACT FAIL step {i}: missing {oe}" >&2; exit 3; }}')
        wrap.append("}")
        wrap.append("")
    listing = "\\n".join(f"{i}\\t{t}" for i, t in enumerate(seq, 1))
    wrap += [
        'case "${1:-}" in',
        f'  --list) printf "{listing}\\n" ;;',
        '  --step) shift; "step${1:?step number}" ;;',
        "  --all) " + " && ".join(f"step{i}" for i in range(1, len(seq) + 1)) + " ;;",
        '  *) echo "usage: $0 --list | --step <N> | --all" >&2; exit 2 ;;',
        "esac",
        "",
    ]
    return {"skill": skill, "perk": perk, "sequence": list(seq),
            "wrapper": "\n".join(wrap), "snippet_shas": snippet_shas, "snippets": snippets}


def plan_sha(plan):
    """The sha256 of the execution plan — value-free, so govd and the agent compute the same hash.
    Covers the pathway (skill/perk/sequence), the exact snippet bytes, and the wrapper structure."""
    canon = json.dumps({k: plan[k] for k in ("skill", "perk", "sequence", "wrapper", "snippet_shas")},
                       sort_keys=True)
    return hashlib.sha256(canon.encode()).hexdigest()


def task_blueprint(L, run, seq=None):
    """The skill's blueprint specialised for THIS task: each gate's abstract predicate bound to the
    concrete check it stands for — resolved against the perk's contract + the task vars — plus the
    resolved contract itself. So the diagram shows what is *actually* validated, not the generic lifecycle."""
    skill, perk, vars = L["skill"], L["perk"], dict(L.get("vars", {}))
    pdir = os.path.join(ROOT, "skills", skill, "perks", perk)
    bp = load(os.path.join(ROOT, "skills", skill, "blueprint.json"))
    contract = load(os.path.join(pdir, "src", "contracts.json"))
    manifesto = load(os.path.join(pdir, "manifesto.json"))
    if seq is None:
        seq = manifesto.get("sequence", [])
    subs = {**vars, "RECORD_STORE": run, "record_store": run}

    def resolve(s):
        for k, v in subs.items():
            s = s.replace("${" + k + "}", str(v))
        return s

    inputs, checks = contract.get("inputs", {}), contract.get("checks", {})
    required = [k for k, spec in inputs.items() if spec.get("required")]
    oe = resolve(checks["output_exists"]) if checks.get("output_exists") else ""
    oed = oe.replace(run, "$RUN") if oe.startswith(run) else oe   # $RUN abbreviates the run dir (defined in the header)
    passes = (["exit_zero == 0"] if checks.get("exit_zero") else []) + ([f"test -f {oed}"] if oe else [])
    rcontract = {                                       # the contract resolved for THIS task
        "tool": contract.get("tool", ""),
        "inputs": {k: {"value": vars.get(k, ""), "type": spec.get("type", ""), "required": spec.get("required", False)}
                   for k, spec in inputs.items()},
        "outputs": {k: {"path": resolve(o.get("path", "")), **({"type": o["type"]} if o.get("type") else {})}
                    for k, o in contract.get("outputs", {}).items()},
        "checks": {**checks, **({"output_exists": oe} if oe else {})},
        "requires": manifesto.get("requires", []),
    }
    atom = {                                            # abstract predicate → the concrete check for this task
        "inputs_present": " ∧ ".join(f"{k}={vars.get(k, '∅')}" for k in required) or "(no required inputs)",
        "store_writable": "store $RUN writable",
        "sequence_resolved": " → ".join(seq) or "(empty)",
        "contracts_present": "I/O + checks bound",
        "governed_run": "ran via executor.py",
        "contract_checks_pass": " ∧ ".join(passes) or "(no checks)",
    }

    def bind(expr):
        out = []
        for p in re.split(r"(/\\|\\/)", expr):
            t = p.strip()
            out.append("∧" if t == "/\\" else "∨" if t == "\\/" else (atom.get(t, t) if t else ""))
        return " ".join(x for x in out if x)

    gates = {gid: {**g, "binding": bind(g.get("expression", ""))} for gid, g in bp.get("gates", {}).items()}
    return {**bp, "gates": gates,
            "task": {"skill": skill, "perk": perk, "vars": vars, "tools": seq,
                     "run_dir": run, "contract": rcontract}}


def main():
    ap = argparse.ArgumentParser(description="compile a task-ledger into a step-wise bash script")
    ap.add_argument("--ledger", required=True)
    ap.add_argument("-o", "--out", default=None)
    a = ap.parse_args()
    L = load(a.ledger)
    skill, perk = L["skill"], L["perk"]
    run = run_dir(L)                                # the grouped run dir (~/cyberware_run_logs/... by default)
    os.makedirs(run, exist_ok=True)
    out = a.out or os.path.join(run, "run.sh")      # the compiled script lives in the run dir unless -o overrides
    os.makedirs(os.path.dirname(os.path.abspath(out)), exist_ok=True)
    text, seq = build_script(L)
    open(out, "w").write(text)
    os.chmod(out, 0o755)
    # the TASK blueprint = the skill's blueprint specialised for THIS task (its perk, vars, run dir),
    # saved to the run dir; the run diagrams are compiled from IT, not the general blueprint.
    base = out[:-3] if out.endswith(".sh") else out
    task_bp_path = os.path.join(run, "task-blueprint.json")
    diagrams = []
    try:
        from infra.tool import visualize
        task_bp = task_blueprint(L, run, seq)
        open(task_bp_path, "w").write(json.dumps(task_bp, indent=2) + "\n")
        diagrams = visualize.render(task_bp, seq, base, ["drawio", "svg"])
    except Exception as e:
        print(f"  (task blueprint / diagram skipped: {e})", file=sys.stderr)
    # a copy of the task-ledger in the run dir, carrying a pointer to the outputs + logs
    contract = load(os.path.join(ROOT, "skills", skill, "perks", perk, "src", "contracts.json"))
    # resolve EVERY var (not just RECORD_STORE): an output designed for a given dir (e.g. ${TARGET_DIR})
    # points THERE, not at the run logs — only ${RECORD_STORE} artifacts land under the run dir.
    subs = {**L.get("vars", {}), "RECORD_STORE": run, "record_store": run}
    outs = []
    for o in contract.get("outputs", {}).values():
        p = o.get("path") or ""
        for k, v in subs.items():
            p = p.replace("${" + k + "}", str(v))
        if p and p not in outs:
            outs.append(p)
    led = {**L, "record_store": run,
           "run": {"dir": run, "script": out, "blueprint": task_bp_path, "diagrams": diagrams,
                   "outputs": outs, "logs": os.path.join(run, "run-ledger.json")}}
    open(os.path.join(run, "task-ledger.json"), "w").write(json.dumps(led, indent=2) + "\n")
    print(f"compiled {skill}/{perk} → {out}  ({len(seq)} steps)")
    print(f"  run dir: {run}  · task-ledger.json points to outputs + run-ledger.json (all land here)")


if __name__ == "__main__":
    main()
