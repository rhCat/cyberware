#!/usr/bin/env bash
# cbqc_contract — public functions missing a docstring or a return type. Structured JSON.
set -euo pipefail
: "${PROJECT_DIR:?}" "${RECORD_STORE:?}"
OUT="${RECORD_STORE%/}/contract_gaps.json"
python3 - "$PROJECT_DIR" "${SRC_DIR:-.}" "$OUT" <<'PY'
import ast, os, sys, json
proj, src, out = sys.argv[1], sys.argv[2], sys.argv[3]
root = proj if src in (".", "") else os.path.join(proj, src)
gaps, total = [], 0
for dp, _, fs in os.walk(root):
    if "__pycache__" in dp or "/." in dp: continue
    for f in fs:
        if not f.endswith(".py"): continue
        p = os.path.join(dp, f)
        try: tree = ast.parse(open(p, encoding="utf-8").read(), p)
        except (SyntaxError, UnicodeDecodeError): continue
        for n in ast.walk(tree):
            if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef)) and not n.name.startswith("_"):
                total += 1
                miss = []
                if not ast.get_docstring(n): miss.append("docstring")
                if n.returns is None: miss.append("return_type")
                if miss: gaps.append({"fn": n.name, "at": f"{os.path.relpath(p, proj)}:{n.lineno}", "missing": miss})
json.dump({"dimension": "contract", "gaps": gaps, "public_total": total, "gap_count": len(gaps)}, open(out, "w"), indent=2)
print(json.dumps({"tool": "cbqc_contract", "status": "ok", "report": out, "public": total, "gaps": len(gaps)}))
PY
