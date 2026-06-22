"""P6-T06 money↔work cross-check (infra/settle/reward_verify.py).

The reward ledger conserves value internally (P6-T02); reward_verify adds the cross-plane invariant that the
MONEY trail (settlements) and the WORK trail (dual-signed, quote-bound receipts) cannot drift silently. These
tests pin the bijection + that BOTH drift directions are caught. Needs openssl (ed25519ph receipts)."""
from __future__ import annotations

import shutil

import pytest

from infra.settle import reward_verify

pytestmark = pytest.mark.skipif(shutil.which("openssl") is None, reason="needs openssl (ed25519ph receipts)")


def test_reward_verify_selftest_clean_and_discriminates_both_directions():
    r = reward_verify.reward_verify_selftest()
    assert r["ok"] is True, r
    assert r["clean_bijection"] is True and r["settlements"] == 3
    assert r["money_without_work_caught"] is True      # a settlement with no authorizing receipt is flagged
    assert r["work_without_money_caught"] is True       # an authorized receipt never settled is flagged
