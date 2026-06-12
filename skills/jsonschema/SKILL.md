---
skill: jsonschema
name: JSON Schema
perks: [validate, infer]
---

# jsonschema — JSON Schema

Validate a JSON file against a JSON Schema, or infer a schema from a JSON sample. Read-only,
pure-stdlib Python cores behind thin `.sh` porters — they run anywhere `python3` is present.

## What to look out for
Each tool emits one line of structured JSON (the audit + debug log) and writes its
artifact under `record_store`. LOGS TO CHECK: that line + the named report + the executor run-ledger.

## Perks
| perk | tool | nature |
|---|---|---|
| `validate` | `js_validate` | read-only / safe |
| `infer` | `js_infer` | read-only / safe |

- **`validate`** — check `DATA_FILE` against `SCHEMA_FILE`. Prefers the `jsonschema` library
  (`Draft7Validator`); when it is absent, falls back to a minimal built-in validator (top-level `type`,
  `required` keys, and each declared `properties[k].type`). Always writes `validation.json` with
  `{valid, errors, validator}`.
- **`infer`** — read `DATA_FILE` and emit an inferred JSON Schema (objects → `properties` + `required`,
  arrays → `items`, scalars → `type`), recursively. Always writes `schema.json`.

## How to use it
Pick a perk, copy `ledger.json` → `task-ledger.json`, fill its vars + `record_store`, then
validate → compose → compile → oversight → executor.
