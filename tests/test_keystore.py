"""KeyStore adapter seam (P0-T15): both backends satisfy one contract suite, the file backend really
persists (the seam is not in-memory), and the PKCS#11 stub holds non-exportable keys."""
from __future__ import annotations

import pytest

from infra.cwp import keystore as K


@pytest.mark.parametrize("factory", [
    lambda d: K.FileKeyStore(str(d)),
    lambda d: K.SoftPkcs11KeyStore(),
], ids=["file", "pkcs11"])
def test_backend_satisfies_the_contract(tmp_path, factory):
    report = K.contract_suite(factory(tmp_path))
    assert report["ok"], report


def test_drill_holds():
    import tempfile
    r = K.keystore_drill(tempfile.mkdtemp())
    assert r["ok"], r
    assert r["both_backends_pass"] and r["seam_real"] and r["hsm_key_nonexportable"]


def test_file_backend_persists_across_instances(tmp_path):
    a = K.FileKeyStore(str(tmp_path))
    kid = a.generate("k1")
    b = K.FileKeyStore(str(tmp_path))                     # fresh instance, same dir
    assert b.has("k1") and b.keyid("k1") == kid
    sig = b.sign("k1", b"hello")                          # and can still sign with the persisted key
    assert a.verify("k1", b"hello", sig)


def test_pkcs11_private_key_is_non_exportable():
    p = K.SoftPkcs11KeyStore()
    p.generate("hsm-key")
    assert not any(hasattr(p, m) for m in ("export_private", "private_bytes", "private_key"))


def test_signatures_are_interchangeable_across_the_seam(tmp_path):
    # the same message signed by either backend verifies under that backend's public — one surface
    for ks in (K.FileKeyStore(str(tmp_path / "f")), K.SoftPkcs11KeyStore()):
        ks.generate("x")
        sig = ks.sign("x", b"m")
        assert ks.verify("x", b"m", sig)
        with pytest.raises(Exception):
            ks.verify("x", b"tampered", sig)
