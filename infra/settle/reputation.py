#!/usr/bin/env python3
"""infra/settle/reputation.py — principal reputation from public ledger data (P6-T13, SV-6 / M6).

Per-principal scores computed from PUBLIC ledger data ALONE (payee credits + settlement counts), so a third
party recomputes the identical score + FMV point from the public chain — and the score table is Ed25519-signed
(tamper-evident). The `/rep` view is privacy-gated: an authenticated counterparty sees per-principal detail;
everyone else sees aggregates only (n_principals + a public FMV point + an aggregate score, never per-principal
names or scores).
"""
from __future__ import annotations

import statistics

from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey, Ed25519PublicKey

from infra.cwp import canonical
from infra.settle.money import Money


def _payee_credits(entries) -> dict:
    """Public payee credits from the ledger: principal -> [credit amount, ...] (one per settlement credit)."""
    out = {}
    for e in entries:
        if e.get("type") != "posting_set":
            continue
        for p in e["postings"]:
            a = p["account"]
            amt = Money(p["amount"]).amount
            if a.startswith("payee:") and amt > 0:
                out.setdefault(a.split(":", 1)[1], []).append(amt)
    return out


def compute_scores(entries) -> dict:
    """Deterministic per-principal reputation from public data: settlement_count, settled_total, and a
    count-weighted score; plus a public fmv_point (median credit). Recomputable by ANYONE from the public
    ledger (no private inputs), so a third party reproduces it byte-for-byte."""
    credits = _payee_credits(entries)
    principals = {n: {"settlement_count": len(v), "settled_total": str(sum(v)),
                      "score": len(v) * 10 + int(sum(v))}
                  for n, v in sorted(credits.items())}
    allc = sorted(a for v in credits.values() for a in v)
    fmv_point = str(statistics.median(allc)) if allc else "0"
    return {"principals": principals, "fmv_point": fmv_point, "n_principals": len(principals)}


def _msg(scores: dict) -> bytes:
    return bytes.fromhex(canonical.digest(scores))             # canonical (RFC 8785) digest of the score table


def sign_scores(scores: dict, priv: Ed25519PrivateKey) -> str:
    return priv.sign(_msg(scores)).hex()


def verify_scores(scores: dict, sig_hex: str, pub: Ed25519PublicKey) -> bool:
    try:
        pub.verify(bytes.fromhex(sig_hex), _msg(scores))
        return True
    except Exception:
        return False


def rep_view(scores: dict, requester: str, counterparties) -> dict:
    """The privacy gate. A requester that is a counterparty (authenticated) gets per-principal detail; anyone
    else gets aggregates ONLY — never per-principal names or scores."""
    if requester in (counterparties or set()):
        return {"authorized": True, "principals": scores["principals"], "fmv_point": scores["fmv_point"]}
    return {"authorized": False, "n_principals": scores["n_principals"], "fmv_point": scores["fmv_point"],
            "aggregate_score": sum(p["score"] for p in scores["principals"].values())}


def reputation_selftest() -> dict:
    """P6-T13: scores recompute identically from the public ledger (third-party reproducible) and the table
    verifies under its signature (a tamper breaks it); the /rep view gives a counterparty per-principal detail
    while a stranger gets aggregates only. `ok` iff all hold."""
    from infra.settle import reward_ledger
    led = reward_ledger.open_ledger()
    for name, amt in [("bob", "100.0000"), ("bob", "50.0000"), ("carol", "30.0000")]:
        reward_ledger.post(led, [reward_ledger._posting("treasury", -Money(amt)),
                                 reward_ledger._posting(f"payee:{name}", Money(amt))], memo="rel")

    s1 = compute_scores(led)
    s2 = compute_scores(led)                                   # an independent third party recomputes
    reproducible = (canonical.digest(s1) == canonical.digest(s2)
                    and s1["principals"]["bob"]["settlement_count"] == 2
                    and s1["principals"]["carol"]["settlement_count"] == 1)

    priv = Ed25519PrivateKey.generate()
    pub = priv.public_key()
    sig = sign_scores(s1, priv)
    signed_ok = verify_scores(s1, sig, pub) and not verify_scores({**s1, "fmv_point": "999"}, sig, pub)

    cp = rep_view(s1, "bob", {"bob"})
    stranger = rep_view(s1, "eve", {"bob"})
    rep_privacy = (cp["authorized"] and "principals" in cp
                   and not stranger["authorized"] and "principals" not in stranger
                   and "aggregate_score" in stranger and "fmv_point" in stranger)

    return {"third_party_reproducible": reproducible, "scores_signed_and_verify": signed_ok,
            "rep_privacy": rep_privacy, "ok": reproducible and signed_ok and rep_privacy}


if __name__ == "__main__":
    import json
    import sys
    r = reputation_selftest()
    print(json.dumps(r, indent=2))
    sys.exit(0 if r.get("ok") else 1)
