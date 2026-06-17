#!/usr/bin/env python3
"""infra/cwp/keyrotation.py — key rotation as a governed drill (P3-T06, SV-4 / M2).

Rotating a signing key without an outage and without breaking the audit trail has three obligations:

  * **overlap honored** — during the rotation window a grant signed by EITHER the old or the new key
    verifies, so in-flight work is not stranded the instant the new key appears.
  * **cross-signed record** — the rotation event is signed by BOTH keys (the old key introduces the new one,
    the new key accepts), so the chain of authority is continuous and provable: a verifier can walk from the
    old key to the new one without trusting a gap.
  * **clean revocation** — once the overlap closes the old key is revoked (P3-T03 feed), and from then on a
    grant signed with the old key is refused; only the new key is honored.

The drill exercises all three against real signatures and the real revocation gate.
"""
from __future__ import annotations
import hashlib
import os

from infra.cwp import canonical, cosign, revocation

_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
PINNED_ROOT = os.path.join(_ROOT, "spec", "tuf", "publisher-root.pub")


def kid(pub_pem_path: str) -> str:
    """A stable key id: sha256 of the PEM public key bytes (the artifact id the revocation feed names)."""
    return "key:" + hashlib.sha256(open(pub_pem_path, "rb").read()).hexdigest()[:32]


def sign_grant(doc: dict, priv_pem_path: str, signer_kid: str) -> dict:
    """Sign a grant doc with a key (cosign-shaped DSSE), tagging which key id signed it."""
    return cosign.sign_ph(canonical.canonical_bytes(doc), priv_pem_path,
                          payload_type="application/vnd.cyberware.grant+json", keyid=signer_kid)


def verify_grant(grant: dict, valid_keys: dict, now: int, feed: dict = None,
                 pinned_pub_pem: str = PINNED_ROOT) -> dict:
    """Verify a grant: its signing key must be in `valid_keys` (kid → pub_pem_path), its signature must
    verify under that key, and (if a revocation `feed` is given) that kid must not be revoked. Returns
    {allow, reason}."""
    signer = (grant.get("signatures") or [{}])[0].get("keyid")
    if signer not in valid_keys:
        return {"allow": False, "reason": "unknown_key"}
    if not cosign.verify_ph(grant, valid_keys[signer]):
        return {"allow": False, "reason": "bad_signature"}
    if feed is not None and not revocation.revocation_decision(
            feed, signer, now, last_seq=0, pinned_pub_pem=pinned_pub_pem)["allow"]:
        return {"allow": False, "reason": "key_revoked"}
    return {"allow": True, "reason": "ok", "kid": signer}


def cross_sign_rotation(old_priv: str, old_kid: str, new_priv: str, new_kid: str,
                        new_pub_pem_path: str) -> dict:
    """The cross-signed rotation record: the introduced new public key, signed by BOTH the old key (which
    attests the successor) and the new key (which accepts)."""
    body = {"event": "key_rotation", "old": old_kid, "new": new_kid,
            "new_pub_sha": hashlib.sha256(open(new_pub_pem_path, "rb").read()).hexdigest()}
    payload = canonical.canonical_bytes(body)
    return {"body": body,
            "sig_old": cosign.ph_sign(payload, old_priv).hex(),
            "sig_new": cosign.ph_sign(payload, new_priv).hex()}


def verify_rotation(record: dict, old_pub_pem: str, new_pub_pem: str) -> bool:
    """True iff the rotation record is cross-signed: BOTH the old and new keys signed the same body."""
    payload = canonical.canonical_bytes(record["body"])
    return (cosign.ph_verify(payload, bytes.fromhex(record["sig_old"]), old_pub_pem)
            and cosign.ph_verify(payload, bytes.fromhex(record["sig_new"]), new_pub_pem))


def keyrotation_selftest() -> dict:
    """A hermetic P3-T06 drill with EPHEMERAL old+new keys and a fixed clock: produce a cross-signed
    rotation record (both keys sign it); during the OVERLAP a grant from either key verifies; then revoke the
    old key via the feed and confirm an old-key grant is refused while a new-key grant still verifies. `ok`
    iff all three hold. Needs openssl (ed25519ph)."""
    import subprocess
    import tempfile
    d = tempfile.mkdtemp(prefix="keyrot-")

    def keypair(tag):
        p, pub = os.path.join(d, f"{tag}.key"), os.path.join(d, f"{tag}.pub")
        subprocess.run(["openssl", "genpkey", "-algorithm", "ed25519", "-out", p], check=True, capture_output=True)
        subprocess.run(["openssl", "pkey", "-in", p, "-pubout", "-out", pub], check=True, capture_output=True)
        return p, pub

    old_priv, old_pub = keypair("old")
    new_priv, new_pub = keypair("new")
    pub_priv, pub_pub = keypair("publisher")                    # signs the revocation feed
    old_kid, new_kid = kid(old_pub), kid(new_pub)

    record = cross_sign_rotation(old_priv, old_kid, new_priv, new_kid, new_pub)
    cross_signed = verify_rotation(record, old_pub, new_pub)
    # tamper: a record signed by only one key must NOT verify as cross-signed
    one_sided = verify_rotation({**record, "sig_new": record["sig_old"]}, old_pub, new_pub)

    doc = {"action": "publish", "target": "chip"}
    both = {old_kid: old_pub, new_kid: new_pub}
    T0 = 1_700_000_000
    g_old = sign_grant(doc, old_priv, old_kid)
    g_new = sign_grant(doc, new_priv, new_kid)
    overlap_old = verify_grant(g_old, both, T0)["allow"]
    overlap_new = verify_grant(g_new, both, T0)["allow"]

    revoke_feed = revocation.sign_feed(1, [old_kid], T0, 3600, pub_priv)
    post_old = verify_grant(g_old, both, T0 + 10, feed=revoke_feed, pinned_pub_pem=pub_pub)
    post_new = verify_grant(g_new, both, T0 + 10, feed=revoke_feed, pinned_pub_pem=pub_pub)

    return {"cross_signed_record_present": cross_signed and not one_sided,
            "overlap_honored": overlap_old and overlap_new,
            "post_revocation_old_key_grant_refuses": post_old["allow"] is False and post_old["reason"] == "key_revoked",
            "post_revocation_new_key_still_valid": post_new["allow"] is True,
            "tuf_root_pinned": os.path.isfile(PINNED_ROOT),
            "ok": (cross_signed and not one_sided and overlap_old and overlap_new
                   and post_old["allow"] is False and post_new["allow"] is True
                   and os.path.isfile(PINNED_ROOT))}
