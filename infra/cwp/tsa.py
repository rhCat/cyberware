#!/usr/bin/env python3
"""infra/cwp/tsa.py — trusted timestamp anchors on high-value receipts (P3-T07, SV-4 / M8).

A high-value receipt must carry an independent proof of *when* it existed, so its settlement cannot be
back- or post-dated. A Time-Stamping Authority (RFC-3161-shaped) countersigns the receipt's digest with a
trusted clock; the token is `{receipt_sha, time}` signed by the TSA key and verifiable **offline** against
the pinned TSA chain — no live TSA call at verification time. The settlement rule:

  * a receipt whose value is **at or above** the threshold is settlement-eligible only if it carries a TSA
    token that verifies (absence or a tampered token blocks settlement),
  * a receipt **below** the threshold settles without one.

So the time anchor is mandatory exactly where it matters, and its absence is a hard stop, not a warning.
"""
from __future__ import annotations
import hashlib
import os

from infra.cwp import canonical, cosign

_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
PINNED_ROOT = os.path.join(_ROOT, "spec", "tuf", "publisher-root.pub")
DEFAULT_THRESHOLD = 1000


def receipt_digest(receipt: dict) -> str:
    """The receipt's content digest — what the TSA countersigns."""
    return hashlib.sha256(canonical.canonical_bytes(receipt)).hexdigest()


def timestamp(receipt: dict, when: int, tsa_priv_pem: str) -> dict:
    """The TSA countersignature: `{receipt_sha, time}` signed by the TSA key (cosign-shaped DSSE)."""
    body = {"receipt_sha": receipt_digest(receipt), "time": when}
    env = cosign.sign_ph(canonical.canonical_bytes(body), tsa_priv_pem,
                         payload_type="application/vnd.cyberware.tsa+json", keyid="tsa-anchor")
    return {"token": env, "receipt_sha": body["receipt_sha"], "time": when}


def verify_token(token: dict, receipt: dict, tsa_pub_pem: str) -> bool:
    """Offline verification: the token signs THIS receipt's digest and verifies under the pinned TSA key."""
    if not isinstance(token, dict) or token.get("receipt_sha") != receipt_digest(receipt):
        return False
    return cosign.verify_ph(token.get("token", {}), tsa_pub_pem)


def settlement_eligible(receipt: dict, token, value: int, tsa_pub_pem: str,
                        threshold: int = DEFAULT_THRESHOLD) -> dict:
    """A receipt at/above `threshold` is eligible only with a valid TSA token; below it, eligible without.
    Returns {eligible, reason}."""
    if value < threshold:
        return {"eligible": True, "reason": "below_threshold"}
    if not token:
        return {"eligible": False, "reason": "tsa_missing"}
    if not verify_token(token, receipt, tsa_pub_pem):
        return {"eligible": False, "reason": "tsa_invalid"}
    return {"eligible": True, "reason": "tsa_verified"}


def tsa_selftest() -> dict:
    """A hermetic P3-T07 demonstration with an EPHEMERAL TSA key: a TSA token verifies OFFLINE against the
    receipt digest; a high-value receipt with a valid token is settlement-eligible; the SAME receipt with no
    token (and with a tampered token, and a token bound to a different receipt) is NOT eligible; a low-value
    receipt settles without a token. `ok` iff every property holds. Needs openssl (ed25519ph)."""
    import subprocess
    import tempfile
    d = tempfile.mkdtemp(prefix="tsa-")
    priv, pub = os.path.join(d, "tsa.key"), os.path.join(d, "tsa.pub")
    subprocess.run(["openssl", "genpkey", "-algorithm", "ed25519", "-out", priv], check=True, capture_output=True)
    subprocess.run(["openssl", "pkey", "-in", priv, "-pubout", "-out", pub], check=True, capture_output=True)

    receipt = {"run_id": "run-9", "amount": 5000, "payee": "alice"}
    tok = timestamp(receipt, 1_700_000_500, priv)

    verifies_offline = verify_token(tok, receipt, pub)
    high_with_token = settlement_eligible(receipt, tok, 5000, pub)["eligible"]
    high_without = settlement_eligible(receipt, None, 5000, pub)
    high_missing_blocked = high_without["eligible"] is False and high_without["reason"] == "tsa_missing"

    other_token = timestamp({"run_id": "run-OTHER"}, 1_700_000_500, priv)
    wrong_receipt_blocked = not settlement_eligible(receipt, other_token, 5000, pub)["eligible"]

    tampered = {**tok, "token": {**tok["token"], "signatures": []}}
    tampered_blocked = not settlement_eligible(receipt, tampered, 5000, pub)["eligible"]

    low_no_token = settlement_eligible(receipt, None, 10, pub)["eligible"]

    return {"token_verifies_offline": verifies_offline, "high_value_with_token_eligible": high_with_token,
            "absence_blocks_settlement": high_missing_blocked, "wrong_receipt_token_blocked": wrong_receipt_blocked,
            "tampered_token_blocked": tampered_blocked, "low_value_settles_without_token": low_no_token,
            "tuf_root_pinned": os.path.isfile(PINNED_ROOT),
            "ok": (verifies_offline and high_with_token and high_missing_blocked and wrong_receipt_blocked
                   and tampered_blocked and low_no_token and os.path.isfile(PINNED_ROOT))}
