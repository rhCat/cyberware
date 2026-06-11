#!/usr/bin/env python3
"""cbqc_coverage — public functions whose name never appears in the test dir (coverage heuristic).

Reads PROJECT_DIR, SRC_DIR (default "."), TEST_DIR (default "tests"), RECORD_STORE from the
environment; writes coverage_gaps.json and prints one structured-JSON line. Name-based heuristic.
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
    """Report public functions not referenced anywhere under the test dir."""
    proj = os.environ["PROJECT_DIR"]
    src = os.environ.get("SRC_DIR", ".")
    testdir = os.environ.get("TEST_DIR", "tests")
    store = os.environ["RECORD_STORE"].rstrip("/")
    root = proj if src in (".", "") else os.path.join(proj, src)
    troot = os.path.join(proj, testdir)
    defs: dict[str, str] = {}
    for path, tree in walk_py(root):
        if os.path.abspath(path).startswith(os.path.abspath(troot)):
            continue
        for n in ast.walk(tree):
            if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef)) and not n.name.startswith("_"):
                defs.setdefault(n.name, f"{os.path.relpath(path, proj)}:{n.lineno}")
    tested: set[str] = set()
    if os.path.isdir(troot):
        for dp, _, files in os.walk(troot):
            for f in files:
                if f.endswith(".py"):
                    text = open(os.path.join(dp, f), encoding="utf-8", errors="ignore").read()
                    tested.update(name for name in defs if name in text)
    uncovered = {k: v for k, v in defs.items() if k not in tested}
    out = os.path.join(store, "coverage_gaps.json")
    json.dump({"dimension": "coverage", "uncovered": uncovered, "public_total": len(defs),
               "uncovered_count": len(uncovered), "has_tests": os.path.isdir(troot)}, open(out, "w"), indent=2)
    print(json.dumps({"tool": "cbqc_coverage", "status": "ok", "report": out, "public": len(defs), "uncovered": len(uncovered)}))
    return 0


if __name__ == "__main__":
    sys.exit(main())
