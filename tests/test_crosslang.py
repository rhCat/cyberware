"""Cross-language conformance — the external anchor (meta-rule M3) for the canonical-bytes path.

The independent Go RFC 8785 implementation (`verifiers/go/`) MUST reproduce `infra/cwp/canonical.py`
byte-for-byte across the whole vector corpus (`spec/vectors/corpus.json`). Two implementations written
from the spec agreeing on every edge — number boundaries, UTF-16 key order, escaping, big-int exactness —
is the evidence that "cyberware is a specification, not a codebase". Skipped where the Go toolchain is
absent (the codeqc CI job installs it, so the anchor is gated there).
"""
import json
import os
import shutil
import subprocess
import tempfile

import pytest

from infra.cwp import canonical as c

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
GO_DIR = os.path.join(ROOT, "verifiers", "go")
CORPUS = os.path.join(ROOT, "spec", "vectors", "corpus.json")
SIG_CORPUS = os.path.join(ROOT, "spec", "vectors", "signatures.json")


def _build_go():
    binp = os.path.join(tempfile.mkdtemp(prefix="jcs-"), "jcs-verify")
    b = subprocess.run(["go", "build", "-o", binp, "."], cwd=GO_DIR, capture_output=True, text=True)
    assert b.returncode == 0, f"go build failed:\n{b.stderr}"
    return binp

# Known-correct outputs (external truth), hand-verified — so the anchor is not merely "two impls agree"
# but "both match the spec's prescribed bytes".
EXTERNAL_TRUTH = [
    ({"b": 1, "a": 2}, '{"a":2,"b":1}'),
    ([1, 2, 3], "[1,2,3]"),
    ({"x": [True, None, False]}, '{"x":[true,null,false]}'),
    (1e30, "1e+30"),
    (0.002, "0.002"),
    (1e21, "1e+21"),
    (1e20, "100000000000000000000"),
    ({"é": 1, "z": 2}, '{"z":2,"é":1}'),                  # 'é' (U+00E9) sorts AFTER 'z'
    (10 ** 30, "1000000000000000000000000000000"),         # big int — exact, never via float64
]


def test_canonical_py_matches_known_external_outputs():
    for inp, want in EXTERNAL_TRUTH:
        assert c.canonicalize(inp) == want, f"{inp!r} → {c.canonicalize(inp)!r} != {want!r}"


@pytest.mark.skipif(shutil.which("go") is None, reason="go toolchain absent")
def test_go_verifier_reproduces_canonical_py_byte_for_byte():
    binp = os.path.join(tempfile.mkdtemp(prefix="jcs-"), "jcs-verify")
    build = subprocess.run(["go", "build", "-o", binp, "."], cwd=GO_DIR, capture_output=True, text=True)
    assert build.returncode == 0, f"go build failed:\n{build.stderr}"

    with open(CORPUS) as f:
        corpus = json.load(f)
    run = subprocess.run([binp], stdin=open(CORPUS), capture_output=True, text=True)
    assert run.returncode == 0, f"go verifier failed:\n{run.stderr}"
    go_results = {r["name"]: r for r in json.loads(run.stdout)}

    assert len(go_results) == len(corpus) >= 200, "corpus shrank unexpectedly"
    mismatches = []
    for vec in corpus:
        name, inp = vec["name"], vec["input"]
        py_canon, py_digest = c.canonicalize(inp), c.digest(inp)
        go = go_results[name]
        if go["canonical"] != py_canon:
            mismatches.append(f"{name}: canonical Go={go['canonical']!r} Py={py_canon!r}")
        elif go["digest"] != py_digest:
            mismatches.append(f"{name}: digest Go={go['digest']} Py={py_digest}")
    assert not mismatches, "Go ≠ Py on:\n  " + "\n  ".join(mismatches[:20])


@pytest.mark.skipif(shutil.which("go") is None, reason="go toolchain absent")
def test_go_verifier_matches_known_external_outputs():
    binp = os.path.join(tempfile.mkdtemp(prefix="jcs-"), "jcs-verify")
    subprocess.run(["go", "build", "-o", binp, "."], cwd=GO_DIR, capture_output=True, text=True, check=True)
    corpus = [{"name": f"ext_{i}", "input": inp} for i, (inp, _) in enumerate(EXTERNAL_TRUTH)]
    run = subprocess.run([binp], input=json.dumps(corpus), capture_output=True, text=True)
    results = {r["name"]: r["canonical"] for r in json.loads(run.stdout)}
    for i, (_, want) in enumerate(EXTERNAL_TRUTH):
        assert results[f"ext_{i}"] == want, f"Go ext_{i}: {results[f'ext_{i}']!r} != {want!r}"


@pytest.mark.skipif(shutil.which("go") is None, reason="go toolchain absent")
def test_go_verifier_reproduces_dsse_sig_verdicts():
    """The sig-verdict half of the anchor: a DSSE/Ed25519 signature produced by infra/cwp/sign.py must
    verify identically in the independent Go implementation (Ed25519 is deterministic), and both must
    agree with each vector's declared verdict — including the tampered + wrong-key negatives."""
    pytest.importorskip("cryptography")
    import base64
    from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey
    from infra.cwp import sign

    vectors = json.load(open(SIG_CORPUS))
    binp = _build_go()
    run = subprocess.run([binp, "sig"], stdin=open(SIG_CORPUS), capture_output=True, text=True)
    assert run.returncode == 0, f"go sig verify failed:\n{run.stderr}"
    go = {r["name"]: r["valid"] for r in json.loads(run.stdout)}

    assert any(v["expect_valid"] for v in vectors) and any(not v["expect_valid"] for v in vectors)
    for v in vectors:
        name, want = v["name"], v["expect_valid"]
        pub = Ed25519PublicKey.from_public_bytes(base64.b64decode(v["pubkey"]))
        assert sign.verify(v["envelope"], pub) == want, f"py verdict {name}"   # Python agrees with the vector
        assert go[name] == want, f"go verdict {name}: {go[name]} != {want}"     # Go agrees with the vector (and Python)
