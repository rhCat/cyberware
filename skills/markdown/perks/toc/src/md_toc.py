#!/usr/bin/env python3
"""md_toc — generate a GitHub-style table of contents from a Markdown file's ATX headings.

Reads MD_FILE and RECORD_STORE from the environment; writes toc.md and prints one structured-JSON
line (the audit/debug log). Read-only: it never modifies MD_FILE.

ATX headings are lines matching ^#{1,6}\\s+ that are NOT inside a fenced (``` or ~~~) code block.
Each heading becomes `- [text](#slug)`, indented by (level-1)*2 spaces, where slug is GitHub-style:
lowercased, spaces → '-', then every character that is not alphanumeric or '-' is dropped.
toc.md is ALWAYS written — when there are no headings it gets a `<!-- no headings -->` note.
"""
from __future__ import annotations
import json
import os
import re
import sys

ATX = re.compile(r"^(#{1,6})\s+(.*?)\s*#*\s*$")
FENCE = re.compile(r"^\s*(```+|~~~+)")


def slugify(text: str) -> str:
    """GitHub-style anchor slug: lowercase, spaces → '-', drop non-alphanumeric-or-hyphen."""
    s = text.strip().lower().replace(" ", "-")
    return "".join(c for c in s if c.isalnum() or c == "-")


def headings(lines):
    """Yield (level, text) for each ATX heading, skipping any inside a fenced code block."""
    in_fence = False
    fence_marker = ""
    for line in lines:
        m = FENCE.match(line)
        if m:
            marker = m.group(1)[0]          # ` or ~
            if not in_fence:
                in_fence, fence_marker = True, marker
            elif marker == fence_marker:    # a fence closes only with its own marker kind
                in_fence, fence_marker = False, ""
            continue
        if in_fence:
            continue
        hm = ATX.match(line)
        if hm:
            text = hm.group(2).strip()
            yield len(hm.group(1)), text


def main() -> int:
    """Build the table of contents and write it to toc.md (always)."""
    md_file = os.environ["MD_FILE"]
    store = os.environ["RECORD_STORE"].rstrip("/")
    out = os.path.join(store, "toc.md")
    os.makedirs(store, exist_ok=True)

    text = open(md_file, encoding="utf-8", errors="replace").read()
    items = list(headings(text.splitlines()))

    if items:
        body = "\n".join(
            f"{'  ' * (level - 1)}- [{txt}](#{slugify(txt)})" for level, txt in items
        ) + "\n"
    else:
        body = "<!-- no headings -->\n"

    with open(out, "w", encoding="utf-8") as fh:
        fh.write(body)

    print(json.dumps({"tool": "md_toc", "status": "ok", "headings": len(items), "toc": out}))
    return 0


if __name__ == "__main__":
    sys.exit(main())
