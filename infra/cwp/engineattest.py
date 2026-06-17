#!/usr/bin/env python3
"""infra/cwp/engineattest.py — engine attestation + mutual handshake (P3-T05, SV-4).

The engine is the reproducibly-built anchor (P0-T13). At release time the publisher signs an **engine
attestation** — a DSSE over `{engine_digest, version}` where `engine_digest` is the byte-for-byte sha256 of
that reproducible build. Before two principals run together (engine ↔ govd/chip) they perform a **mutual
handshake**: each side presents its signed attestation AND its live binary; each verifies the other's
signature under the PINNED publisher root *and* re-measures the live binary, requiring the live digest to
equal the signed digest. A **one-byte tamper on either side** changes the live measurement, the digests stop
matching, and the result is `engine_unattested` — the handshake fails closed. A **release receipt** binds the
chip release (P3-T01) and the engine attestation into one dual-signed object, so `health_matches_signed_release`
is checkable: the live engine measures to the digest the signed release published, and nothing else runs.
"""
from __future__ import annotations
import base64
import hashlib
import json
import os

from infra.cwp import canonical, cosign, release

ENGINE_TYPE = "application/vnd.cyberware.engine+json"
_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
PINNED_ROOT = os.path.join(_ROOT, "spec", "tuf", "publisher-root.pub")
ATTESTED = "attested"
UNATTESTED = "engine_unattested"


def engine_measure(blob: bytes) -> str:
    """The engine's identity: the sha256 of its bytes — the same digest the reproducible build pins."""
    return hashlib.sha256(blob).hexdigest()


def sign_engine(blob: bytes, version: str, priv_pem_path: str) -> dict:
    """Publisher-sign an engine attestation over `{engine_digest, version}` (cosign-shaped, Ed25519ph)."""
    body = {"engine_digest": engine_measure(blob), "version": version}
    return cosign.sign_ph(canonical.canonical_bytes(body), priv_pem_path, payload_type=ENGINE_TYPE,
                          keyid="publisher-root")


def verify_engine(att: dict, pinned_pub_pem: str = PINNED_ROOT):
    """Returns (ok, body). The attestation must be the engine type, signed, and verify under the PINNED
    publisher root — a forged or unsigned attestation fails here."""
    if not isinstance(att, dict) or att.get("payloadType") != ENGINE_TYPE:
        return False, None
    if not att.get("signatures") or not cosign.verify_ph(att, pinned_pub_pem):
        return False, None
    try:
        return True, json.loads(base64.b64decode(att["payload"]))
    except Exception:
        return False, None


def attest_live(att: dict, live_blob: bytes, pinned_pub_pem: str = PINNED_ROOT) -> str:
    """The core check on ONE side: the attestation verifies under the pinned root AND the live binary
    re-measures to the signed digest. Returns ATTESTED or UNATTESTED — a one-byte tamper in `live_blob`
    changes the measurement and lands here as UNATTESTED."""
    ok, body = verify_engine(att, pinned_pub_pem)
    if not ok:
        return UNATTESTED
    return ATTESTED if engine_measure(live_blob) == body.get("engine_digest") else UNATTESTED


def mutual_handshake(local_att, local_blob, peer_att, peer_blob, pinned_pub_pem=PINNED_ROOT) -> dict:
    """Both principals attest each other's live engine. The handshake succeeds only if BOTH sides are
    ATTESTED; a tamper on either side fails the whole handshake closed (engine_unattested)."""
    a = attest_live(local_att, local_blob, pinned_pub_pem)
    b = attest_live(peer_att, peer_blob, pinned_pub_pem)
    both = a == ATTESTED and b == ATTESTED
    return {"local": a, "peer": b, "status": ATTESTED if both else UNATTESTED, "ok": both}


def release_receipt(chip_index_path: str, engine_blob: bytes, version: str, priv_pem_path: str) -> dict:
    """A dual-signed receipt binding the chip release (P3-T01) and the engine attestation — what the
    publisher actually publishes, so a verifier can tie the running engine to the signed release."""
    return {"release": release.sign_release(chip_index_path, priv_pem_path),
            "engine": sign_engine(engine_blob, version, priv_pem_path)}


def health_matches_signed_release(receipt: dict, live_engine_blob: bytes,
                                  pinned_pub_pem: str = PINNED_ROOT) -> bool:
    """True iff the live engine's health matches the signed release: the engine attestation verifies, the
    live binary measures to the published engine_digest, and the chip release in the receipt verifies — all
    under the pinned root."""
    eok, ebody = verify_engine(receipt.get("engine", {}), pinned_pub_pem)
    if not eok or engine_measure(live_engine_blob) != ebody.get("engine_digest"):
        return False
    rok, _ = release.verify_release(receipt.get("release", {}), pinned_pub_pem)
    return rok


def engine_selftest(chip_index_path: str = None) -> dict:
    """A hermetic P3-T05 demonstration: generate an EPHEMERAL publisher key, sign two engine attestations
    (a local + a peer engine), and run a clean mutual handshake (attested). Then flip ONE byte on the local
    side, and separately on the peer side, and confirm each yields engine_unattested. Finally build a dual-
    signed release receipt and confirm the live engine's health matches the signed release — and that a
    tampered engine does not. `ok` iff every property holds. Needs openssl (ed25519ph)."""
    import subprocess
    import tempfile
    d = tempfile.mkdtemp(prefix="engineattest-")
    priv, pub = os.path.join(d, "p.key"), os.path.join(d, "p.pub")
    subprocess.run(["openssl", "genpkey", "-algorithm", "ed25519", "-out", priv], check=True, capture_output=True)
    subprocess.run(["openssl", "pkey", "-in", priv, "-pubout", "-out", pub], check=True, capture_output=True)

    local = b"cyberware-engine-anchor-vA-" + b"\x00" * 64
    peer = b"cyberware-engine-anchor-vB-" + b"\x11" * 64
    local_att = sign_engine(local, "1.1.0", priv)
    peer_att = sign_engine(peer, "1.1.0", priv)

    clean = mutual_handshake(local_att, local, peer_att, peer, pub)["status"] == ATTESTED

    def _flip(b):
        m = bytearray(b)
        m[0] ^= 0x01
        return bytes(m)

    local_tampered = mutual_handshake(local_att, _flip(local), peer_att, peer, pub)["status"] == UNATTESTED
    peer_tampered = mutual_handshake(local_att, local, peer_att, _flip(peer), pub)["status"] == UNATTESTED
    forged_att = {**local_att, "signatures": []}
    unsigned_refused = attest_live(forged_att, local, pub) == UNATTESTED

    chip = chip_index_path or os.path.join(_ROOT, "skillChip", "index.json")
    receipt = release_receipt(chip, local, "1.1.0", priv)
    health_ok = health_matches_signed_release(receipt, local, pub)
    health_rejects_tamper = not health_matches_signed_release(receipt, _flip(local), pub)

    return {"clean_handshake_attested": clean,
            "tamper_local_unattested": local_tampered, "tamper_peer_unattested": peer_tampered,
            "unsigned_attestation_refused": unsigned_refused,
            "health_matches_signed_release": health_ok, "health_rejects_tampered_engine": health_rejects_tamper,
            "tuf_root_pinned": os.path.isfile(PINNED_ROOT),
            "ok": (clean and local_tampered and peer_tampered and unsigned_refused and health_ok
                   and health_rejects_tamper and os.path.isfile(PINNED_ROOT))}
