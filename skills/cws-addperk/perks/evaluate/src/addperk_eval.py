#!/usr/bin/env python3
"""addperk_eval — assess a proposed perk for a skill: does it BELONG, does it EXIST, is it GENERALIZABLE?

Reads SKILL, PERK, PERK_DESC, RECORD_STORE from the environment. Read-only — writes perk_eval.json and
prints one structured-JSON line. Exit 0 = ok to apply, 2 = should not apply (the chain halts there).
"""
from __future__ import annotations
import json
import os
import re
import sys

EXEC = ["run", "build", "fetch", "query", "deploy", "compile", "test", "lint", "transform", "convert",
        "archive", "search", "commit", "tag", "execute", "send", "post", "request", "scan", "validate",
        "generate", "migrate", "backup", "restore", "extract", "parse", "format", "check", "process",
        "upload", "download", "sync", "render", "analyze", "count", "resolve", "diff", "snapshot", "list",
        "push", "pull", "merge", "clone", "create", "update", "remove", "delete", "open", "write", "read",
        "copy", "move", "apply", "install", "start", "stop", "publish", "load", "watch", "notify", "dump", "patch"]


def repo_root() -> str:
    """The cyberware repo root, relative to this snippet."""
    here = os.path.dirname(os.path.abspath(__file__))
    return os.path.abspath(os.path.join(here, "..", "..", "..", "..", ".."))


def main() -> int:
    """Assess the proposed perk and write perk_eval.json."""
    skill = os.environ["SKILL"]
    perk = os.environ["PERK"]
    desc = os.environ["PERK_DESC"]
    store = os.environ["RECORD_STORE"].rstrip("/")
    sdir = os.path.join(repo_root(), "skills", skill)
    perks_json = os.path.join(sdir, "perks.json")
    existing = [p["id"] for p in json.load(open(perks_json)).get("perks", [])] if os.path.isfile(perks_json) else []
    exists = perk in existing

    STOP = {"the", "for", "and", "through", "with", "this", "that", "from", "into", "your", "only", "both",
            "via", "are", "not", "use", "run", "runs", "ran", "step", "steps", "tool", "tools", "skill",
            "perk", "perks", "task", "ledger", "record", "store", "output", "json", "structured", "executor",
            "pathway", "pathways", "proven", "concrete", "contract", "contracts", "bound", "agnostic",
            "lifecycle", "governed", "look", "logs", "check", "audit", "debug", "ready", "prepared",
            "verified", "executed", "what", "which", "each", "general", "supplies", "host", "name"}
    skill_text = skill.replace("_", " ").replace("-", " ")
    for fn in ("SKILL.md", "perks.json"):
        fp = os.path.join(sdir, fn)
        if os.path.isfile(fp):
            skill_text += " " + open(fp, encoding="utf-8", errors="ignore").read().lower()
    dw = set(re.findall(r"[a-z]{4,}", desc.lower())) - STOP
    sw = set(re.findall(r"[a-z]{4,}", skill_text)) - STOP
    shared = sorted(dw & sw)
    belongs = len(shared) >= 1
    verbs = sorted({w for w in EXEC if re.search(r"\b" + w + r"(?:s|es|ed|ing|d)?\b", desc.lower())})
    generalizable = bool(verbs)

    if not os.path.isdir(sdir):
        verdict, proceed, rec = "no_such_skill", False, f"No skill '{skill}'. Create it first with cws-create, or fix the name."
    elif exists:
        verdict, proceed, rec = "exists", False, f"Perk '{perk}' already exists in '{skill}' — pick another id or update the existing perk."
    elif not generalizable:
        verdict, proceed, rec = "unclear", False, f"Describe a clear deterministic action for '{perk}' — no execution verb found in the description."
    else:
        proceed = True
        scope = (f"shares {', '.join(shared)} with '{skill}'" if shared
                 else f"shares NO domain terms with '{skill}' — confirm it belongs here, not another skill")
        verdict = "ok" if shared else "ok_confirm_scope"
        rec = (f"'{perk}' is new and reads as a generalizable pathway ({', '.join(verbs)}); it {scope}. "
               f"If it belongs, run cws-addperk/apply — branch, formulate, validate, and open a PR.")
    result = {"tool": "addperk_eval", "status": "ok", "skill": skill, "perk": perk, "exists": exists,
              "belongs": belongs, "shared_terms": shared[:8], "generalizable": generalizable, "verbs": verbs,
              "verdict": verdict, "proceed": proceed, "recommendation": rec, "report": os.path.join(store, "perk_eval.json")}
    json.dump(result, open(os.path.join(store, "perk_eval.json"), "w"), indent=2)
    print(json.dumps(result))
    return 0 if proceed else 2


if __name__ == "__main__":
    sys.exit(main())
