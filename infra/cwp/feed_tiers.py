#!/usr/bin/env python3
"""infra/cwp/feed_tiers.py — revocation-feed availability tiers + grace policy (P3-T12, SV-4 / M3).

When the revocation feed cannot be refreshed (the feed service is down), the system must degrade gracefully,
not fall over and not silently keep trusting an arbitrarily old feed. Staleness is bucketed into tiers:

  * **FRESH** (age ≤ max_age) — normal operation.
  * **GRACE-1 / GRACE-2** (age within the grace windows) — **read-only operations proceed**, **destructive
    operations refuse**. The system keeps serving safe traffic through a bounded outage.
  * **EXPIRED** (beyond grace-2) — everything refuses; the feed is too old to trust at all (fail closed).

A feed must always be authentically signed (a forged feed is refused at every tier). Recovery needs **no
manual ledger surgery**: the decision is a pure function of the current feed + clock, so presenting a fresh
feed instantly re-converges to FRESH — nothing persistent was mutated during the outage to undo.
"""
from __future__ import annotations
import base64
import json
import os

from infra.cwp import cosign, revocation

_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
PINNED_ROOT = os.path.join(_ROOT, "spec", "tuf", "publisher-root.pub")
FRESH, GRACE_1, GRACE_2, EXPIRED = "fresh", "grace-1", "grace-2", "expired"


def tier_for(age: int, max_age: int, grace1: int, grace2: int) -> str:
    """Bucket a feed age into an availability tier."""
    if age <= max_age:
        return FRESH
    if age <= max_age + grace1:
        return GRACE_1
    if age <= max_age + grace1 + grace2:
        return GRACE_2
    return EXPIRED


def decision(feed: dict, destructive: bool, now: int, max_age: int = 600, grace1: int = 600,
             grace2: int = 1800, artifact_id: str = None, pinned_pub_pem: str = PINNED_ROOT) -> dict:
    """The graceful-degradation gate. A forged feed refuses everywhere; otherwise the tier governs: FRESH →
    proceed, GRACE-* → read-only only, EXPIRED → refuse. A listed artifact is refused while the feed is still
    trusted at all. Returns {allow, tier, reason}."""
    if not isinstance(feed, dict) or feed.get("payloadType") != revocation.FEED_TYPE:
        return {"allow": False, "tier": None, "reason": "wrong_type"}
    if not feed.get("signatures") or not cosign.verify_ph(feed, pinned_pub_pem):
        return {"allow": False, "tier": None, "reason": "bad_signature"}
    try:
        body = json.loads(base64.b64decode(feed["payload"]))
    except Exception:
        return {"allow": False, "tier": None, "reason": "bad_signature"}

    tier = tier_for(now - body["issued"], max_age, grace1, grace2)
    if tier == EXPIRED:
        return {"allow": False, "tier": tier, "reason": "feed_expired"}
    if artifact_id is not None and artifact_id in body.get("revoked", []):
        return {"allow": False, "tier": tier, "reason": "revoked"}
    if tier in (GRACE_1, GRACE_2) and destructive:
        return {"allow": False, "tier": tier, "reason": "grace_destructive_refused"}
    return {"allow": True, "tier": tier, "reason": "ok"}


def tiers_selftest() -> dict:
    """A hermetic P3-T12 outage drill with an EPHEMERAL key and a fixed clock: at FRESH both read-only and
    destructive proceed; through GRACE-1 and GRACE-2 read-only proceeds while destructive refuses; past
    grace-2 (EXPIRED) everything refuses (fail closed); a forged feed refuses at every tier; and recovery —
    presenting a fresh feed — re-converges to FRESH with no state mutation. `ok` iff every property holds."""
    import subprocess
    import tempfile
    d = tempfile.mkdtemp(prefix="feedtiers-")
    priv, pub = os.path.join(d, "p.key"), os.path.join(d, "p.pub")
    subprocess.run(["openssl", "genpkey", "-algorithm", "ed25519", "-out", priv], check=True, capture_output=True)
    subprocess.run(["openssl", "pkey", "-in", priv, "-pubout", "-out", pub], check=True, capture_output=True)
    MAXAGE, G1, G2 = 600, 600, 1800
    issued = 1_700_000_000
    feed = revocation.sign_feed(1, [], issued, 999_999, priv)   # long ttl so 'expires' never gates; tier does

    def at(age, destructive):
        return decision(feed, destructive, issued + age, MAXAGE, G1, G2, pinned_pub_pem=pub)

    fresh_ro = at(10, False)["allow"] and at(10, False)["tier"] == FRESH
    fresh_destr = at(10, True)["allow"]
    g1 = at(MAXAGE + 100, False)["allow"] and not at(MAXAGE + 100, True)["allow"]
    g1_tier = at(MAXAGE + 100, False)["tier"] == GRACE_1
    g2 = at(MAXAGE + G1 + 100, False)["allow"] and not at(MAXAGE + G1 + 100, True)["allow"]
    g2_tier = at(MAXAGE + G1 + 100, False)["tier"] == GRACE_2
    expired_ro = not at(MAXAGE + G1 + G2 + 100, False)["allow"]
    expired_destr = not at(MAXAGE + G1 + G2 + 100, True)["allow"]

    forged = {**feed, "signatures": []}
    forged_refused = not decision(forged, False, issued + 10, pinned_pub_pem=pub)["allow"]

    # recovery: a fresh feed presented after the outage → FRESH again, both ops proceed (no ledger surgery)
    fresh_feed = revocation.sign_feed(2, [], issued + 10_000, 999_999, priv)
    rec = decision(fresh_feed, True, issued + 10_010, MAXAGE, G1, G2, pinned_pub_pem=pub)
    recovered = rec["allow"] and rec["tier"] == FRESH

    return {"fresh_read_only": fresh_ro, "fresh_destructive": fresh_destr,
            "grace1_read_only_only": g1 and g1_tier, "grace2_read_only_only": g2 and g2_tier,
            "expired_fails_closed": expired_ro and expired_destr, "forged_refused": forged_refused,
            "recovery_reconverges": recovered, "tuf_root_pinned": os.path.isfile(PINNED_ROOT),
            "ok": (fresh_ro and fresh_destr and g1 and g1_tier and g2 and g2_tier and expired_ro
                   and expired_destr and forged_refused and recovered and os.path.isfile(PINNED_ROOT))}
