#!/usr/bin/env python3
"""infra/cwp/cosign.py — sigstore/cosign DSSE interop adapter (Ed25519ph) for P0-T03.

cwp's NATIVE signatures are pure Ed25519 (infra/cwp/sign.py, pyca) and stay unchanged. But cosign/sigstore
sign DSSE attestations with **Ed25519ph** — HashEdDSA over SHA-512 of the DSSE PAE — which pyca/cryptography
does not implement. This adapter bridges that one gap through the OpenSSL CLI (>= 3.4, which added
Ed25519ph): `openssl pkeyutl ... -pkeyopt instance:ed25519ph`. So a cosign-generated DSSE envelope verifies
here (`verify_ph`), and a cwp-produced ph envelope verifies in cosign (`sign_ph` / `attest_blob`) — the two
directions of the T03 interop acceptance.

The PAE is identical to cwp's native DSSE (infra/cwp/sign.pae); only the signature *algorithm* differs
(ph vs pure). Keys ride as PEM files (cosign and openssl both use PEM). Requires the `openssl` CLI >= 3.4.
"""
from __future__ import annotations
import base64
import hashlib
import os
import subprocess
import tempfile

from infra.cwp import canonical, sign

IN_TOTO_TYPE = "application/vnd.in-toto+json"


def _openssl(args):
    return subprocess.run(["openssl", *args], capture_output=True, text=True)


def ph_sign(message: bytes, priv_pem_path: str) -> bytes:
    """Ed25519ph signature over `message` (the DSSE PAE) via OpenSSL — the algorithm sigstore uses."""
    with tempfile.TemporaryDirectory() as d:
        mp, sp = os.path.join(d, "m"), os.path.join(d, "s")
        with open(mp, "wb") as f:
            f.write(message)
        r = _openssl(["pkeyutl", "-sign", "-inkey", priv_pem_path, "-rawin", "-in", mp,
                      "-out", sp, "-pkeyopt", "instance:ed25519ph"])
        if r.returncode != 0:
            raise RuntimeError(f"openssl ed25519ph sign failed: {r.stderr.strip()}")
        with open(sp, "rb") as f:
            return f.read()


def ph_verify(message: bytes, sig: bytes, pub_pem_path: str) -> bool:
    """True iff `sig` is a valid Ed25519ph signature over `message` under the PEM public key (via OpenSSL)."""
    with tempfile.TemporaryDirectory() as d:
        mp, sp = os.path.join(d, "m"), os.path.join(d, "s")
        with open(mp, "wb") as f:
            f.write(message)
        with open(sp, "wb") as f:
            f.write(sig)
        r = _openssl(["pkeyutl", "-verify", "-pubin", "-inkey", pub_pem_path, "-rawin",
                      "-in", mp, "-sigfile", sp, "-pkeyopt", "instance:ed25519ph"])
        return r.returncode == 0 and "Verified Successfully" in r.stdout


def verify_ph(envelope: dict, pub_pem_path: str) -> bool:
    """True iff a signature in the DSSE envelope verifies as Ed25519ph over PAE(payloadType, payload) —
    i.e. cwp accepting a cosign/sigstore-generated DSSE envelope."""
    try:
        payload = base64.b64decode(envelope["payload"])
        message = sign.pae(envelope["payloadType"], payload)
    except (KeyError, ValueError, TypeError):
        return False
    for s in envelope.get("signatures", []):
        try:
            if ph_verify(message, base64.b64decode(s["sig"]), pub_pem_path):
                return True
        except (ValueError, TypeError):
            continue
    return False


def sign_ph(payload: bytes, priv_pem_path: str, payload_type: str = IN_TOTO_TYPE, keyid: str = "") -> dict:
    """Ed25519ph-sign PAE(payload_type, payload) → a DSSE envelope cosign can verify."""
    sig = ph_sign(sign.pae(payload_type, payload), priv_pem_path)
    return {"payload": base64.b64encode(payload).decode(), "payloadType": payload_type,
            "signatures": [{"keyid": keyid, "sig": base64.b64encode(sig).decode()}]}


def intoto_statement(name: str, sha256_hex: str, predicate_type: str, predicate: dict) -> dict:
    """An in-toto v0.1 Statement binding a subject (name + sha256 digest) to a predicate — the body cosign
    DSSE-attests. Canonicalized (JCS) so the bytes are reproducible."""
    return {"_type": "https://in-toto.io/Statement/v0.1", "predicateType": predicate_type,
            "subject": [{"name": name, "digest": {"sha256": sha256_hex}}], "predicate": predicate}


def attest_blob(blob_path: str, priv_pem_path: str, predicate_type: str, predicate: dict) -> dict:
    """Produce a cosign-verifiable DSSE attestation over a blob: build the in-toto statement (subject =
    the blob's sha256), then Ed25519ph-sign its canonical bytes."""
    with open(blob_path, "rb") as f:
        digest = hashlib.sha256(f.read()).hexdigest()
    stmt = intoto_statement(os.path.basename(blob_path), digest, predicate_type, predicate)
    return sign_ph(canonical.canonical_bytes(stmt), priv_pem_path)
