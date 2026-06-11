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

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def load(p): return json.load(open(p))


def main():
    ap = argparse.ArgumentParser(description="compile a task-ledger into a step-wise bash script")
    ap.add_argument("--ledger", required=True)
    ap.add_argument("-o", "--out", default=None)
    a = ap.parse_args()
    L = load(a.ledger)
    skill, perk, store, vars = L["skill"], L["perk"], L["record_store"], dict(L.get("vars", {}))
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
    text = "\n".join(out)
    if a.out:
        open(a.out, "w").write(text)
        os.chmod(a.out, 0o755)
        # quick-inspect artifacts beside the script: the blueprint diagram annotated with THIS perk's
        # tool sequence, in both draw.io XML and self-contained SVG — the only fast way to eyeball it.
        try:
            import visualize
            bp = load(os.path.join(ROOT, "skills", skill, "blueprint.json"))
            base = a.out[:-3] if a.out.endswith(".sh") else a.out
            extra = ", ".join(os.path.basename(w) for w in visualize.render(bp, seq, base, ["drawio", "svg"]))
            print(f"compiled {skill}/{perk} → {a.out}  (+ {extra} · {len(seq)} steps)")
        except Exception as e:
            print(f"compiled {skill}/{perk} → {a.out}  ({len(seq)} steps; diagram skipped: {e})")
    else:
        sys.stdout.write(text)


if __name__ == "__main__":
    main()
