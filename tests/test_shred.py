"""Crypto-shredding for Ledger-v2 records (P1-T07): destroy a record's DEK and its subject fields become
unrecoverable while the prev-hash chain still verifies and every other record is unaffected."""
from __future__ import annotations

import base64
import json

import pytest
from cryptography.exceptions import InvalidTag

from infra.cwp import shred


def test_erasure_drill_holds():
    r = shred.erasure_drill()
    assert r["ok"], r
    assert r["chain_verifies_before"] and r["chain_verifies_after_shred"]   # shred the key, not the chain
    assert r["shredded_unrecoverable"]                                      # the erased subject can't be read
    assert r["others_recoverable"] and r["nonsubject_unaffected"]          # everyone else is untouched


def test_seal_open_roundtrip():
    kr = shred.Keyring()
    dek = shred.new_dek()
    kr.put("d1", dek)
    sealed = shred.seal_fields({"name": "alice", "email": "a@x", "amount": 5}, ("name", "email"), dek, "d1")
    assert "_sealed" in sealed["name"] and sealed["amount"] == 5             # subject sealed, rest in clear
    opened = shred.open_fields(sealed, ("name", "email"), kr)
    assert opened["name"] == "alice" and opened["email"] == "a@x"


def test_destroyed_dek_makes_fields_unrecoverable():
    kr = shred.Keyring()
    dek = shred.new_dek()
    kr.put("d1", dek)
    sealed = shred.seal_fields({"name": "bob"}, ("name",), dek, "d1")
    kr.destroy("d1")
    with pytest.raises(shred.Shredded):
        shred.open_fields(sealed, ("name",), kr)


def test_tampered_ciphertext_is_rejected():
    kr = shred.Keyring()
    dek = shred.new_dek()
    kr.put("d1", dek)
    sealed = shred.seal_fields({"name": "carol"}, ("name",), dek, "d1")
    raw = bytearray(base64.b64decode(sealed["name"]["_sealed"]))
    raw[-1] ^= 0x01                                                          # flip a ciphertext bit
    sealed["name"]["_sealed"] = base64.b64encode(bytes(raw)).decode()
    with pytest.raises(InvalidTag):
        shred.open_fields(sealed, ("name",), kr)


def test_aad_binds_dek_id_so_ciphertext_cannot_be_moved():
    kr = shred.Keyring()
    dek = shred.new_dek()
    kr.put("d1", dek)
    kr.put("d2", dek)                                                        # same key, different id
    sealed = shred.seal_fields({"name": "dave"}, ("name",), dek, "d1")
    sealed["_dek"] = "d2"                                                    # relabel — AAD no longer matches
    with pytest.raises(InvalidTag):
        shred.open_fields(sealed, ("name",), kr)
