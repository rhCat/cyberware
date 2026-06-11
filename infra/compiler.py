#!/usr/bin/env python3
"""compiler.py — task-ledger + blueprint + contracts + snippets → ONE step-wise bash script.

Reads the chosen perk's manifesto (the `${VAR}` template + the tool `sequence`), substitutes the
task-ledger's `vars` and `record_store`, and emits a single bash executable in which each tool is a
gated step (`--step N`), each followed by its contract checks. The script is meant to be run *only*
through `executor.py`. The compiler touches nothing — it returns a string.

  compiler.py --ledger task-ledger.json [-o run.sh]
"""
from __future__ import annotations
import argparse, json, os, shlex, sys

from runlog import run_dir

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


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
    # the blueprint diagram (annotated with this perk's tools), beside the script
    base = out[:-3] if out.endswith(".sh") else out
    diagrams = []
    try:
        import visualize
        bp = load(os.path.join(ROOT, "skills", skill, "blueprint.json"))
        diagrams = visualize.render(bp, seq, base, ["drawio", "svg"])
    except Exception as e:
        print(f"  (diagram skipped: {e})", file=sys.stderr)
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
           "run": {"dir": run, "script": out, "diagrams": diagrams,
                   "outputs": outs, "logs": os.path.join(run, "run-ledger.json")}}
    open(os.path.join(run, "task-ledger.json"), "w").write(json.dumps(led, indent=2) + "\n")
    print(f"compiled {skill}/{perk} → {out}  ({len(seq)} steps)")
    print(f"  run dir: {run}  · task-ledger.json points to outputs + run-ledger.json (all land here)")


if __name__ == "__main__":
    main()
