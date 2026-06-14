"""Cross-language anchor for the Ledger-v2 cryptographic chain (P1-T04, meta-rule M3 / SV-2).

The independent Go chain verifier (`verifiers/go chain`) MUST reproduce `infra/cwp/ledger.py verify_chain`
verdict-for-verdict — over sound chains, single-bit tampers, genesis transplants, deleted-record seq gaps,
headless chains, AND the live `done-ledger-v2.json`. Two implementations written from the same rules
agreeing on every chain is the evidence that the chain is independently re-verifiable, not merely trusted.
Skipped where the Go toolchain is absent (the codeqc CI job installs it / the compute image ships it).
"""
import copy
import json
import os
import shutil
import subprocess
import tempfile

import pytest

from infra.cwp import ledger as L

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
GO_DIR = os.path.join(ROOT, "verifiers", "go")
DONE_V2 = os.path.join(ROOT, "workzone", "version1.1", "cyberware-swarm-v1.1", "done-ledger-v2.json")

pytestmark = pytest.mark.skipif(shutil.which("go") is None, reason="requires the go toolchain")


def _build_go():
    binp = os.path.join(tempfile.mkdtemp(prefix="chain-"), "jcs")
    b = subprocess.run(["go", "build", "-o", binp, "."], cwd=GO_DIR, capture_output=True, text=True)
    assert b.returncode == 0, f"go build failed:\n{b.stderr}"
    return binp


def _sound():
    c = [L.genesis("run-A", "plan-1")]
    L.append(c, {"task_id": "T1", "verdict": "pass", "evidence_sha": "a"})
    L.append(c, {"task_id": "T2", "verdict": "pass", "evidence_sha": "b"})
    return c


def test_go_chain_anchor_reproduces_python_verify_chain():
    binp = _build_go()
    sound = _sound()
    tamper = copy.deepcopy(sound)
    tamper[1]["evidence_sha"] = "MUTATED"
    delgap = copy.deepcopy(sound)
    del delgap[1]
    delgap[1]["prev"] = L.link_digest(L.link_of(delgap[0]), 2)        # seqs 0,2
    headless = [{"type": "step", "task_id": "evil", "seq": 0, "prev": L.ZERO}]
    L.append(headless, {"task_id": "evil2"})
    real, _ = L.read_chain(DONE_V2)

    corpus = [
        {"name": "sound", "schema": 2, "entries": sound, "expect_run_id": "run-A", "expect_plan_sha": "plan-1"},
        {"name": "tamper", "schema": 2, "entries": tamper},
        {"name": "transplant", "schema": 2, "entries": sound, "expect_run_id": "IMPOSTOR", "expect_plan_sha": "x"},
        {"name": "deletion-gap", "schema": 2, "entries": delgap},
        {"name": "headless", "schema": 2, "entries": headless},
        {"name": "real-done-ledger-v2", "schema": 2, "entries": real},
    ]
    go = {v["name"]: v for v in json.loads(
        subprocess.run([binp, "chain"], input=json.dumps(corpus), capture_output=True, text=True).stdout)}

    for c in corpus:
        py_ok, _ = L.verify_chain(c["entries"], 2, c.get("expect_run_id"), c.get("expect_plan_sha"))
        assert go[c["name"]]["ok"] == py_ok, f"{c['name']}: go={go[c['name']]} != py {py_ok}"
        if not py_ok:
            assert go[c["name"]]["problem"], f"{c['name']}: Go rejected but did not name the fault"
    # discrimination actually exercised — not "both always agree on ok"
    assert go["sound"]["ok"] and go["real-done-ledger-v2"]["ok"]
    assert not go["tamper"]["ok"] and not go["deletion-gap"]["ok"]
