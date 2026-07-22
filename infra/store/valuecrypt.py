#!/usr/bin/env python3
"""infra/store/valuecrypt.py — envelope encryption for the tier-2 value ledger (docs/pg-provenance-ledger.md).

The tier-1 chain stays value-free; tier 2 records the (already declared-subset, secret-filtered) per-step
`var_values` so a run is INSPECTABLE + REPRODUCIBLE — but never in plaintext at rest. Each value blob gets a
fresh per-blob data key (DEK); the DEK is wrapped to a RECIPIENT SET of X25519 public keys (standalone: the
node's own key; post fleet-handshake: + the mothership oversight key). So:

  * off-node at rest = ciphertext only — a replica / backup / over-granted DB role yields nothing readable;
  * fleet join re-wraps the DEK to a new recipient (a few bytes) WITHOUT re-encrypting the data;
  * any recipient decrypts OFFLINE from the blob alone — no per-row key fetch.

The commitment `values_sha` (bound into the tier-1 chain) is sha256 of the canonical PLAINTEXT — NEVER the
ciphertext (a fresh nonce per blob would make a ciphertext hash meaningless). Verify: decrypt -> canon -> hash
-> match the chain. Confidentiality (this module) and integrity (the chain) stay orthogonal.

Primitives are all from `cryptography` (already required for the Ed25519 grant/exod identities): X25519 ECDH
+ HKDF-SHA256 to derive a per-recipient key-wrapping key, AES-256-GCM to wrap the DEK and to seal the blob.
No new dependency. HONEST LIMIT: govd sees values transiently (it is the writer); a compromised LIVE govd host
reads them regardless — this defends the AT-REST surface (backups, replicas, roles), which is exactly what
federation + backup create.
"""
from __future__ import annotations
import hashlib
import json
import os

from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric.x25519 import X25519PrivateKey, X25519PublicKey
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from cryptography.hazmat.primitives.kdf.hkdf import HKDF

_WRAP_INFO = b"cyberware/valuecrypt/dek-wrap/v1"       # HKDF domain separation — wrap KEK vs anything else
_BLOB_AAD = b"cyberware/valuecrypt/blob/v1"            # AES-GCM AAD binds the ciphertext to this scheme+version


