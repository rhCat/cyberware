#!/usr/bin/env python3
"""infra/cwp/keystore.py — the KeyStore adapter seam (P0-T15, spec/keys.md T29).

Key custody sits behind one seam so the backend can evolve (file today, an HSM tomorrow) without touching
the signing surface. A KeyStore answers the same contract regardless of backend: hold an Ed25519 key by id,
expose its raw public key + its resolvable cwp key-id (`sign.keyid`), and SIGN with it — the private key is
an implementation detail of the backend.

Two backends ship:
  * FileKeyStore — keys persist as raw bytes on disk (mode 0600); a fresh instance over the same directory
    finds them again (the seam is real, not in-memory).
  * SoftPkcs11KeyStore — an HSM-shaped stub: keys live in a "token" and NEVER leave it (there is no
    export-private method); signing happens in the token. It stands in for a real PKCS#11 adapter and proves
    the seam supports a non-exportable-key backend behind the identical contract.
"""
from __future__ import annotations
import abc
import os

from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey, Ed25519PublicKey

from infra.cwp import sign

_RAW = (serialization.Encoding.Raw, serialization.PublicFormat.Raw)
_RAW_PRIV = (serialization.Encoding.Raw, serialization.PrivateFormat.Raw, serialization.NoEncryption())


class KeyStore(abc.ABC):
    """The custody contract. Backends differ in WHERE the private key lives, never in this surface."""

    @abc.abstractmethod
    def generate(self, key_id: str) -> str:
        """Create + store a fresh Ed25519 key under `key_id`; return its resolvable key-id."""

    @abc.abstractmethod
    def public_raw(self, key_id: str) -> bytes:
        """The 32-byte raw Ed25519 public key."""

    @abc.abstractmethod
    def sign(self, key_id: str, message: bytes) -> bytes:
        """A 64-byte Ed25519 signature over `message`, produced by the backend (the private key never
        crosses this boundary for an HSM-class backend)."""

    @abc.abstractmethod
    def has(self, key_id: str) -> bool:
        ...

    @abc.abstractmethod
    def list_keys(self) -> list:
        ...

    # shared, backend-agnostic
    def keyid(self, key_id: str) -> str:
        return sign.keyid(self.public_raw(key_id))

    def verify(self, key_id: str, message: bytes, signature: bytes) -> bool:
        """True iff the signature verifies under the key's public; raises on a bad signature."""
        Ed25519PublicKey.from_public_bytes(self.public_raw(key_id)).verify(signature, message)
        return True


class FileKeyStore(KeyStore):
    """Keys persisted as raw private bytes on disk (mode 0600). Exportable custody — a file backend."""

    def __init__(self, directory: str):
        self.dir = directory
        os.makedirs(directory, exist_ok=True)

    def _path(self, key_id: str) -> str:
        return os.path.join(self.dir, key_id + ".key")

    def _load(self, key_id: str) -> Ed25519PrivateKey:
        with open(self._path(key_id), "rb") as f:
            return Ed25519PrivateKey.from_private_bytes(f.read())

    def generate(self, key_id: str) -> str:
        raw = Ed25519PrivateKey.generate().private_bytes(*_RAW_PRIV)
        fd = os.open(self._path(key_id), os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
        with os.fdopen(fd, "wb") as f:
            f.write(raw)
        return self.keyid(key_id)

    def public_raw(self, key_id: str) -> bytes:
        return self._load(key_id).public_key().public_bytes(*_RAW)

    def sign(self, key_id: str, message: bytes) -> bytes:
        return self._load(key_id).sign(message)

    def has(self, key_id: str) -> bool:
        return os.path.isfile(self._path(key_id))

    def list_keys(self) -> list:
        return sorted(f[:-4] for f in os.listdir(self.dir) if f.endswith(".key"))


class SoftPkcs11KeyStore(KeyStore):
    """An HSM-shaped stub: private keys live in the token and never leave it. There is deliberately NO
    method to export a private key — the non-exportable-custody property a real PKCS#11 backend provides."""

    def __init__(self):
        self._token = {}                                # key_id -> Ed25519PrivateKey, never exported

    def generate(self, key_id: str) -> str:
        self._token[key_id] = Ed25519PrivateKey.generate()
        return self.keyid(key_id)

    def public_raw(self, key_id: str) -> bytes:
        return self._token[key_id].public_key().public_bytes(*_RAW)

    def sign(self, key_id: str, message: bytes) -> bytes:
        return self._token[key_id].sign(message)        # signed "in the token"

    def has(self, key_id: str) -> bool:
        return key_id in self._token

    def list_keys(self) -> list:
        return sorted(self._token)


def contract_suite(ks: KeyStore) -> dict:
    """The single contract every backend must satisfy. Returns a per-check report; `ok` iff all hold."""
    c = {}
    kid = ks.generate("contract-key")
    c["keyid_resolvable"] = isinstance(kid, str) and kid.startswith("ed25519:") and len(kid) == 24
    c["has"] = ks.has("contract-key")
    c["listed"] = "contract-key" in ks.list_keys()
    c["missing_is_absent"] = not ks.has("no-such-key")
    msg = b"the canonical bytes to sign"
    sig = ks.sign("contract-key", msg)
    c["sig_len_64"] = len(sig) == 64
    try:
        ks.verify("contract-key", msg, sig)
        c["sig_verifies"] = True
    except Exception:
        c["sig_verifies"] = False
    try:
        ks.verify("contract-key", b"a different message", sig)
        c["rejects_wrong_message"] = False
    except Exception:
        c["rejects_wrong_message"] = True
    c["ok"] = all(v is True for v in c.values())
    return c


def keystore_drill(tmp_dir: str) -> dict:
    """P0-T15 acceptance, demonstrated: BOTH backends pass the one contract suite, the seam is real (the
    file backend persists across instances), and the HSM backend is non-exportable. Returns a report."""
    file_ok = contract_suite(FileKeyStore(os.path.join(tmp_dir, "fileks")))["ok"]
    p11 = SoftPkcs11KeyStore()
    p11_ok = contract_suite(p11)["ok"]

    seam_dir = os.path.join(tmp_dir, "seam")
    a = FileKeyStore(seam_dir)
    a.generate("persisted")
    b = FileKeyStore(seam_dir)                          # a FRESH instance over the same directory
    seam_real = b.has("persisted") and b.keyid("persisted") == a.keyid("persisted")

    hsm_nonexportable = not any(hasattr(p11, m) for m in ("export_private", "private_bytes", "private_key"))

    both = file_ok and p11_ok
    return {"file_backend_passes": file_ok, "pkcs11_backend_passes": p11_ok,
            "both_backends_pass": both, "seam_real": seam_real,
            "hsm_key_nonexportable": hsm_nonexportable,
            "ok": both and seam_real and hsm_nonexportable}


if __name__ == "__main__":
    import json
    import sys
    import tempfile
    r = keystore_drill(tempfile.mkdtemp())
    print(json.dumps(r, indent=2))
    sys.exit(0 if r["ok"] else 1)
