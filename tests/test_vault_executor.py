"""P2-T05 double-blind secrets (infra/exec/vault.py) + P2-T12 govd-as-executor (infra/govern/govd_executor.py)
— the agent-mode keystone: the cortex holds names, the kernel holds the bytes and the limb."""
from __future__ import annotations

from infra.exec import vault
from infra.govern import govd_executor


def test_vault_double_blind_secrets():
    r = vault.vault_selftest()
    assert r["ok"] is True, r
    assert r["both_backends_one_contract"] is True
    assert r["agent_zero_secret_bytes"] is True and r["step_side_injection"] is True
    assert r["leak_caught"] is True and r["star_file_deprecated"] is True


def test_govd_as_executor_agent_holds_no_limb():
    r = govd_executor.govd_executor_selftest()
    assert r["ok"] is True, r
    assert r["agent_claim_zero_secret"] is True and r["agent_holds_no_limb"] is True
    assert r["info_only_return"] is True and r["faithful_uid"] is True
    assert r["agent_zero_secret_bytes"] is True
