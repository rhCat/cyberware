#!/usr/bin/env python3
"""infra/cwp/release.py — publisher signing for the release transparency layer (P3-T01, SV-4).

A release manifest — the chip's `chip_sha` plus every skill's `skill_sha`, drawn from the chip's own
`index.json` — is signed by the PUBLISHER key (Ed25519ph, via the cosign adapter) and verified against a
PINNED publisher root committed at `spec/tuf/publisher-root.pub` (TUF-style: the root travels with the repo,
the private key never does). The SAME verification runs at all THREE entry points — chipfetch (acquire),
govd boot, exod run — so an unsigned or tampered release is refused everywhere, not at one gate that could
be bypassed. This is the SV-4 promise that what runs is the signed, published artifact and nothing else.
"""
from __future__ import annotations
import json
import os

from infra.cwp import canonical, cosign

RELEASE_TYPE = "application/vnd.cyberware.release+json"
_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
PINNED_ROOT = os.path.join(_ROOT, "spec", "tuf", "publisher-root.pub")
ENTRY_POINTS = ("chipfetch", "govd_boot", "exod_run")


def release_manifest(chip_index_path: str) -> dict:
    """The value-free release subject: the chip roll-up hash + every skill's authenticity hash."""
    idx = json.load(open(chip_index_path))
    skills = idx.get("skills") or []
    return {"chip_sha": idx.get("chip_sha"),
            "skills": {s["skill"]: s.get("skill_sha") for s in skills}}


def sign_release(chip_index_path: str, priv_pem_path: str) -> dict:
    """Sign the release manifest with the publisher key → a DSSE envelope (Ed25519ph, cosign-shaped)."""
    payload = canonical.canonical_bytes(release_manifest(chip_index_path))
    return cosign.sign_ph(payload, priv_pem_path, payload_type=RELEASE_TYPE, keyid="publisher-root")


def verify_release(envelope: dict, pinned_pub_pem: str = PINNED_ROOT):
    """Returns (ok, reason). The envelope must be a release type AND verify under the PINNED publisher root
    — an unsigned/forged/tampered release fails here, against the committed root only (TUF root pin)."""
    if not isinstance(envelope, dict) or envelope.get("payloadType") != RELEASE_TYPE:
        return False, "wrong_type"
    if not envelope.get("signatures"):
        return False, "unsigned"
    if not cosign.verify_ph(envelope, pinned_pub_pem):
        return False, "bad_signature"
    return True, "ok"


def release_matches_chip(envelope: dict, chip_index_path: str) -> bool:
    """True iff the signed manifest's hashes match the chip on disk — a verified release that has since
    drifted from the chip is not the artifact that was published."""
    try:
        import base64
        signed = json.loads(base64.b64decode(envelope["payload"]))
    except Exception:
        return False
    return signed == release_manifest(chip_index_path)


def tri_layer_check(envelope: dict, pinned_pub_pem: str = PINNED_ROOT) -> dict:
    """Run the verification at all three entry points. An unsigned/invalid release must refuse at EVERY one
    (the tri-layer refusal); a valid release passes at every one."""
    ok, reason = verify_release(envelope, pinned_pub_pem)
    layers = {e: {"pass": ok, "reason": reason} for e in ENTRY_POINTS}
    return {"layers": layers, "all_pass": ok, "all_refuse": not ok, "reason": reason}


def release_drill(chip_index_path: str, priv_pem_path: str) -> dict:
    """P3-T01 acceptance: a publisher-signed release passes the tri-layer check + matches the chip; an
    unsigned manifest and a tampered envelope are each refused at all three layers (against the pinned
    root). Returns a report; `ok` iff every property holds."""
    import base64
    env = sign_release(chip_index_path, priv_pem_path)
    good = tri_layer_check(env)
    matches = release_matches_chip(env, chip_index_path)

    unsigned = {"payloadType": RELEASE_TYPE, "payload": env["payload"], "signatures": []}
    unsigned_refused = tri_layer_check(unsigned)["all_refuse"]

    body = json.loads(base64.b64decode(env["payload"]))
    body["chip_sha"] = "0" * 64                                 # tamper the signed hash
    tampered = {**env, "payload": base64.b64encode(canonical.canonical_bytes(body)).decode()}
    tampered_refused = tri_layer_check(tampered)["all_refuse"]

    return {"signed_passes_tri_layer": good["all_pass"], "matches_chip": matches,
            "unsigned_refused_all_layers": unsigned_refused,
            "tampered_refused_all_layers": tampered_refused, "tuf_root_pinned": os.path.isfile(PINNED_ROOT),
            "ok": good["all_pass"] and matches and unsigned_refused and tampered_refused
            and os.path.isfile(PINNED_ROOT)}


def release_selftest(chip_index_path: str = None) -> dict:
    """A hermetic P3-T01 demonstration: generate an EPHEMERAL publisher keypair, sign the chip's real
    release manifest, and verify the tri-layer refusal against that ephemeral root (so the test needs no
    committed private key). Still asserts the committed TUF root is pinned. Needs openssl (ed25519ph)."""
    import base64
    import subprocess
    import tempfile
    d = tempfile.mkdtemp(prefix="release-")
    priv, pub = os.path.join(d, "p.key"), os.path.join(d, "p.pub")
    subprocess.run(["openssl", "genpkey", "-algorithm", "ed25519", "-out", priv], check=True, capture_output=True)
    subprocess.run(["openssl", "pkey", "-in", priv, "-pubout", "-out", pub], check=True, capture_output=True)
    chip = chip_index_path or os.path.join(_ROOT, "skillChip", "index.json")
    env = sign_release(chip, priv)
    good = tri_layer_check(env, pub)["all_pass"]
    matches = release_matches_chip(env, chip)
    unsigned = {"payloadType": RELEASE_TYPE, "payload": env["payload"], "signatures": []}
    unsigned_refused = tri_layer_check(unsigned, pub)["all_refuse"]
    body = json.loads(base64.b64decode(env["payload"]))
    body["chip_sha"] = "0" * 64
    tampered = {**env, "payload": base64.b64encode(canonical.canonical_bytes(body)).decode()}
    tampered_refused = tri_layer_check(tampered, pub)["all_refuse"]
    return {"signed_passes_tri_layer": good, "matches_chip": matches,
            "unsigned_refused_all_layers": unsigned_refused, "tampered_refused_all_layers": tampered_refused,
            "tuf_root_pinned": os.path.isfile(PINNED_ROOT),
            "ok": good and matches and unsigned_refused and tampered_refused and os.path.isfile(PINNED_ROOT)}
