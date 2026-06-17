#!/usr/bin/env python3
"""infra/cwp/revocation.py — the signed revocation feed (P3-T03, SV-4).

A monotonic, publisher-signed feed names what must no longer run: `{seq, issued, expires, revoked[]}` where
each entry is a skill_sha, key id, or engine digest. The feed is a DSSE signed under the PINNED publisher
root, and three properties make it trustworthy:

  * **freshness** — a feed older than `max_age` is `feed_stale`; a consumer that cannot refresh must not keep
    trusting a frozen feed (this is what bounds revocation latency: govd refuses by T+interval, exod on its
    next run).
  * **no rollback** — `seq` is strictly monotonic; replaying an older feed (to un-revoke something) is
    `rollback` and refused.
  * **authenticity** — an unsigned or forged feed is `bad_signature`.

A consumer pins the last accepted `seq` and the current time, verifies the feed, and refuses any artifact the
accepted feed lists. Revocation fails *closed*: if the feed is stale or rolled back, nothing new is trusted.
"""
from __future__ import annotations
import base64
import json
import os

from infra.cwp import canonical, cosign

FEED_TYPE = "application/vnd.cyberware.revocation+json"
_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
PINNED_ROOT = os.path.join(_ROOT, "spec", "tuf", "publisher-root.pub")
DEFAULT_MAX_AGE = 3600                                          # a feed older than this (seconds) is stale


def sign_feed(seq: int, revoked, issued: int, ttl: int, priv_pem_path: str) -> dict:
    """Publisher-sign a revocation feed: `{seq, issued, expires, revoked[]}` (cosign-shaped, Ed25519ph)."""
    body = {"seq": seq, "issued": issued, "expires": issued + ttl, "revoked": sorted(set(revoked))}
    return cosign.sign_ph(canonical.canonical_bytes(body), priv_pem_path, payload_type=FEED_TYPE,
                          keyid="publisher-root")


def _body(feed: dict):
    try:
        return json.loads(base64.b64decode(feed["payload"]))
    except Exception:
        return None


def verify_feed(feed: dict, now: int, last_seq: int = -1, max_age: int = DEFAULT_MAX_AGE,
                pinned_pub_pem: str = PINNED_ROOT):
    """Returns (ok, reason, body). A feed is trusted only if it is the right type, verifies under the pinned
    root, is not past its expiry or older than `max_age`, and advances `seq` beyond the last accepted one.
    reason ∈ {ok, wrong_type, bad_signature, feed_stale, rollback}."""
    if not isinstance(feed, dict) or feed.get("payloadType") != FEED_TYPE:
        return False, "wrong_type", None
    if not feed.get("signatures") or not cosign.verify_ph(feed, pinned_pub_pem):
        return False, "bad_signature", None
    body = _body(feed)
    if body is None:
        return False, "bad_signature", None
    if now > body["expires"] or now - body["issued"] > max_age:
        return False, "feed_stale", body
    if body["seq"] <= last_seq:
        return False, "rollback", body
    return True, "ok", body


def is_revoked(feed: dict, artifact_id: str, now: int, last_seq: int = -1,
               max_age: int = DEFAULT_MAX_AGE, pinned_pub_pem: str = PINNED_ROOT) -> bool:
    """True iff a VALID (verified, fresh, non-rolled-back) feed lists `artifact_id`. A feed that does not
    verify is not consulted — but the caller must treat a failed verify as 'refuse to proceed', not 'allowed'
    (see `revocation_decision`)."""
    ok, _, body = verify_feed(feed, now, last_seq, max_age, pinned_pub_pem)
    return ok and artifact_id in body["revoked"]


def revocation_decision(feed: dict, artifact_id: str, now: int, last_seq: int = -1,
                        max_age: int = DEFAULT_MAX_AGE, pinned_pub_pem: str = PINNED_ROOT) -> dict:
    """The fail-closed gate a consumer runs: if the feed does not verify (stale/rollback/forged) the artifact
    is REFUSED (`reason`), not waved through; if the feed verifies, the artifact is refused iff it is listed.
    Returns {allow, reason}."""
    ok, reason, body = verify_feed(feed, now, last_seq, max_age, pinned_pub_pem)
    if not ok:
        return {"allow": False, "reason": reason}
    if artifact_id in body["revoked"]:
        return {"allow": False, "reason": "revoked"}
    return {"allow": True, "reason": "ok", "seq": body["seq"]}


def revocation_selftest() -> dict:
    """A hermetic P3-T03 demonstration with an EPHEMERAL publisher key and a fixed clock: accept feed seq=1
    (nothing revoked); issue seq=2 revoking artifact X and confirm X is now refused while Y still runs;
    replay seq=1 (rollback) and confirm it is refused; present an expired feed and confirm `feed_stale`;
    forge the signature and confirm `bad_signature`; and confirm the gate fails CLOSED on a stale feed (a
    previously-allowed artifact is refused). `ok` iff every property holds. Needs openssl (ed25519ph)."""
    import subprocess
    import tempfile
    d = tempfile.mkdtemp(prefix="revocation-")
    priv, pub = os.path.join(d, "p.key"), os.path.join(d, "p.pub")
    subprocess.run(["openssl", "genpkey", "-algorithm", "ed25519", "-out", priv], check=True, capture_output=True)
    subprocess.run(["openssl", "pkey", "-in", priv, "-pubout", "-out", pub], check=True, capture_output=True)
    T0 = 1_700_000_000
    X, Y = "sha256:" + "a" * 64, "sha256:" + "b" * 64

    f1 = sign_feed(1, [], T0, 3600, priv)
    accept1 = verify_feed(f1, T0 + 10, last_seq=0, pinned_pub_pem=pub)[0]

    f2 = sign_feed(2, [X], T0 + 100, 3600, priv)
    x_refused = revocation_decision(f2, X, T0 + 110, last_seq=1, pinned_pub_pem=pub)["allow"] is False
    y_allowed = revocation_decision(f2, Y, T0 + 110, last_seq=1, pinned_pub_pem=pub)["allow"] is True

    rollback_refused = verify_feed(f1, T0 + 200, last_seq=2, pinned_pub_pem=pub)[1] == "rollback"

    stale = sign_feed(3, [X], T0, 60, priv)                     # expires at T0+60
    stale_refused = verify_feed(stale, T0 + 5000, last_seq=2, pinned_pub_pem=pub)[1] == "feed_stale"
    # fail-closed: an artifact NOT on the stale feed is still refused because the feed cannot be trusted
    fail_closed = revocation_decision(stale, Y, T0 + 5000, last_seq=2, pinned_pub_pem=pub)["allow"] is False

    forged = {**f2, "signatures": []}
    forged_refused = verify_feed(forged, T0 + 110, last_seq=1, pinned_pub_pem=pub)[1] == "bad_signature"

    return {"accepts_first_feed": accept1, "revoked_artifact_refused": x_refused,
            "unrevoked_artifact_allowed": y_allowed, "rollback_refused": rollback_refused,
            "stale_refused": stale_refused, "stale_feed_fails_closed": fail_closed,
            "forged_refused": forged_refused, "tuf_root_pinned": os.path.isfile(PINNED_ROOT),
            "ok": (accept1 and x_refused and y_allowed and rollback_refused and stale_refused
                   and fail_closed and forged_refused and os.path.isfile(PINNED_ROOT))}
