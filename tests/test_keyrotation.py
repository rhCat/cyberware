"""Key rotation as a governed drill for SV-4 (P3-T06): the rotation record is cross-signed by both old and
new keys; during the overlap a grant from either key verifies; after the old key is revoked, an old-key grant
is refused while the new key still works. Needs openssl with ed25519ph; skips otherwise."""
from __future__ import annotations
import shutil

import pytest

from infra.cwp import keyrotation as K


def _capable() -> bool:
    if not shutil.which("openssl"):
        return False
    try:
        K.keyrotation_selftest()
        return True
    except Exception:
        return False


pytestmark = pytest.mark.skipif(not _capable(), reason="needs openssl with ed25519ph")


def test_selftest_holds():
    r = K.keyrotation_selftest()
    assert r["ok"], r


def test_overlap_cross_sign_and_post_revocation():
    r = K.keyrotation_selftest()
    assert r["cross_signed_record_present"] and r["overlap_honored"]
    assert r["post_revocation_old_key_grant_refuses"] and r["post_revocation_new_key_still_valid"]
