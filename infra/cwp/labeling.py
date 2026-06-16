#!/usr/bin/env python3
"""infra/cwp/labeling.py — truth-in-labeling doc lint (P0-T16).

You may not label a control "enforced" you cannot point to. Every enforcement CLAIM in the specs — an
"Enforced by:" footer or an explicit `ENFORCED` tag — must cite at least one plan **criterion-id** (a
validator id `P0-V06`, a task id `P1-T07`, a feature `F5`, or a milestone `M9`). A claim with no criterion
reference is a truth-in-labeling violation: the doc asserts enforcement the plan does not pin.

The check is paragraph-scoped (a claim and its citation live in the same footer paragraph) and deliberately
narrow — a casual lowercase "enforced" in prose is not a claim; only the `Enforced by:` footer convention
and an uppercase `ENFORCED` tag are.
"""
from __future__ import annotations
import glob
import os
import re

# plan criterion / validator / feature / milestone ids
CRITERION = re.compile(r"\b(P\d+-[VT]\d+|F\d+|M\d+)\b")
# an enforcement CLAIM: the "Enforced by:" footer convention, or an explicit uppercase ENFORCED tag
CLAIM = re.compile(r"[Ee]nforced by:|\[ENFORCED|\bENFORCED\b")


def lint_text(text: str) -> dict:
    """Per-paragraph: any paragraph making an enforcement claim must cite a criterion-id."""
    claims, violations = 0, []
    for para in re.split(r"\n\s*\n", text):
        if CLAIM.search(para):
            claims += 1
            if not CRITERION.search(para):
                violations.append(" ".join(para.split())[:140])
    return {"claims": claims, "violations": violations}


def lint_doc(path: str) -> dict:
    with open(path, encoding="utf-8") as f:
        r = lint_text(f.read())
    return {"path": os.path.basename(path), **r}


def lint_specs(spec_dir: str) -> dict:
    """Lint every spec under `spec_dir`. `ok` iff the convention is exercised (some claims exist) and no
    enforcement claim is missing its criterion-id."""
    docs = [lint_doc(p) for p in sorted(glob.glob(os.path.join(spec_dir, "*.md")))]
    claims = sum(d["claims"] for d in docs)
    bad = [{"path": d["path"], "violations": d["violations"]} for d in docs if d["violations"]]
    return {"docs": len(docs), "claims": claims, "docs_with_claims": sum(1 for d in docs if d["claims"]),
            "violations": bad, "ok": (not bad) and claims > 0}


DEFAULT_SPECS = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),
                             "spec")


if __name__ == "__main__":
    import json
    import sys
    r = lint_specs(DEFAULT_SPECS)
    print(json.dumps(r, indent=2))
    sys.exit(0 if r["ok"] else 1)
