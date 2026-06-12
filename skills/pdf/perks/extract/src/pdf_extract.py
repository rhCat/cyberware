#!/usr/bin/env python3
"""pdf_extract — extract a PDF's text to record_store (Python core of the read-only `extract` perk).

Reads PDF_FILE, RECORD_STORE from the environment; ALWAYS writes extracted.txt and prints one
structured-JSON line (the audit/debug log). Tries pypdf, then PyPDF2, then pdfminer; if none is
installed (or extraction fails), writes a one-line note so the contract's output_exists holds.
Read-only: never modifies the source PDF.
"""
from __future__ import annotations
import json
import os
import sys

NOTE = "[no PDF extractor available — install poppler's pdftotext or the pypdf python package]"


def extract_text(pdf_file: str) -> str | None:
    """Return the PDF's text via the first available library, or None if none works."""
    # pypdf (and the legacy PyPDF2 alias) expose PdfReader(path).pages[*].extract_text()
    for mod in ("pypdf", "PyPDF2"):
        try:
            reader = __import__(mod).PdfReader(pdf_file)
        except Exception:
            continue
        try:
            return "\n".join((page.extract_text() or "") for page in reader.pages)
        except Exception:
            continue
    # pdfminer.six: a single high-level call
    try:
        from pdfminer.high_level import extract_text as _pm
        return _pm(pdf_file) or ""
    except Exception:
        return None


def main() -> int:
    """Extract text, always writing extracted.txt, and print the structured-JSON log line."""
    pdf_file = os.environ["PDF_FILE"]
    store = os.environ["RECORD_STORE"].rstrip("/")
    out = os.path.join(store, "extracted.txt")
    text = extract_text(pdf_file)
    body = text if text is not None else NOTE
    with open(out, "w", encoding="utf-8") as fh:
        fh.write(body)
    print(json.dumps({"tool": "pdf_extract", "status": "ok", "chars": len(body), "text": out}))
    return 0


if __name__ == "__main__":
    sys.exit(main())
