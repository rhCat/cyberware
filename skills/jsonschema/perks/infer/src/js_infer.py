#!/usr/bin/env python3
"""js_infer — infer a JSON Schema from a JSON sample. Read-only.

Reads DATA_FILE, RECORD_STORE from the environment; ALWAYS writes schema.json and prints one
structured-JSON line (the audit/debug log). Pure stdlib — no required third-party import.

Inference rules (recursive):
  object -> {type: object, properties: {k: infer(v)}, required: [all keys]}
  array  -> {type: array, items: infer(first element)}  (empty array -> bare {type: array})
  scalar -> {type: <string|number|integer|boolean|null>}
"""
from __future__ import annotations

import json
import os
import sys


def _scalar_type(value) -> str:
    """JSON Schema type name for a scalar value (bool checked before int)."""
    if value is None:
        return "null"
    if isinstance(value, bool):
        return "boolean"
    if isinstance(value, int):
        return "integer"
    if isinstance(value, float):
        return "number"
    return "string"


def infer(value) -> dict:
    """Recursively infer a JSON Schema fragment for `value`."""
    if isinstance(value, dict):
        return {
            "type": "object",
            "properties": {k: infer(v) for k, v in value.items()},
            "required": list(value.keys()),
        }
    if isinstance(value, list):
        schema: dict = {"type": "array"}
        if value:
            schema["items"] = infer(value[0])
        return schema
    return {"type": _scalar_type(value)}


def main() -> int:
    """Infer a JSON Schema from DATA_FILE; always write schema.json."""
    data_file = os.environ["DATA_FILE"]
    store = os.environ["RECORD_STORE"].rstrip("/")
    out = os.path.join(store, "schema.json")

    with open(data_file, encoding="utf-8") as fh:
        data = json.load(fh)

    schema = infer(data)
    with open(out, "w", encoding="utf-8") as fh:
        json.dump(schema, fh, indent=2)

    print(json.dumps({"tool": "js_infer", "status": "ok", "schema": out}))
    return 0


if __name__ == "__main__":
    sys.exit(main())
