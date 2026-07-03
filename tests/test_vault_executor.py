"""P2-T05 double-blind secrets (infra/exec/vault.py) + P2-T12 govd-as-executor (infra/govern/govd_executor.py)
— the agent-mode keystone: the cortex holds names, the kernel holds the bytes and the limb."""
from __future__ import annotations

import json
import os

import pytest

from infra.exec import vault
from infra.govern import govd_executor


def test_vault_double_blind_secrets():
    r = vault.vault_selftest()
    assert r["ok"] is True, r
    assert r["both_backends_one_contract"] is True
    assert r["agent_zero_secret_bytes"] is True and r["step_side_injection"] is True
    assert r["leak_caught"] is True and r["star_file_deprecated"] is True


def test_filevault_enforces_0600_fail_closed(tmp_path):
    """The 0600 confidentiality is ENFORCED, not documentation-only: a group/other-accessible secrets store is
    refused at read time (fail-closed), and tightening it to 0600 lets the credential resolve."""
    p = tmp_path / "secrets.json"
    p.write_text(json.dumps({"api-key": "S3CR3T"}))
    v = vault.FileVault(str(p))
    os.chmod(p, 0o644)                                        # world-readable — a secrets store must not be
    with pytest.raises(PermissionError):
        v.get("api-key")
    os.chmod(p, 0o640)                                        # group-readable is still refused
    with pytest.raises(PermissionError):
        v.get("api-key")
    os.chmod(p, 0o600)                                        # 0600 -> resolves
    assert v.get("api-key") == "S3CR3T"


def test_govd_as_executor_agent_holds_no_limb():
    r = govd_executor.govd_executor_selftest()
    assert r["ok"] is True, r
    assert r["agent_claim_zero_secret"] is True and r["agent_holds_no_limb"] is True
    assert r["info_only_return"] is True and r["faithful_uid"] is True
    assert r["agent_zero_secret_bytes"] is True
