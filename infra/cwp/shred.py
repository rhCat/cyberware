#!/usr/bin/env python3
"""infra/cwp/shred.py — crypto-shredding for Ledger-v2 records (P1-T07).

The right-to-erasure made cryptographic: shred the key, not the chain. Each record's *subject* fields are
sealed with a per-record DEK (AES-256-GCM, the dek-id bound as AAD); the ledger stores **only the
ciphertext**, so the prev-hash chain covers the ciphertext and **still verifies** after a key is destroyed.
Destroying a record's DEK (dropping it from the keyring) makes that record's subject fields **permanently
unrecoverable**, while every other record — its own DEK intact — is **unaffected**. The chain stays a
faithful, verifiable record of *what happened*; the erased subject simply can no longer be read.
"""
from __future__ import annotations
import base64
import json
import os

from cryptography.exceptions import InvalidTag
from cryptography.hazmat.primitives.ciphers.aead import AESGCM

from infra.cwp import ledger
from infra.cwp.chainverify import CURRENT_MAJOR, verify_chain


def new_dek() -> bytes:
    """A fresh 256-bit data-encryption key."""
    return AESGCM.generate_key(bit_length=256)


def seal_fields(record: dict, subject_fields, dek: bytes, dek_id: str) -> dict:
    """Return a copy of `record` with each named subject field replaced by its ciphertext. The dek-id is
    recorded in `_dek` (so a reader knows which key) and bound as AAD (so the ciphertext cannot be moved to
    another record). The DEK itself is never stored in the record."""
    sealed = dict(record)
    sealed["_dek"] = dek_id
    aes = AESGCM(dek)
    aad = b"_dek=" + dek_id.encode()
    for f in subject_fields:
        if f in sealed and f != "_dek":
            nonce = os.urandom(12)
            ct = aes.encrypt(nonce, json.dumps(sealed[f]).encode(), aad)
            sealed[f] = {"_sealed": base64.b64encode(nonce + ct).decode()}
    return sealed


class Keyring:
    """dek-id → DEK. `destroy` crypto-shreds a record's subject fields by forgetting its key."""
    def __init__(self):
        self._k = {}

    def put(self, dek_id: str, dek: bytes):
        self._k[dek_id] = dek

    def get(self, dek_id: str):
        return self._k.get(dek_id)

    def destroy(self, dek_id: str):
        self._k.pop(dek_id, None)


def open_fields(sealed: dict, subject_fields, keyring: Keyring) -> dict:
    """Decrypt the subject fields of a sealed record. Raises `Shredded` if the record's DEK is gone, or
    InvalidTag if the ciphertext was tampered. A successful return reconstructs the original values."""
    dek = keyring.get(sealed.get("_dek"))
    if dek is None:
        raise Shredded(sealed.get("_dek"))
    aes = AESGCM(dek)
    aad = b"_dek=" + str(sealed.get("_dek")).encode()
    out = dict(sealed)
    for f in subject_fields:
        v = out.get(f)
        if isinstance(v, dict) and "_sealed" in v:
            raw = base64.b64decode(v["_sealed"])
            out[f] = json.loads(aes.decrypt(raw[:12], raw[12:], aad))
    return out


class Shredded(Exception):
    """Raised when a record's subject fields are requested but its DEK has been destroyed."""


def erasure_drill(n: int = 5, shred_index: int = 2, subject_fields=("name", "email")) -> dict:
    """The P1-T07 acceptance, demonstrated end to end: build a Ledger-v2 chain over n records whose subject
    fields are sealed per-record; verify the chain; destroy ONE record's DEK; then prove
      (1) the chain STILL verifies (the stored ciphertext is untouched),
      (2) the shredded record's subject fields are unrecoverable, and
      (3) every other record's subject fields are still recoverable (other queries unaffected).
    Returns a report; `ok` is True iff all three hold."""
    entries = [ledger.genesis("erasure-run", "erasure-plan")]
    keyring = Keyring()
    for i in range(n):
        dek_id = f"dek-{i}"
        dek = new_dek()
        keyring.put(dek_id, dek)
        rec = {"id": i, "name": f"subject-{i}", "email": f"s{i}@example.com", "amount": i * 10}
        ledger.append(entries, seal_fields(rec, subject_fields, dek, dek_id))

    ok_before, _ = verify_chain(entries, CURRENT_MAJOR,
                                expect_run_id="erasure-run", expect_plan_sha="erasure-plan")
    keyring.destroy(f"dek-{shred_index}")                       # the erasure
    ok_after, problems = verify_chain(entries, CURRENT_MAJOR,
                                      expect_run_id="erasure-run", expect_plan_sha="erasure-plan")

    sealed_records = [e for e in entries if e.get("type") != "genesis"]
    try:
        open_fields(sealed_records[shred_index], subject_fields, keyring)
        shredded_unrecoverable = False
    except Shredded:
        shredded_unrecoverable = True

    others_recoverable = True
    for i, rec in enumerate(sealed_records):
        if i == shred_index:
            continue
        try:
            opened = open_fields(rec, subject_fields, keyring)
            if opened["name"] != f"subject-{i}":
                others_recoverable = False
        except (Shredded, InvalidTag):
            others_recoverable = False

    # the non-subject field of the shredded record is still in the clear (other queries unaffected)
    amount_still_readable = sealed_records[shred_index].get("amount") == shred_index * 10

    report = {"n": n, "shred_index": shred_index,
              "chain_verifies_before": ok_before, "chain_verifies_after_shred": ok_after,
              "chain_problems_after": problems,
              "shredded_unrecoverable": shredded_unrecoverable,
              "others_recoverable": others_recoverable,
              "nonsubject_unaffected": amount_still_readable}
    report["ok"] = (ok_before and ok_after and shredded_unrecoverable and others_recoverable
                    and amount_still_readable)
    return report


if __name__ == "__main__":
    import sys
    r = erasure_drill()
    print(json.dumps(r, indent=2))
    sys.exit(0 if r["ok"] else 1)
