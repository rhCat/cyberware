#!/usr/bin/env bash
# cbqc_usage — functions defined but never referenced by name (dead-code heuristic). Structured JSON.
set -euo pipefail
: "${PROJECT_DIR:?}" "${RECORD_STORE:?}"
OUT="${RECORD_STORE%/}/usage_gaps.json"
python3 - "$PROJECT_DIR" "${SRC_DIR:-.}" "$OUT" <<'PY'
import ast, os, sys, json
proj, src, out = sys.argv[1], sys.argv[2], sys.argv[3]
root = proj if src in (".", "") else os.path.join(proj, src)
defs, calls = {}, set()
for dp, _, fs in os.walk(root):
    if "__pycache__" in dp or "/." in dp: continue
    for f in fs:
        if not f.endswith(".py"): continue
        p = os.path.join(dp, f)
        try: tree = ast.parse(open(p, encoding="utf-8").read(), p)
        except (SyntaxError, UnicodeDecodeError): continue
        for n in ast.walk(tree):
            if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef)):
                defs.setdefault(n.name, []).append(f"{os.path.relpath(p, proj)}:{n.lineno}")
            elif isinstance(n, ast.Call):
                fn = n.func
                if isinstance(fn, ast.Name): calls.add(fn.id)
                elif isinstance(fn, ast.Attribute): calls.add(fn.attr)
unused = {k: v for k, v in defs.items() if k not in calls and not k.startswith("__")}
json.dump({"dimension": "usage", "unused_functions": unused, "defined": len(defs), "unused_count": len(unused)}, open(out, "w"), indent=2)
print(json.dumps({"tool": "cbqc_usage", "status": "ok", "report": out, "defined": len(defs), "unused": len(unused)}))
PY
