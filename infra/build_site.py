#!/usr/bin/env python3
"""build_site.py — generate docs/site/data.js for the static skill dashboard.

Walks skills/, reads each skill's blueprint + SKILL.md + perks (metadata, manifesto, contracts, the
snippet code) + blueprint.svg, and emits `window.SKILLS = [...]` for docs/site/index.html. Static —
open docs/site/index.html in a browser, no server, no build.

  build_site.py
"""
from __future__ import annotations
import glob
import json
import os

import visualize
import compiler

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def load(p: str) -> dict:
    """Load a JSON file, or {} if absent."""
    return json.load(open(p)) if os.path.isfile(p) else {}


def read(p: str) -> str:
    """Read a text file, or '' if absent."""
    return open(p, encoding="utf-8").read() if os.path.isfile(p) else ""


def perk_data(pdir: str, pm: dict, bp: dict) -> dict:
    """Assemble one perk: metadata + manifesto + contracts + snippet code + the perk-annotated SVG."""
    man = load(os.path.join(pdir, "manifesto.json"))
    seq = man.get("sequence", [])
    snippets = {}
    for tool in seq:
        for ext in (".py", ".sh"):
            fp = os.path.join(pdir, "src", tool + ext)
            if os.path.isfile(fp):
                snippets[tool + ext] = read(fp)
    return {
        "id": pm["id"], "summary": pm.get("summary", ""), "destructive": pm.get("destructive", False),
        "metadata": load(os.path.join(pdir, "metadata.json")),
        "sequence": seq, "tools": man.get("tools", {}),
        "env": man.get("env", {}), "requires": man.get("requires", []),
        "contracts": load(os.path.join(pdir, "src", "contracts.json")), "snippets": snippets,
        "svg": visualize.svg(bp, seq),
    }


def demo_data(sid: str, perk: dict, tpl_vars: dict) -> dict:
    """A worked example: a pre-filled task-ledger for the perk + its real compiled script."""
    ex = perk.get("metadata", {}).get("minimal_example", {}).get("vars", {})
    dvars = {}
    for v in perk.get("env", {}):
        if v != "RECORD_STORE":
            dvars[v] = ex.get(v, tpl_vars.get(v, ""))
    ledger = {"skill": sid, "perk": perk["id"], "record_store": f"/tmp/{sid}-demo", "vars": dvars}
    try:
        text, _ = compiler.build_script(ledger)
        compiled = text.replace(ROOT + "/", "")   # relativize the SNIP path for display
    except Exception as exc:
        compiled = f"# (compile preview unavailable: {exc})"
    return {"perk": perk["id"], "ledger": ledger, "compiled": compiled}


def skill_data(sdir: str) -> dict | None:
    """Assemble one skill: blueprint + svg + SKILL.md + perks + a worked demo."""
    bp = load(os.path.join(sdir, "blueprint.json"))
    if not bp:
        return None
    perks = [perk_data(os.path.join(sdir, "perks", pm["id"]), pm, bp)
             for pm in load(os.path.join(sdir, "perks.json")).get("perks", [])]
    tpl_vars = load(os.path.join(sdir, "ledger.json")).get("vars", {})
    return {
        "id": bp["id"], "name": bp.get("name", bp["id"]), "description": bp.get("description", ""),
        "states": bp.get("states", {}), "transitions": bp.get("transitions", []),
        "terminal": list(bp.get("terminal_states", {})), "entry": bp.get("entry_state", ""),
        "safety_invariants": bp.get("safety_invariants", []),
        "svg": read(os.path.join(sdir, "blueprint.svg")), "skill_md": read(os.path.join(sdir, "SKILL.md")),
        "perks": perks,
        "demo": demo_data(bp["id"], perks[0], tpl_vars) if perks else None,
    }


DOC_TABS = [("architecture", "Architecture"), ("authoring", "Authoring"), ("skills", "Catalog")]


def main() -> int:
    """Emit docs/site/data.js — the skills plus the markdown review docs."""
    skills = [d for sdir in sorted(glob.glob(os.path.join(ROOT, "skills", "*")))
              if os.path.isdir(sdir) and (d := skill_data(sdir))]
    docs = [{"id": name, "label": label, "body": read(os.path.join(ROOT, "docs", name + ".md"))}
            for name, label in DOC_TABS]
    out = os.path.join(ROOT, "docs", "site", "data.js")
    os.makedirs(os.path.dirname(out), exist_ok=True)
    open(out, "w").write("window.SKILLS = " + json.dumps(skills, indent=1)
                         + ";\nwindow.DOCS = " + json.dumps(docs, indent=1) + ";\n")
    print(f"wrote {os.path.relpath(out, ROOT)} — {len(skills)} skills, "
          f"{sum(len(s['perks']) for s in skills)} perks, {len(docs)} docs")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
