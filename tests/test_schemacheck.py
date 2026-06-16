"""CWP message-schema conformance (P0-T05): the 2020-12 schemas accept every valid CWP instance (100%) and
reject every negative one, and the schemas are themselves valid 2020-12 documents."""
from __future__ import annotations
import glob
import json
import os

from jsonschema import Draft202012Validator

from infra.cwp import schemacheck

SCHEMAS = schemacheck.DEFAULT_SCHEMAS


def test_every_schema_is_a_valid_2020_12_document():
    files = glob.glob(os.path.join(SCHEMAS, "*.schema.json"))
    assert files, "no schemas found"
    for f in files:
        Draft202012Validator.check_schema(json.load(open(f)))   # raises if the schema is malformed


def test_valid_corpus_validates_100_percent_and_negatives_are_rejected():
    r = schemacheck.check_corpus()
    assert r["ok"], r["failures"]
    assert r["coverage"] == 1.0
    assert r["valid_passed"] == r["valid_total"] and r["valid_total"] >= 9
    assert r["invalid_rejected"] == r["invalid_total"] and r["invalid_total"] >= 1


def test_a_value_in_a_claim_body_is_refused():
    # the value-free-body invariant, machine-checkable: a claim carrying a value (not a key) fails its schema
    v = Draft202012Validator(json.load(open(os.path.join(SCHEMAS, "claim.schema.json"))))
    bad = {"cwp": "1.0", "type": "claim",
           "body": {"skill": "x", "perk": "y", "var_keys": ["K"], "K": "secret-value"},
           "sig": {"keyid": "ed25519:0123456789abcdef", "sig": "z"}}
    assert list(v.iter_errors(bad)), "a value in the claim body must be rejected"
