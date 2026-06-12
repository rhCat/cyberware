#!/usr/bin/env python3
"""oversight.py — enforce OVERSIGHT_RULE over a compiled script. Push back on violations.

regex (the default) over the compiled bash; a matched deny rule blocks the run. *Approvable* rules
(drop table, truncate, …) can be waived with `--approve <id>` — an explicit, logged decision.
*Non-approvable* rules (drop database, pipe-to-shell, sudo) can never be waived. `--subagent` is the
opt-in hook to hand the script to an LLM reviewer; the regex pass is authoritative either way.

  oversight.py --script run.sh [--approve drop_table] [--subagent]
"""
from __future__ import annotations
import argparse, json, os, re, sys

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
RULES_PATH = os.path.join(ROOT, "infra", "govern", "OVERSIGHT_RULE.json")


def scan(script_text, approve=(), rules_path=RULES_PATH):
    """Scan compiled bash against OVERSIGHT_RULE. Returns (violations, waived) — rule dicts.
    The single source of truth: the standalone CLI *and* the executor's in-channel gate both call this."""
    violations, waived = [], []
    for r in json.load(open(rules_path))["deny"]:
        if re.search(r["pattern"], script_text):
            (waived if (r["id"] in approve and r.get("approvable")) else violations).append(r)
    return violations, waived


def main():
    ap = argparse.ArgumentParser(description="enforce OVERSIGHT_RULE over a compiled script")
    ap.add_argument("--script", required=True)
    ap.add_argument("--rules", default=os.path.join(ROOT, "infra", "govern", "OVERSIGHT_RULE.json"))
    ap.add_argument("--approve", action="append", default=[], help="rule id to waive (approvable rules only)")
    ap.add_argument("--subagent", action="store_true", help="opt-in LLM review hook")
    a = ap.parse_args()
    script = open(a.script).read()
    print(f"oversight · {os.path.basename(a.script)}")

    violations, waived = scan(script, a.approve, a.rules)
    for r in waived:
        print(f"  [WAIVED] {r['id']} — {r['reason']} (explicitly approved)")
    for r in violations:
        how = "" if not r.get("approvable") else f"  (approvable: --approve {r['id']})"
        print(f"  [BLOCK] {r['id']} — {r['reason']}{how}")
    if not violations and not waived:
        print("  [clean] no denied patterns")
    if a.subagent:
        print("  [subagent] opt-in LLM review not wired in this scaffold — the regex pass governs")

    if violations:
        print(f"oversight: PUSH BACK — {len(violations)} unwaived violation(s)")
        sys.exit(2)
    print("oversight: PASS" + (f" ({len(waived)} waived)" if waived else ""))
    sys.exit(0)


if __name__ == "__main__":
    main()
