"""Repatriating the ancestor for SV-6 (P6-T19): a verified-tier publish pays a royalty to the alchemy lineage
through the reward ledger (balanced); a subject alchemy blocks pays nothing. Needs the pinned alchemy engine;
skips otherwise."""
from __future__ import annotations

import pytest

from infra.cwp import alchemy
from infra.settle import royalties as R

pytestmark = pytest.mark.skipif(not alchemy.tools_present(), reason="needs the pinned alchemy/putrefactio engine")


def test_selftest():
    r = R.royalty_selftest()
    assert r["ok"], r
    assert r["verified_publish_pays_lineage"] and r["blocked_subject_pays_nothing"]
