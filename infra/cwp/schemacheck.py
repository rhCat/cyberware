#!/usr/bin/env python3
"""infra/cwp/schemacheck.py — CWP message-schema conformance (P0-T05).

Validates a corpus of CWP message instances against the JSON Schemas (2020-12) under spec/schemas/. The
acceptance is two-sided: every VALID instance must validate against its type's schema (100%), and every
NEGATIVE instance — a value smuggled into a claim body, a grant missing its nonce, an unknown envelope type
— must be REJECTED (so the schemas discriminate, not merely accept). Each instance is matched to its schema
by its declared `type` (an unknown type is checked against the generic envelope, whose closed `type` enum
refuses it).
"""
from __future__ import annotations
import json
import os

from jsonschema import Draft202012Validator

DEFAULT_SCHEMAS = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),
                               "spec", "schemas")


def _validator(schemas_dir: str, type_: str) -> Draft202012Validator:
    path = os.path.join(schemas_dir, f"{type_}.schema.json")
    if not os.path.isfile(path):                       # an unknown type falls back to the generic envelope
        path = os.path.join(schemas_dir, "envelope.schema.json")
    return Draft202012Validator(json.load(open(path)))


def _errors(schemas_dir, item):
    inst = json.load(open(os.path.join(schemas_dir, "instances", item["file"])))
    return [e.message for e in _validator(schemas_dir, item["type"]).iter_errors(inst)]


def check_corpus(schemas_dir: str = DEFAULT_SCHEMAS) -> dict:
    """Validate spec/schemas/instances/corpus.json. Returns a report; `ok` is True iff every valid instance
    passes AND every invalid instance is rejected."""
    corpus = json.load(open(os.path.join(schemas_dir, "instances", "corpus.json")))
    r = {"valid_passed": 0, "valid_total": 0, "invalid_rejected": 0, "invalid_total": 0, "failures": []}
    for item in corpus.get("valid", []):
        r["valid_total"] += 1
        errs = _errors(schemas_dir, item)
        if errs:
            r["failures"].append({"file": item["file"], "expected": "valid", "errors": errs[:3]})
        else:
            r["valid_passed"] += 1
    for item in corpus.get("invalid", []):
        r["invalid_total"] += 1
        if _errors(schemas_dir, item):
            r["invalid_rejected"] += 1
        else:
            r["failures"].append({"file": item["file"], "expected": "rejected", "errors": ["validated but should not"]})
    r["coverage"] = round(r["valid_passed"] / r["valid_total"], 4) if r["valid_total"] else 0.0
    r["ok"] = (r["valid_passed"] == r["valid_total"] and r["valid_total"] > 0
               and r["invalid_rejected"] == r["invalid_total"] and not r["failures"])
    return r


if __name__ == "__main__":
    import sys
    print(json.dumps(check_corpus(), indent=2))
    sys.exit(0 if check_corpus()["ok"] else 1)
