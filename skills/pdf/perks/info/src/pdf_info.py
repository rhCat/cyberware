#!/usr/bin/env python3
"""pdf_info — read a PDF's page count + metadata to record_store (Python core of the `info` perk).

Reads PDF_FILE, RECORD_STORE from the environment; ALWAYS writes pdf_info.json and prints one
structured-JSON line (the audit/debug log). Tries poppler's `pdfinfo` (parsing its key: value text
into JSON), then pypdf (page count + document metadata); if neither is available (or both fail),
writes {"note": "no pdf tool available", "file": <path>}. Read-only: never modifies the source PDF.
"""
from __future__ import annotations
import json
import os
import shutil
import subprocess
import sys


def from_pdfinfo(pdf_file: str) -> dict | None:
    """Parse `pdfinfo`'s `Key: value` lines into a dict, or None if the binary is absent/fails."""
    if not shutil.which("pdfinfo"):
        return None
    try:
        proc = subprocess.run(["pdfinfo", pdf_file], capture_output=True, text=True, timeout=30)
    except Exception:
        return None
    if proc.returncode != 0:
        return None
    info: dict[str, str] = {}
    for line in proc.stdout.splitlines():
        if ":" in line:
            key, _, val = line.partition(":")
            info[key.strip()] = val.strip()
    return {"source": "pdfinfo", **info} if info else None


def from_pypdf(pdf_file: str) -> dict | None:
    """Read page count + document metadata via pypdf/PyPDF2, or None if unavailable/fails."""
    for mod in ("pypdf", "PyPDF2"):
        try:
            reader = __import__(mod).PdfReader(pdf_file)
        except Exception:
            continue
        try:
            meta = reader.metadata or {}
            return {
                "source": mod,
                "pages": len(reader.pages),
                "metadata": {str(k): str(v) for k, v in dict(meta).items()},
            }
        except Exception:
            continue
    return None


def main() -> int:
    """Gather PDF info, always writing pdf_info.json, and print the structured-JSON log line."""
    pdf_file = os.environ["PDF_FILE"]
    store = os.environ["RECORD_STORE"].rstrip("/")
    out = os.path.join(store, "pdf_info.json")
    info = from_pdfinfo(pdf_file) or from_pypdf(pdf_file) or {"note": "no pdf tool available", "file": pdf_file}
    with open(out, "w", encoding="utf-8") as fh:
        json.dump(info, fh, indent=2)
    print(json.dumps({"tool": "pdf_info", "status": "ok", "info": out}))
    return 0


if __name__ == "__main__":
    sys.exit(main())
