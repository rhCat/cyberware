"""External-truth conformance — canonical.py must reproduce the PUBLISHED cyberphone/json-canonicalization
reference vectors byte-for-byte (P0-T02). These are the RFC 8785 author's own input/output pairs, vendored
under spec/vectors/published/ and folded into corpus.json with their `expected` output. Python-only +
always-on, so the published-corpus conformance is gated on every push (the Go side is in test_crosslang)."""
import json
import os

from infra.cwp import canonical as c

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CORPUS = os.path.join(ROOT, "spec", "vectors", "corpus.json")


def test_canonical_reproduces_published_reference_vectors():
    corpus = json.load(open(CORPUS))
    published = [v for v in corpus if "expected" in v]
    assert len(published) >= 6, "the published reference vectors should be folded into the corpus"
    for v in published:
        assert c.canonicalize(v["input"]) == v["expected"], f"{v['name']}: != published output"
