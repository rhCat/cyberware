"""The no-root execution gate (infra/govern/executor.noroot_gate).

Faithful execution requires a NON-ROOT identity — the user's own uid or a scoped agent assumed-role — never
ambient root. These tests exercise BOTH branches (root refused / non-root allowed) so the gate's mutants
(`== 0`, the exit code, the recorded refusal) are killed — the executor is a ratchet-tracked enforcement
surface.
"""
import json

import pytest

from infra.govern.executor import noroot_gate


def test_noroot_gate_refuses_root(tmp_path):
    lpath = tmp_path / "run-ledger.json"
    ledger = {"runs": []}
    with pytest.raises(SystemExit) as e:
        noroot_gate(0, ledger, str(lpath))            # root -> REFUSED
    assert e.value.code == 9                            # the no-root exit code
    assert ledger["runs"][-1]["event"] == "root_refused"
    assert ledger["runs"][-1]["euid"] == 0
    # the refusal is recorded to disk as evidence, not just in memory
    assert json.load(open(lpath))["runs"][-1]["event"] == "root_refused"


def test_noroot_gate_allows_nonroot(tmp_path):
    lpath = tmp_path / "run-ledger.json"
    for euid in (1000, 65534, 501):                     # user / nobody / a typical macOS uid -> allowed
        ledger = {"runs": []}
        noroot_gate(euid, ledger, str(lpath))           # no raise — execution proceeds
        assert ledger["runs"] == []                      # non-root path records nothing and runs onward
