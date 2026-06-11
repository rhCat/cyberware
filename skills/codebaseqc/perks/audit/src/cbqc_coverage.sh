#!/usr/bin/env bash
# cbqc_coverage — public functions whose name never appears in the test dir (coverage heuristic). Structured JSON.
set -euo pipefail
: "${PROJECT_DIR:?}" "${RECORD_STORE:?}"
OUT="${RECORD_STORE%/}/coverage_gaps.json"
python3 - "$PROJECT_DIR" "${SRC_DIR:-.}" "${TEST_DIR:-tests}" "$OUT" <<'PY'
import ast, os, sys, json
proj, src, testdir, out = sys.argv[1], sys.argv[2], sys.argv[3], sys.argv[4]
root = proj if src in (".", "") else os.path.join(proj, src)
troot = os.path.join(proj, testdir)
defs = {}
for dp, _, fs in os.walk(root):
    if "__pycache__" in dp or "/." in dp: continue
    if os.path.abspath(dp).startswith(os.path.abspath(troot)): continue
    for f in fs:
        if not f.endswith(".py"): continue
        p = os.path.join(dp, f)
        try: tree = ast.parse(open(p, encoding="utf-8").read(), p)
        except (SyntaxError, UnicodeDecodeError): continue
        for n in ast.walk(tree):
            if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef)) and not n.name.startswith("_"):
                defs.setdefault(n.name, f"{os.path.relpath(p, proj)}:{n.lineno}")
tested = set()
if os.path.isdir(troot):
    for dp, _, fs in os.walk(troot):
        for f in fs:
            if f.endswith(".py"):
                txt = open(os.path.join(dp, f), encoding="utf-8", errors="ignore").read()
                for name in defs:
                    if name in txt: tested.add(name)
uncovered = {k: v for k, v in defs.items() if k not in tested}
json.dump({"dimension": "coverage", "uncovered": uncovered, "public_total": len(defs), "uncovered_count": len(uncovered), "has_tests": os.path.isdir(troot)}, open(out, "w"), indent=2)
print(json.dumps({"tool": "cbqc_coverage", "status": "ok", "report": out, "public": len(defs), "uncovered": len(uncovered)}))
PY
