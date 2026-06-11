#!/usr/bin/env python3
"""cws_evaluate — classify a candidate skill: execution (tool) | design (taste) | transformable | unclear.

Reads SKILL_NAME, SKILL_DESC, RECORD_STORE from the environment; writes evaluation.json and prints one
structured-JSON line. Keyword heuristic — the verdict is a recommendation, not a proof.
"""
from __future__ import annotations
import json
import os
import re
import sys

EXEC = ["run", "build", "fetch", "query", "deploy", "compile", "test", "lint", "transform", "convert",
        "archive", "search", "commit", "tag", "execute", "send", "post", "request", "scan", "validate",
        "generate", "migrate", "backup", "restore", "extract", "parse", "format", "check", "process",
        "upload", "download", "sync", "render", "analyze", "count", "resolve", "diff", "snapshot"]
DESIGN = ["color", "colour", "font", "layout", "aesthetic", "style", "theme", "visual", "fade",
          "gradient", "spacing", "typography", "palette", "look", "feel", "beautiful", "pretty",
          "vibe", "tasteful", "elegant", "minimalist", "ornament", "branding", "mood"]


def signals(text: str, words: list) -> list:
    """The signal words present in text (whole-word)."""
    low = text.lower()
    return sorted({w for w in words if re.search(r"\b" + re.escape(w) + r"(?:s|es|ed|ing|d)?\b", low)})


def main() -> int:
    """Classify the candidate and write evaluation.json."""
    name = os.environ["SKILL_NAME"]
    desc = os.environ["SKILL_DESC"]
    store = os.environ["RECORD_STORE"].rstrip("/")
    ex, dz = signals(desc, EXEC), signals(desc, DESIGN)
    if ex and not dz:
        verdict, onboard = "execution", True
        rec = (f"'{name}' is an execution / tool skill — a deterministic pathway. It fits cyberware "
               f"directly: model it as a blueprint + perks, each tool emitting structured JSON. "
               f"Run cws-create/scaffold to lay down the skeleton.")
    elif dz and not ex:
        verdict, onboard = "design", False
        rec = (f"'{name}' is a design / taste skill (e.g. {', '.join(dz)}). That is NOT the cyberware "
               f"emphasis — the framework governs deterministic execution, not aesthetics. Keep it as "
               f"guidance, not a governed tool skill.")
    elif ex and dz:
        verdict, onboard = "transformable", True
        rec = (f"'{name}' mixes execution ({', '.join(ex)}) and design ({', '.join(dz)}). Extract the "
               f"execution core into a governed cyberware pathway; leave the taste/design part as "
               f"guidance. Run cws-create/scaffold on the execution core.")
    else:
        verdict, onboard = "unclear", False
        rec = (f"'{name}' shows no clear execution verbs or design signals — describe what it DOES "
               f"(inputs -> action -> output) so it can be classified.")
    out = os.path.join(store, "evaluation.json")
    result = {"tool": "cws_evaluate", "status": "ok", "skill": name, "verdict": verdict,
              "onboard": onboard, "execution_signals": ex, "design_signals": dz,
              "recommendation": rec, "report": out}
    json.dump(result, open(out, "w"), indent=2)
    print(json.dumps(result))
    return 0


if __name__ == "__main__":
    sys.exit(main())
