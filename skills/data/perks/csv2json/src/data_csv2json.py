#!/usr/bin/env python3
"""data_csv2json — convert a CSV file to a JSON array of row objects. Reads CSV_FILE, RECORD_STORE from env."""
from __future__ import annotations
import csv
import json
import os
import sys


def main() -> int:
    """Read CSV_FILE and write data.json."""
    src = os.environ["CSV_FILE"]
    store = os.environ["RECORD_STORE"].rstrip("/")
    out = os.path.join(store, "data.json")
    with open(src, newline="", encoding="utf-8") as f:
        rows = list(csv.DictReader(f))
    json.dump(rows, open(out, "w"), indent=2)
    cols = list(rows[0].keys()) if rows else []
    print(json.dumps({"tool": "data_csv2json", "status": "ok", "rows": len(rows), "columns": cols, "out": out}))
    return 0


if __name__ == "__main__":
    sys.exit(main())
