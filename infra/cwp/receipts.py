#!/usr/bin/env python3
"""infra/cwp/receipts.py — finalized dual-signed receipts (P3-T14, SV-4 / M0).

A governed run's receipt is the durable proof of what happened. To be trustworthy it is:

  * **dual-signed** — TWO independent Ed25519-DSSE signatures over the SAME in-toto statement (e.g. the
    executor that ran it and the approver/oversight that blessed it). Neither party alone can forge a
    receipt; both signatures must verify.
  * **in-toto consumable** — the signed payload is a real in-toto Statement (subject digest + predicate), so
    the receipt is a standard attestation a cosign `verify-attestation` consumer accepts, not a bespoke blob.

A receipt with only one signature, or a tampered statement, is not a finalized receipt.
"""
from __future__ import annotations
import base64
import json
import os

from infra.cwp import canonical, cosign, sign

RECEIPT_PREDICATE = "https://cyberware.dev/predicates/run-receipt/v1"


def finalize_receipt(run_name: str, run_sha: str, predicate: dict, priv_a: str, kid_a: str,
                     priv_b: str, kid_b: str) -> dict:
    """Build the in-toto receipt statement and DSSE-sign it with BOTH keys → one envelope, two signatures."""
    stmt = cosign.intoto_statement(run_name, run_sha, RECEIPT_PREDICATE, predicate)
    payload = canonical.canonical_bytes(stmt)
    pae = sign.pae(cosign.IN_TOTO_TYPE, payload)
    return {"payload": base64.b64encode(payload).decode(), "payloadType": cosign.IN_TOTO_TYPE,
            "signatures": [{"keyid": kid_a, "sig": base64.b64encode(cosign.ph_sign(pae, priv_a)).decode()},
                           {"keyid": kid_b, "sig": base64.b64encode(cosign.ph_sign(pae, priv_b)).decode()}]}


def _statement(receipt: dict):
    try:
        return json.loads(base64.b64decode(receipt["payload"]))
    except Exception:
        return None


def verify_receipt(receipt: dict, pub_a: str, pub_b: str) -> dict:
    """Verify a finalized receipt: BOTH distinct keys' signatures verify (dual_signed), and the payload is a
    consumable in-toto Statement. Returns {dual_signed, in_toto_consumable, ok}."""
    if not isinstance(receipt, dict) or receipt.get("payloadType") != cosign.IN_TOTO_TYPE:
        return {"dual_signed": False, "in_toto_consumable": False, "ok": False}
    a_ok = cosign.verify_ph(receipt, pub_a)
    b_ok = cosign.verify_ph(receipt, pub_b)
    distinct = len({s.get("keyid") for s in receipt.get("signatures", [])}) >= 2
    dual_signed = a_ok and b_ok and distinct
    stmt = _statement(receipt)
    consumable = bool(stmt and stmt.get("_type", "").startswith("https://in-toto.io/Statement")
                      and stmt.get("subject") and stmt.get("predicateType"))
    return {"dual_signed": dual_signed, "in_toto_consumable": consumable, "ok": dual_signed and consumable}


def receipts_selftest() -> dict:
    """A hermetic P3-T14 demonstration with EPHEMERAL executor + approver keys: a finalized receipt is
    dual-signed and in-toto consumable; a receipt missing the second signature is NOT dual-signed; a
    tampered statement (one signature recomputed, the other stale) fails to verify; and two signatures from
    the SAME key do not count as dual-signed. `ok` iff every property holds. Needs openssl (ed25519ph)."""
    import subprocess
    import tempfile
    d = tempfile.mkdtemp(prefix="receipts-")

    def keypair(tag):
        p, pub = os.path.join(d, f"{tag}.key"), os.path.join(d, f"{tag}.pub")
        subprocess.run(["openssl", "genpkey", "-algorithm", "ed25519", "-out", p], check=True, capture_output=True)
        subprocess.run(["openssl", "pkey", "-in", p, "-pubout", "-out", pub], check=True, capture_output=True)
        return p, pub

    ax, ap = keypair("executor")
    bx, bp = keypair("approver")
    predicate = {"run_id": "run-123", "outcome": "ok", "steps": 3}
    receipt = finalize_receipt("run-123", "a" * 64, predicate, ax, "executor", bx, "approver")

    good = verify_receipt(receipt, ap, bp)
    dual_ok = good["dual_signed"] and good["in_toto_consumable"] and good["ok"]

    single = {**receipt, "signatures": receipt["signatures"][:1]}
    single_not_dual = not verify_receipt(single, ap, bp)["dual_signed"]

    tampered_stmt = {**receipt, "payload": base64.b64encode(canonical.canonical_bytes(
        cosign.intoto_statement("run-123", "0" * 64, RECEIPT_PREDICATE, predicate))).decode()}
    tamper_refused = not verify_receipt(tampered_stmt, ap, bp)["ok"]

    # two signatures from the SAME private key (different kid labels) must not pass as dual-signed against
    # two DISTINCT public keys — only one of (ap, bp) actually verifies the executor's signature
    same_key = finalize_receipt("run-123", "a" * 64, predicate, ax, "executor", ax, "executor-2")
    same_key_single_pub = verify_receipt(same_key, ap, bp)["dual_signed"] is False

    return {"dual_signed_and_consumable": dual_ok, "single_signature_not_dual": single_not_dual,
            "tampered_statement_refused": tamper_refused, "same_key_not_dual": same_key_single_pub,
            "ok": dual_ok and single_not_dual and tamper_refused and same_key_single_pub}
