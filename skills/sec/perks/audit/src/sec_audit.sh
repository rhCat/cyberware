#!/usr/bin/env bash
# sec_audit — best-effort dependency vulnerability audit (read-only). Structured JSON output.
# Runs pip-audit when it is on PATH and a requirements*.txt exists, and/or npm audit when npm is on
# PATH and a package.json exists. Auditors are OPTIONAL — when none can run, that is a clean no-op
# with a clear note. audit_report.json is ALWAYS written. Never installs or modifies dependencies.
set -uo pipefail
: "${PROJECT_DIR:?}" "${RECORD_STORE:?}"
OUT="${RECORD_STORE%/}/audit_report.json"
mkdir -p "${RECORD_STORE%/}"

AUDITORS=()      # names of auditors that actually ran
declare -a RESULT_KEYS=()
declare -a RESULT_FILES=()
NOTES=()

# --- pip-audit (only if the binary is present AND a requirements file exists under PROJECT_DIR) ---
if command -v pip-audit >/dev/null 2>&1; then
  REQ="$(find "$PROJECT_DIR" -type f -name 'requirements*.txt' -not -path '*/.*' 2>/dev/null | head -1 || true)"
  if [ -n "${REQ:-}" ]; then
    PA_OUT="${RECORD_STORE%/}/.pip_audit.json"
    pip-audit -f json -r "$REQ" > "$PA_OUT" 2>/dev/null || true
    if [ -s "$PA_OUT" ]; then
      AUDITORS+=("pip-audit"); RESULT_KEYS+=("pip_audit"); RESULT_FILES+=("$PA_OUT")
      NOTES+=("pip-audit ran against $REQ")
    else
      NOTES+=("pip-audit present but produced no JSON for $REQ")
    fi
  else
    NOTES+=("pip-audit present but no requirements*.txt under PROJECT_DIR")
  fi
else
  NOTES+=("pip-audit not on PATH")
fi

# --- npm audit (only if npm is present AND package.json exists in PROJECT_DIR) ---
if command -v npm >/dev/null 2>&1; then
  if [ -f "$PROJECT_DIR/package.json" ]; then
    NPM_OUT="${RECORD_STORE%/}/.npm_audit.json"
    # npm audit exits non-zero when advisories are found; capture JSON either way (script is not set -e).
    ( cd "$PROJECT_DIR" && npm audit --json ) > "$NPM_OUT" 2>/dev/null || true
    if [ -s "$NPM_OUT" ]; then
      AUDITORS+=("npm-audit"); RESULT_KEYS+=("npm_audit"); RESULT_FILES+=("$NPM_OUT")
      NOTES+=("npm audit ran in $PROJECT_DIR")
    else
      NOTES+=("npm present but npm audit produced no JSON")
    fi
  else
    NOTES+=("npm present but no package.json in PROJECT_DIR")
  fi
else
  NOTES+=("npm not on PATH")
fi

[ "${#AUDITORS[@]}" -eq 0 ] && NOTES+=("no auditor ran — report is a clean no-op")

# --- assemble the report (always valid JSON, embedding each auditor's raw JSON under results) ---
json_str() { printf '%s' "$1" | sed 's/\\/\\\\/g; s/"/\\"/g'; }

{
  printf '{\n'
  # auditors: [ ... ]
  printf '  "auditors": ['
  for i in "${!AUDITORS[@]}"; do
    [ "$i" -gt 0 ] && printf ', '
    printf '"%s"' "$(json_str "${AUDITORS[$i]}")"
  done
  printf '],\n'
  # results: { key: <raw auditor json>, ... }
  printf '  "results": {'
  for i in "${!RESULT_KEYS[@]}"; do
    [ "$i" -gt 0 ] && printf ','
    printf '\n    "%s": ' "$(json_str "${RESULT_KEYS[$i]}")"
    if [ -s "${RESULT_FILES[$i]}" ]; then cat "${RESULT_FILES[$i]}"; else printf 'null'; fi
  done
  printf '%s},\n' "$([ "${#RESULT_KEYS[@]}" -gt 0 ] && printf '\n  ')"
  # note: "a; b; c"
  NOTE_STR=""
  for n in "${NOTES[@]}"; do NOTE_STR="${NOTE_STR:+$NOTE_STR; }$n"; done
  printf '  "note": "%s"\n' "$(json_str "$NOTE_STR")"
  printf '}\n'
} > "$OUT" 2>/dev/null

# Guarantee the contract output exists no matter what.
[ -s "$OUT" ] || printf '{\n  "auditors": [],\n  "results": {},\n  "note": "audit_report write failed; clean no-op"\n}\n' > "$OUT"

# The per-auditor raw captures (.pip_audit.json / .npm_audit.json) are left as hidden sidecars in the
# record store — the final audit_report.json embeds their contents under "results".

printf '{"tool":"sec_audit","status":"ok","auditors":%s,"report":"%s"}\n' "${#AUDITORS[@]}" "$OUT"
