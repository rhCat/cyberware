#!/usr/bin/env python3
"""cbqc_contract — public functions missing a docstring or a return type.

Reads PROJECT_DIR, SRC_DIR (default "."), RECORD_STORE from the environment; writes contract_gaps.json
and prints one structured-JSON line. ast-based (sound for this check).
"""
from __future__ import annotations
import ast
import json
import os
import sys


def walk_py(root: str):
    """Yield (path, ast.Module) for every parseable .py file under root."""
    for dp, _, files in os.walk(root):
        if "__pycache__" in dp or "/." in dp:
            continue
        for f in files:
            if not f.endswith(".py"):
                continue
            p = os.path.join(dp, f)
            try:
                yield p, ast.parse(open(p, encoding="utf-8").read(), p)
            except (SyntaxError, UnicodeDecodeError):
                continue


def main() -> int:
    """Report public functions lacking a docstring or a return annotation."""
    proj = os.environ["PROJECT_DIR"]
    src = os.environ.get("SRC_DIR", ".")
    store = os.environ["RECORD_STORE"].rstrip("/")
    root = proj if src in (".", "") else os.path.join(proj, src)
    gaps: list[dict] = []
    total = 0
    for path, tree in walk_py(root):
        for n in ast.walk(tree):
            if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef)) and not n.name.startswith("_"):
                total += 1
                missing = []
                if not ast.get_docstring(n):
                    missing.append("docstring")
                if n.returns is None:
                    missing.append("return_type")
                if missing:
                    gaps.append({"fn": n.name, "at": f"{os.path.relpath(path, proj)}:{n.lineno}", "missing": missing})
    out = os.path.join(store, "contract_gaps.json")
    json.dump({"dimension": "contract", "gaps": gaps, "public_total": total, "gap_count": len(gaps)},
              open(out, "w"), indent=2)
    print(json.dumps({"tool": "cbqc_contract", "status": "ok", "report": out, "public": total, "gaps": len(gaps)}))
    return 0


if __name__ == "__main__":
    sys.exit(main())
