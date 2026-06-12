#!/usr/bin/env python3
"""js_validate — validate a JSON file against a JSON Schema. Read-only.

Reads DATA_FILE, SCHEMA_FILE, RECORD_STORE from the environment; ALWAYS writes validation.json
and prints one structured-JSON line (the audit/debug log).

Prefers the `jsonschema` library (Draft7Validator). When it is not importable, falls back to a
MINIMAL pure-stdlib validator covering: top-level `type`, `required` keys present, and each declared
`properties[k].type`. No required third-party import — runs anywhere python3 is present.
"""
from __future__ import annotations

import json
import os
import sys

# JSON Schema "type" name -> Python type(s). "integer" excludes bool (which is an int subclass).
_PYTYPES = {
    "object": dict,
    "array": list,
    "string": str,
    "number": (int, float),
    "integer": int,
    "boolean": bool,
    "null": type(None),
}


def _type_ok(value, declared: str) -> bool:
    """True if `value` matches the JSON Schema `type` name `declared` (builtin fallback)."""
    py = _PYTYPES.get(declared)
    if py is None:
        return True  # unknown/unsupported type keyword — the builtin path does not judge it
    if declared == "boolean":
        return isinstance(value, bool)
    # bool is a subclass of int — keep it out of number/integer
    if declared in ("number", "integer") and isinstance(value, bool):
        return False
    return isinstance(value, py)


def _builtin_validate(data, schema) -> list:
    """Minimal stdlib validator: top-level type, required keys, declared properties[k].type."""
    errors: list = []
    if not isinstance(schema, dict):
        return errors
    top = schema.get("type")
    if isinstance(top, str) and not _type_ok(data, top):
        errors.append({"path": "", "message": f"expected type '{top}', got {type(data).__name__}"})
        # if the top-level shape is already wrong, deeper checks are not meaningful
        return errors
    for key in schema.get("required", []) or []:
        if isinstance(data, dict) and key not in data:
            errors.append({"path": key, "message": f"required property '{key}' is missing"})
    props = schema.get("properties") or {}
    if isinstance(data, dict) and isinstance(props, dict):
        for key, subschema in props.items():
            if key not in data or not isinstance(subschema, dict):
                continue
            declared = subschema.get("type")
            if isinstance(declared, str) and not _type_ok(data[key], declared):
                errors.append({"path": key, "message": f"expected type '{declared}', got {type(data[key]).__name__}"})
    return errors


def main() -> int:
    """Validate DATA_FILE against SCHEMA_FILE; always write validation.json."""
    data_file = os.environ["DATA_FILE"]
    schema_file = os.environ["SCHEMA_FILE"]
    store = os.environ["RECORD_STORE"].rstrip("/")
    out = os.path.join(store, "validation.json")

    with open(data_file, encoding="utf-8") as fh:
        data = json.load(fh)
    with open(schema_file, encoding="utf-8") as fh:
        schema = json.load(fh)

    try:
        import jsonschema  # type: ignore

        validator = jsonschema.Draft7Validator(schema)
        errors = [
            {"path": "/".join(str(p) for p in err.absolute_path), "message": err.message}
            for err in sorted(validator.iter_errors(data), key=lambda e: list(e.absolute_path))
        ]
        used = "jsonschema"
    except ImportError:
        errors = _builtin_validate(data, schema)
        used = "builtin"

    result = {"valid": not errors, "errors": errors, "validator": used}
    with open(out, "w", encoding="utf-8") as fh:
        json.dump(result, fh, indent=2)

    print(json.dumps({"tool": "js_validate", "status": "ok", "valid": not errors, "report": out}))
    return 0


if __name__ == "__main__":
    sys.exit(main())
