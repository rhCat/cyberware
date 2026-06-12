#!/usr/bin/env bash
# sec_secrets — scan a tree for likely leaked secrets (read-only). Structured JSON output.
# Pure bash + grep + awk (no Python). grep -rEn over SEARCH_DIR for three secret families;
# the report carries file:line:rule only (the secret VALUE is never copied into the report).
# secrets_report.json is ALWAYS written — empty findings array when nothing matched.
set -uo pipefail
: "${SEARCH_DIR:?}" "${RECORD_STORE:?}"
OUT="${RECORD_STORE%/}/secrets_report.json"
mkdir -p "${RECORD_STORE%/}"

# Collect raw grep hits as: <rule>\t<grep "file:line:content">. -I skips binaries, -r recurses,
# -E extended regex, -n line numbers. `|| true` so a no-match exit (1) never aborts the script.
RAW="$(
  {
    grep -rEnI -- 'AKIA[0-9A-Z]{16}' "$SEARCH_DIR" 2>/dev/null \
      | awk '{print "aws_access_key\t" $0}' || true
    grep -rEnI -- '-----BEGIN [A-Z ]*PRIVATE KEY-----' "$SEARCH_DIR" 2>/dev/null \
      | awk '{print "private_key\t" $0}' || true
    grep -rEnIi -- '((api|secret|access)[_-]?key|password|token)' "$SEARCH_DIR" 2>/dev/null \
      | awk '{print "assigned_secret\t" $0}' || true
  }
)"

# Build the JSON report with awk (handles "" / \\ escaping). For assigned_secret we keep only lines
# where the keyword is actually followed by '=' or ':' and a value — drops bare mentions in prose.
printf '%s\n' "$RAW" | awk -F'\t' '
  function jesc(s){ gsub(/\\/,"\\\\",s); gsub(/"/,"\\\"",s); return s }
  BEGIN{ n=0; assign="((api|secret|access)[_-]?key|password|token)[ \t\"'"'"']*[:=][ \t\"'"'"']*[^ \t\"'"'"']" }
  NF<2 { next }
  {
    rule=$1; rest=$2
    ci=index(rest,":"); if(ci==0) next
    file=substr(rest,1,ci-1); tail=substr(rest,ci+1)
    cj=index(tail,":"); if(cj==0){ lno=tail; content="" } else { lno=substr(tail,1,cj-1); content=substr(tail,cj+1) }
    if(lno !~ /^[0-9]+$/) next
    if(rule=="assigned_secret" && tolower(content) !~ assign) next
    k=file SUBSEP lno SUBSEP rule; if(seen[k]++) next
    item[n++]=sprintf("    {\"file\": \"%s\", \"line\": %s, \"rule\": \"%s\"}", jesc(file), lno, rule)
  }
  END{
    printf "{\n  \"count\": %d,\n  \"findings\": [", n
    for(i=0;i<n;i++) printf "%s\n%s", (i?",":""), item[i]
    printf "%s  ]\n}\n", (n?"\n":"")
  }
' > "$OUT" 2>/dev/null

# Guarantee the contract output exists even if awk produced nothing (e.g. odd locale/IO error).
[ -s "$OUT" ] || printf '{\n  "count": 0,\n  "findings": []\n}\n' > "$OUT"

COUNT="$(grep -c '"rule":' "$OUT" 2>/dev/null || true)"
: "${COUNT:=0}"
printf '{"tool":"sec_secrets","status":"ok","findings":%s,"report":"%s"}\n' "$COUNT" "$OUT"
