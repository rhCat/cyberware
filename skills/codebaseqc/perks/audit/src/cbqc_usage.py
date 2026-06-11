#!/usr/bin/env python3
"""cbqc_usage — functions defined but never referenced by name (dead-code heuristic).

Reads PROJECT_DIR, SRC_DIR (default "."), RECORD_STORE from the environment; writes usage_gaps.json
and prints one structured-JSON line (the audit/debug log). Name-based heuristic.
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
    """Report functions whose name never appears as a call."""
    proj = os.environ["PROJECT_DIR"]
    src = os.environ.get("SRC_DIR", ".")
    store = os.environ["RECORD_STORE"].rstrip("/")
    root = proj if src in (".", "") else os.path.join(proj, src)
    defs: dict[str, list[str]] = {}
    calls: set[str] = set()
    for path, tree in walk_py(root):
        for n in ast.walk(tree):
            if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef)):
                defs.setdefault(n.name, []).append(f"{os.path.relpath(path, proj)}:{n.lineno}")
            elif isinstance(n, ast.Call):
                fn = n.func
                if isinstance(fn, ast.Name):
                    calls.add(fn.id)
                elif isinstance(fn, ast.Attribute):
                    calls.add(fn.attr)
    unused = {k: v for k, v in defs.items() if k not in calls and not k.startswith("__")}
    out = os.path.join(store, "usage_gaps.json")
    json.dump({"dimension": "usage", "unused_functions": unused, "defined": len(defs), "unused_count": len(unused)},
              open(out, "w"), indent=2)
    print(json.dumps({"tool": "cbqc_usage", "status": "ok", "report": out, "defined": len(defs), "unused": len(unused)}))
    return 0


if __name__ == "__main__":
    sys.exit(main())