def canon(values: dict) -> bytes:
    """The canonical plaintext bytes hashed into `values_sha` AND sealed as the blob. Stable: sorted keys,
    tight separators — so the same {KEY:value} map always yields the same sha and the same sealed bytes."""
    return json.dumps(values, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")


def values_sha(values: dict) -> str:
    """sha256 of the canonical PLAINTEXT — the commitment bound into the tier-1 chain (never the ciphertext)."""
    return hashlib.sha256(canon(values)).hexdigest()


def keyid(pub_raw: bytes) -> str:
    """A short stable id for a recipient public key — the map key in `dek_wraps` and the audit label."""
    return "x25519:" + hashlib.sha256(pub_raw).hexdigest()[:16]


# ── key material ─────────────────────────────────────────────────────────────────────────────────────────
def generate_node_key(path: str) -> bytes:
    """Create a fresh X25519 private key at `path` (chmod 600) if absent; return the RAW 32-byte PUBLIC key.
    Idempotent — an existing key is loaded, never overwritten (rotation is an explicit operator act, not a
    restart side effect). The private key lives beside govd's other key material, NEVER in the DB / a
    replicated path."""
    path = os.path.expanduser(path)
    if os.path.exists(path):
        return load_public(path)
    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
    sk = X25519PrivateKey.generate()
    raw = sk.private_bytes(serialization.Encoding.Raw, serialization.PrivateFormat.Raw,
                           serialization.NoEncryption())
    # write 0600: create with a restrictive mode from the start (never a world-readable window mid-write)
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    try:
        os.write(fd, raw)
    finally:
        os.close(fd)
    return sk.public_key().public_bytes(serialization.Encoding.Raw, serialization.PublicFormat.Raw)


def load_private(path: str) -> X25519PrivateKey:
    with open(os.path.expanduser(path), "rb") as f:
        return X25519PrivateKey.from_private_bytes(f.read())


def load_public(path: str) -> bytes:
    """The RAW 32-byte public key for the private key at `path` (recipient set membership + keyid)."""
    return load_private(path).public_key().public_bytes(
        serialization.Encoding.Raw, serialization.PublicFormat.Raw)


# ── envelope ─────────────────────────────────────────────────────────────────────────────────────────────
def _wrap_kek(recipient_pub_raw: bytes) -> tuple[bytes, bytes]:
    """Derive a one-shot key-wrapping key for `recipient` via ephemeral-static X25519 + HKDF. Returns
    (kek, ephemeral_pub_raw) — the ephemeral public rides in the wrap so the recipient can re-derive the KEK."""
    eph = X25519PrivateKey.generate()
    shared = eph.exchange(X25519PublicKey.from_public_bytes(recipient_pub_raw))
    kek = HKDF(algorithm=hashes.SHA256(), length=32, salt=None, info=_WRAP_INFO).derive(shared)
    eph_pub = eph.public_key().public_bytes(serialization.Encoding.Raw, serialization.PublicFormat.Raw)
    return kek, eph_pub


def _unwrap_kek(sk: X25519PrivateKey, eph_pub_raw: bytes) -> bytes:
    shared = sk.exchange(X25519PublicKey.from_public_bytes(eph_pub_raw))
    return HKDF(algorithm=hashes.SHA256(), length=32, salt=None, info=_WRAP_INFO).derive(shared)


def encrypt(values: dict, recipient_pubs: list[bytes]) -> dict:
    """Seal `values` under a fresh DEK, wrap that DEK to EACH recipient public key. Returns a self-describing
    blob dict (JSON-friendly, hex fields) plus the plaintext commitment `values_sha`:

        {"v":1, "sha": <sha256(plaintext)>, "nonce": <hex>, "ct": <hex>,
         "wraps": { <keyid>: {"eph": <hex>, "nonce": <hex>, "wrap": <hex>} , ... }}

    At least one recipient is required (a blob no one can open is a bug, not a feature)."""
    if not recipient_pubs:
        raise ValueError("valuecrypt.encrypt: recipient set is empty — a value blob needs >=1 recipient")
    pt = canon(values)
    dek = AESGCM.generate_key(bit_length=256)
    blob_nonce = os.urandom(12)
    ct = AESGCM(dek).encrypt(blob_nonce, pt, _BLOB_AAD)
    wraps = {}
    for pub in recipient_pubs:
        kek, eph_pub = _wrap_kek(pub)
        wrap_nonce = os.urandom(12)
        wrapped = AESGCM(kek).encrypt(wrap_nonce, dek, _WRAP_INFO)
        wraps[keyid(pub)] = {"eph": eph_pub.hex(), "nonce": wrap_nonce.hex(), "wrap": wrapped.hex()}
    return {"v": 1, "sha": hashlib.sha256(pt).hexdigest(), "nonce": blob_nonce.hex(),
            "ct": ct.hex(), "wraps": wraps}


def rewrap(blob: dict, sk: X25519PrivateKey, new_recipient_pubs: list[bytes]) -> dict:
    """Add recipients to an existing blob WITHOUT re-encrypting the data: recover the DEK with a key we hold,
    wrap it to each new recipient, merge into `wraps`. This is the fleet-join backfill — a few bytes per blob.
    Returns a new blob dict (the input is not mutated)."""
    dek = _recover_dek(blob, sk)
    wraps = dict(blob.get("wraps") or {})
    for pub in new_recipient_pubs:
        kek, eph_pub = _wrap_kek(pub)
        wrap_nonce = os.urandom(12)
        wraps[keyid(pub)] = {"eph": eph_pub.hex(), "nonce": wrap_nonce.hex(),
                             "wrap": AESGCM(kek).encrypt(wrap_nonce, dek, _WRAP_INFO).hex()}
    out = dict(blob)
    out["wraps"] = wraps
    return out


def _recover_dek(blob: dict, sk: X25519PrivateKey) -> bytes:
    """Find the wrap addressed to our key and unwrap the DEK. Raises if we are not a recipient."""
    my_id = keyid(sk.public_key().public_bytes(serialization.Encoding.Raw, serialization.PublicFormat.Raw))
    w = (blob.get("wraps") or {}).get(my_id)
    if w is None:
        raise ValueError("valuecrypt.decrypt: this key is not a recipient of the blob")
    kek = _unwrap_kek(sk, bytes.fromhex(w["eph"]))
    return AESGCM(kek).decrypt(bytes.fromhex(w["nonce"]), bytes.fromhex(w["wrap"]), _WRAP_INFO)


def decrypt(blob: dict, sk: X25519PrivateKey) -> dict:
    """Open a blob with a recipient private key -> the original `values` dict. Also re-verifies the plaintext
    commitment (`sha`) so a tampered ciphertext is caught here, not silently returned."""
    dek = _recover_dek(blob, sk)
    pt = AESGCM(dek).decrypt(bytes.fromhex(blob["nonce"]), bytes.fromhex(blob["ct"]), _BLOB_AAD)
    if hashlib.sha256(pt).hexdigest() != blob.get("sha"):
        raise ValueError("valuecrypt.decrypt: plaintext commitment mismatch — blob tampered")
    return json.loads(pt.decode("utf-8"))
