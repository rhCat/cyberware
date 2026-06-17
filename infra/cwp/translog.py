#!/usr/bin/env python3
"""infra/cwp/translog.py — an OFFLINE, Rekor-shaped transparency log for releases (P3-T02, SV-4).

Every published release envelope is appended as a leaf to an append-only Merkle log. The log's head — a
**Signed Tree Head** (`{tree_size, root_hash}`, signed with the PUBLISHER key, Ed25519ph) — is the only
trusted anchor. A release ships with a self-contained **offline proof bundle**: the leaf, its index, the
inclusion (audit) path, and the signed tree head. A verifier recomputes the root from leaf + path, checks it
equals the STH's root, and checks the STH's signature against the PINNED publisher root — *no live log
service is contacted*. This is the SV-4 transparency promise made verifiable on an airgapped box.

The Merkle construction is the SAME one Ledger-v2 checkpoints use (`checkpoint.merkle_root`: binary
SHA-256, odd nodes duplicate the last) so the two layers share one audited tree primitive, and the inclusion
proof here recomputes exactly that root.
"""
from __future__ import annotations
import hashlib
import json
import os

from infra.cwp import canonical, checkpoint, cosign

STH_TYPE = "application/vnd.cyberware.sth+json"
_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
PINNED_ROOT = os.path.join(_ROOT, "spec", "tuf", "publisher-root.pub")


def leaf_hash(envelope: dict) -> bytes:
    """The log leaf for a release: SHA-256 of the canonical envelope bytes (the whole signed DSSE, so the
    leaf binds the publisher signature too, not just the payload)."""
    return hashlib.sha256(canonical.canonical_bytes(envelope)).digest()


def inclusion_proof(index: int, leaves) -> list:
    """The audit path for leaf `index`: the sibling hash at each level, bottom-up. Recomputed with these
    siblings + the leaf, it reproduces `merkle_root(leaves)` exactly (same odd-duplicates-last rule)."""
    if not (0 <= index < len(leaves)):
        raise IndexError("leaf index out of range")
    path = []
    level = list(leaves)
    idx = index
    while len(level) > 1:
        sib = idx ^ 1
        if sib >= len(level):                                   # odd node at the end duplicates itself
            sib = idx
        path.append(level[sib].hex())
        nxt = []
        for i in range(0, len(level), 2):
            a = level[i]
            b = level[i + 1] if i + 1 < len(level) else level[i]
            nxt.append(hashlib.sha256(a + b).digest())
        level = nxt
        idx //= 2
    return path


def verify_inclusion(leaf: bytes, index: int, tree_size: int, proof, root_hash_hex: str) -> bool:
    """Recompute the root from the leaf + audit path and compare to the claimed root — the offline core.
    Reproduces checkpoint.merkle_root's tree, so a forged leaf, wrong index, or doctored path all miss."""
    if not (0 <= index < tree_size):
        return False
    h = leaf
    idx, span = index, tree_size
    for sib_hex in proof:
        sib = bytes.fromhex(sib_hex)
        if idx % 2 == 0:
            # left child; right sibling exists only if there is a node to the right at this level
            h = hashlib.sha256(h + (sib if idx + 1 < span else h)).digest()
        else:
            h = hashlib.sha256(sib + h).digest()
        idx //= 2
        span = (span + 1) // 2
    return h.hex() == root_hash_hex


def signed_tree_head(leaves, priv_pem_path: str) -> dict:
    """The trusted anchor: sign `{tree_size, root_hash}` with the publisher key (cosign-shaped DSSE)."""
    body = {"tree_size": len(leaves), "root_hash": checkpoint.merkle_root(leaves).hex()}
    return cosign.sign_ph(canonical.canonical_bytes(body), priv_pem_path, payload_type=STH_TYPE,
                          keyid="publisher-root")


def verify_sth(sth: dict, pinned_pub_pem: str = PINNED_ROOT):
    """Returns (ok, body). The STH must be the right type, signed, and verify under the PINNED publisher
    root — an unsigned or forged head is rejected here, before any inclusion check."""
    import base64
    if not isinstance(sth, dict) or sth.get("payloadType") != STH_TYPE:
        return False, None
    if not sth.get("signatures") or not cosign.verify_ph(sth, pinned_pub_pem):
        return False, None
    try:
        return True, json.loads(base64.b64decode(sth["payload"]))
    except Exception:
        return False, None


