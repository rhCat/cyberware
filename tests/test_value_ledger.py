"""Tier-2 value ledger (docs/pg-provenance-ledger.md): envelope encryption + the backend run_values table +
the mirror op. Proves the load-bearing invariants: values are ciphertext-at-rest, the `values_sha` commitment
is over PLAINTEXT, a non-recipient cannot open a blob, tampering is caught, and a fleet re-wrap adds a
recipient without re-encrypting. Hermetic — no server, no Postgres."""
import json
import os
import tempfile

import pytest

from infra.store import valuecrypt as vc
from infra.store.backend import PsycopgBackend, SqliteWalBackend
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.x25519 import X25519PrivateKey


def _node_key(d):
    kf = os.path.join(d, ".value-key")
    return kf, vc.generate_node_key(kf)


def test_keygen_is_0600_and_idempotent():
    d = tempfile.mkdtemp()
    kf, pub = _node_key(d)
    assert oct(os.stat(kf).st_mode)[-3:] == "600"
    assert vc.generate_node_key(kf) == pub          # existing key loaded, never overwritten


def test_commitment_is_over_plaintext_not_ciphertext():
    d = tempfile.mkdtemp()
    _, pub = _node_key(d)
    vals = {"SOURCE": "/repos/curl", "LIMIT": "50"}
    blob = vc.encrypt(vals, [pub])
    assert blob["sha"] == vc.values_sha(vals)       # commitment == sha256(canonical plaintext)
    # two encryptions of the same values differ (fresh nonce/DEK) yet share the plaintext commitment
    blob2 = vc.encrypt(vals, [pub])
    assert blob["ct"] != blob2["ct"] and blob["sha"] == blob2["sha"]


def test_ciphertext_carries_no_plaintext():
    d = tempfile.mkdtemp()
    _, pub = _node_key(d)
    blob = vc.encrypt({"SOURCE": "/secret/path/xyzzy", "TOKEN_FILE": "/k"}, [pub])
    assert b"xyzzy" not in json.dumps(blob).encode()


def test_roundtrip_and_nonrecipient_refused():
    d = tempfile.mkdtemp()
    kf, pub = _node_key(d)
    vals = {"A": "1", "B": "two"}
    blob = vc.encrypt(vals, [pub])
    assert vc.decrypt(blob, vc.load_private(kf)) == vals
    stranger = X25519PrivateKey.generate()
    with pytest.raises(ValueError):
        vc.decrypt(blob, stranger)


def test_tamper_is_caught():
    d = tempfile.mkdtemp()
    kf, pub = _node_key(d)
    blob = vc.encrypt({"A": "1"}, [pub])
    bad = dict(blob)
    bad["ct"] = "00" * (len(bytes.fromhex(blob["ct"])))
    with pytest.raises(Exception):
        vc.decrypt(bad, vc.load_private(kf))


def test_rewrap_adds_recipient_without_reencrypting():
    d = tempfile.mkdtemp()
    kf, pub = _node_key(d)
    vals = {"SOURCE": "/r"}
    blob = vc.encrypt(vals, [pub])
    sk = vc.load_private(kf)
    moth = X25519PrivateKey.generate()
    mpub = moth.public_key().public_bytes(serialization.Encoding.Raw, serialization.PublicFormat.Raw)
    blob2 = vc.rewrap(blob, sk, [mpub])
    assert blob2["ct"] == blob["ct"]                # data NOT re-encrypted, only a wrap added
    assert vc.decrypt(blob2, sk) == vals            # original recipient still opens it
    assert vc.decrypt(blob2, moth) == vals          # new recipient opens it too


def test_empty_recipient_set_rejected():
    with pytest.raises(ValueError):
        vc.encrypt({"A": "1"}, [])


def test_backend_run_values_upsert_and_isolation():
    d = tempfile.mkdtemp()
    be = SqliteWalBackend(os.path.join(d, "idx.sqlite")).open()
    kf, pub = _node_key(d)
    blob = vc.encrypt({"SOURCE": "/r", "LIMIT": "9"}, [pub])
    assert be.record_values("run1", "1", "t0", blob["sha"], blob)["status"] == "indexed"
    assert be.record_values("run1", "1", "t0", blob["sha"], blob)["status"] == "duplicate"
    rows = be.get_values("run1")
    assert [r["values_sha"] for r in rows] == [blob["sha"]]
    assert vc.decrypt(rows[0]["blob"], vc.load_private(kf)) == {"SOURCE": "/r", "LIMIT": "9"}
    assert be.get_values("other") == []
    be.reset()
    assert be.get_values("run1") == []              # reset drops the tier-2 table too


def test_pg_backend_inert_until_configured():
    pg = PsycopgBackend({})
    assert pg.record_values("r", "1", "t", "s", {})["status"] == "unconfigured"
    assert pg.get_values("r") == []
