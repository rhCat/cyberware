#!/usr/bin/env python3
"""infra/cwp/publish.py — the governed release receipt (P3-T15, SV-4).

This is the capstone of the M4 cone: it composes the three release primitives into ONE dual-signed,
transparency-logged receipt and verifies it end to end.

  * the **chip release** is publisher-signed (P3-T01, `release.py`),
  * the **engine** is publisher-signed and bound to its reproducible-build digest (P3-T05, `engineattest.py`),
  * the release is entered into the **transparency log** and the receipt carries the offline **inclusion
    proof** (P3-T02, `translog.py`) — so `rekor_proof_stored` is true and verifiable with no live log.

A verifier checks all three legs under the PINNED publisher root, re-measures the live engine, and replays
the inclusion proof — offline. Tampering any single leg (chip, engine, or transparency) fails the receipt
closed. This is the SV-4 promise made one artifact: *chip + engine are dual-signed receipts via the channel,
the transparency proof is stored, and what runs is exactly what was published.*
"""
from __future__ import annotations
import os

from infra.cwp import engineattest, release, translog

_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
PINNED_ROOT = os.path.join(_ROOT, "spec", "tuf", "publisher-root.pub")


def governed_release(chip_index_path: str, engine_blob: bytes, version: str, priv_pem_path: str,
                     prior_leaves=None) -> dict:
    """Produce the governed release receipt: a dual-signed (chip + engine) object that also stores the
    transparency inclusion proof. `prior_leaves` are the existing log leaves (the release is appended after
    them); default is an empty log, so the release is leaf 0."""
    rel = release.sign_release(chip_index_path, priv_pem_path)
    eng = engineattest.sign_engine(engine_blob, version, priv_pem_path)
    leaves = list(prior_leaves or [])
    leaves.append(translog.leaf_hash(rel))
    index = len(leaves) - 1
    proof = translog.offline_proof(rel, index, leaves, priv_pem_path)
    return {"release": rel, "engine": eng, "transparency": proof, "version": version}


def verify_governed_release(receipt: dict, live_engine_blob: bytes, chip_index_path: str = None,
                            pinned_pub_pem: str = PINNED_ROOT) -> dict:
    """Verify all three legs of the receipt offline under the pinned root. Returns a per-leg report; `ok`
    iff every leg holds (and, when `chip_index_path` is given, the signed release still matches the chip)."""
    rel_ok, rel_reason = release.verify_release(receipt.get("release", {}), pinned_pub_pem)
    matches = (chip_index_path is None) or release.release_matches_chip(receipt.get("release", {}), chip_index_path)
    engine_status = engineattest.attest_live(receipt.get("engine", {}), live_engine_blob, pinned_pub_pem)
    trans_ok, trans_reason = translog.verify_offline(receipt.get("transparency", {}), pinned_pub_pem)
    rekor_proof_stored = isinstance(receipt.get("transparency"), dict) and "inclusion" in receipt["transparency"]
    return {"release_signed": rel_ok, "release_reason": rel_reason, "release_matches_chip": matches,
            "engine_attested": engine_status == engineattest.ATTESTED,
            "transparency_verified": trans_ok, "transparency_reason": trans_reason,
            "rekor_proof_stored": rekor_proof_stored,
            "ok": rel_ok and matches and engine_status == engineattest.ATTESTED and trans_ok
            and rekor_proof_stored}


def publish_selftest(chip_index_path: str = None) -> dict:
    """A hermetic P3-T15 demonstration: build a governed release receipt with an EPHEMERAL publisher key,
    verify all three legs offline (chip release + engine attestation + stored transparency proof), and then
    tamper EACH leg in turn — the chip release, the live engine (one byte), and the transparency leaf — and
    confirm each independently fails the receipt closed. `ok` iff the clean receipt verifies, the rekor proof
    is stored, and all three tampers are caught. Needs openssl (ed25519ph)."""
    import base64
    import json
    import subprocess
    import tempfile
    from infra.cwp import canonical
    d = tempfile.mkdtemp(prefix="publish-")
    priv, pub = os.path.join(d, "p.key"), os.path.join(d, "p.pub")
    subprocess.run(["openssl", "genpkey", "-algorithm", "ed25519", "-out", priv], check=True, capture_output=True)
    subprocess.run(["openssl", "pkey", "-in", priv, "-pubout", "-out", pub], check=True, capture_output=True)
    chip = chip_index_path or os.path.join(_ROOT, "skillChip", "index.json")
    engine = b"cyberware-engine-anchor-" + b"\x00" * 48

    # prior log traffic so the release lands at a non-zero index (a realistic inclusion proof)
    prior = [translog.leaf_hash({"payloadType": release.RELEASE_TYPE,
             "payload": base64.b64encode(canonical.canonical_bytes({"prev": i})).decode(),
             "signatures": [{"sig": "x"}]}) for i in range(3)]
    receipt = governed_release(chip, engine, "1.1.0", priv, prior)

    clean = verify_governed_release(receipt, engine, chip, pub)
    clean_ok = clean["ok"] and clean["rekor_proof_stored"]

    tampered_chip = {**receipt, "release": {**receipt["release"], "payload":
                     base64.b64encode(canonical.canonical_bytes({"chip_sha": "0" * 64, "skills": {}})).decode()}}
    chip_tamper_caught = not verify_governed_release(tampered_chip, engine, chip, pub)["ok"]

    flipped = bytearray(engine)
    flipped[0] ^= 0x01
    engine_tamper_caught = not verify_governed_release(receipt, bytes(flipped), chip, pub)["ok"]

    body = json.loads(base64.b64decode(receipt["transparency"]["sth"]["payload"]))
    body["root_hash"] = "0" * 64
    tampered_trans = {**receipt, "transparency": {**receipt["transparency"], "sth":
                      {**receipt["transparency"]["sth"],
                       "payload": base64.b64encode(canonical.canonical_bytes(body)).decode()}}}
    trans_tamper_caught = not verify_governed_release(tampered_trans, engine, chip, pub)["ok"]

    return {"governed_release_verifies": clean_ok, "rekor_proof_stored": clean["rekor_proof_stored"],
            "chip_tamper_caught": chip_tamper_caught, "engine_tamper_caught": engine_tamper_caught,
            "transparency_tamper_caught": trans_tamper_caught,
            "tuf_root_pinned": os.path.isfile(PINNED_ROOT),
            "ok": (clean_ok and chip_tamper_caught and engine_tamper_caught and trans_tamper_caught
                   and os.path.isfile(PINNED_ROOT))}