def offline_proof(envelope: dict, index: int, leaves, priv_pem_path: str) -> dict:
    """A self-contained, offline-verifiable transparency receipt for one release: the leaf, its index, the
    inclusion path, and the publisher-signed tree head. Ships with the release; needs no live log."""
    return {"leaf": leaf_hash(envelope).hex(), "index": index, "tree_size": len(leaves),
            "inclusion": inclusion_proof(index, leaves), "sth": signed_tree_head(leaves, priv_pem_path)}


def verify_offline(bundle: dict, pinned_pub_pem: str = PINNED_ROOT):
    """Returns (ok, reason). Offline verification, in order: the STH verifies under the pinned publisher
    root; the bundle's tree_size matches the STH; the leaf + inclusion path recompute the STH root. Any
    failure → refused, against the committed root only (no live Rekor)."""
    ok, body = verify_sth(bundle.get("sth", {}), pinned_pub_pem)
    if not ok:
        return False, "bad_sth"
    if bundle.get("tree_size") != body.get("tree_size"):
        return False, "size_mismatch"
    try:
        leaf = bytes.fromhex(bundle["leaf"])
    except Exception:
        return False, "bad_leaf"
    if not verify_inclusion(leaf, bundle["index"], body["tree_size"], bundle["inclusion"], body["root_hash"]):
        return False, "not_included"
    return True, "ok"


def transparency_selftest(n: int = 7) -> dict:
    """A hermetic P3-T02 demonstration: build a log of `n` release envelopes, emit an offline proof for one,
    and verify it against an EPHEMERAL pinned root (so no committed private key is needed) WITHOUT consulting
    any live log. Then confirm four refusals — unsigned STH, forged STH root, tampered leaf, wrong index —
    each fail offline. Asserts the committed TUF root is pinned. `ok` iff every property holds. Needs openssl.
    """
    import base64
    import subprocess
    import tempfile
    d = tempfile.mkdtemp(prefix="translog-")
    priv, pub = os.path.join(d, "p.key"), os.path.join(d, "p.pub")
    subprocess.run(["openssl", "genpkey", "-algorithm", "ed25519", "-out", priv], check=True, capture_output=True)
    subprocess.run(["openssl", "pkey", "-in", priv, "-pubout", "-out", pub], check=True, capture_output=True)

    envelopes = [{"payloadType": "application/vnd.cyberware.release+json",
                  "payload": base64.b64encode(canonical.canonical_bytes({"release": i})).decode(),
                  "signatures": [{"keyid": "publisher-root", "sig": "x"}]} for i in range(n)]
    leaves = [leaf_hash(e) for e in envelopes]
    target = n // 2
    bundle = offline_proof(envelopes[target], target, leaves, priv)

    valid_ok = verify_offline(bundle, pub)[0]
    every_index_ok = all(verify_offline(offline_proof(envelopes[i], i, leaves, priv), pub)[0] for i in range(n))

    unsigned = {**bundle, "sth": {**bundle["sth"], "signatures": []}}
    unsigned_refused = not verify_offline(unsigned, pub)[0]

    body = json.loads(base64.b64decode(bundle["sth"]["payload"]))
    body["root_hash"] = "0" * 64
    forged_sth = {**bundle, "sth": {**bundle["sth"],
                  "payload": base64.b64encode(canonical.canonical_bytes(body)).decode()}}
    forged_refused = not verify_offline(forged_sth, pub)[0]

    tampered_leaf = {**bundle, "leaf": "0" * 64}
    tampered_refused = not verify_offline(tampered_leaf, pub)[0]

    # point the proof at a different leaf; vacuously satisfied for a single-leaf tree (no other index)
    wrong_index_refused = n < 2 or not verify_offline({**bundle, "index": (target + 1) % n}, pub)[0]

    return {"valid_verifies_offline": valid_ok, "every_leaf_verifies": every_index_ok,
            "unsigned_sth_refused": unsigned_refused, "forged_sth_refused": forged_refused,
            "tampered_leaf_refused": tampered_refused, "wrong_index_refused": wrong_index_refused,
            "tree_size": n, "tuf_root_pinned": os.path.isfile(PINNED_ROOT),
            "ok": (valid_ok and every_index_ok and unsigned_refused and forged_refused
                   and tampered_refused and wrong_index_refused and os.path.isfile(PINNED_ROOT))}
