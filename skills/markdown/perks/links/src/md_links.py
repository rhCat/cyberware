#!/usr/bin/env python3
"""md_links — find dead RELATIVE links in a Markdown file.

Reads MD_FILE and RECORD_STORE from the environment; writes link_report.json and prints one
structured-JSON line (the audit/debug log). Read-only: it never modifies MD_FILE.

Finds inline links of the form [text](target). Only RELATIVE targets are checked — links that start
with http://, https://, or mailto:, and pure #anchor links, are skipped. For a relative target any
#fragment is stripped, the path is resolved against os.path.dirname(MD_FILE), and its existence is
checked. The report is ALWAYS written: {"checked": N, "dead": [...], "ok": M}.
"""
from __future__ import annotations
import json
import os
import re
import sys

# [text](target) — text has no closing ']'; target is everything up to the matching ')'.
LINK = re.compile(r"\[([^\]]*)\]\(([^)]*)\)")
SKIP_PREFIXES = ("http://", "https://", "mailto:")


def is_relative(target: str) -> bool:
    """True only for links we should resolve on disk (skip web/mail schemes and pure #anchors)."""
    if not target or target.startswith("#"):
        return False
    return not target.lower().startswith(SKIP_PREFIXES)


def main() -> int:
    """Check every relative inline link and record the dead ones."""
    md_file = os.environ["MD_FILE"]
    store = os.environ["RECORD_STORE"].rstrip("/")
    out = os.path.join(store, "link_report.json")
    os.makedirs(store, exist_ok=True)
    base = os.path.dirname(os.path.abspath(md_file))

    text = open(md_file, encoding="utf-8", errors="replace").read()
    checked = 0
    dead = []
    for m in LINK.finditer(text):
        label, target = m.group(1).strip(), m.group(2).strip()
        # a markdown target may carry a title: (path "title") — the path is the first token
        path_part = target.split()[0] if target else ""
        if not is_relative(path_part):
            continue
        checked += 1
        rel = path_part.split("#", 1)[0]            # drop any #fragment
        if not rel:                                 # was something like (#) — nothing to resolve
            continue
        resolved = os.path.normpath(os.path.join(base, rel))
        if not os.path.exists(resolved):
            dead.append({"text": label, "target": target})

    report = {"checked": checked, "dead": dead, "ok": checked - len(dead)}
    with open(out, "w", encoding="utf-8") as fh:
        json.dump(report, fh, indent=2)

    print(json.dumps({"tool": "md_links", "status": "ok", "dead": len(dead), "report": out}))
    return 0


if __name__ == "__main__":
    sys.exit(main())
