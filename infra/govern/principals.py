#!/usr/bin/env python3
"""infra/govern/principals.py — principal authentication + rate-limiting for govd (P1-T08, SV-2 / F5).

The agent-mode syscall boundary's IDENTITY check. A govd request carries `Authorization: Bearer <token>`; the
token's sha256 is matched against the principals registry (`id -> token_sha -> quota`). A missing/unknown
token is rejected (govd answers 401); a principal over its token-bucket quota is throttled (429); an
authenticated request's principal id is recorded on every provenance record. Token VALUES never enter the
registry or the ledger — only the sha256 and the principal id (identity, not capability). This is the
prose-clean decision core (pinned both-sides by tests/test_principals.py); govd.py calls it thinly.
"""
from __future__ import annotations
import hashlib
import hmac
import json
import os


def token_sha(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()


def load_principals(path: str) -> dict:
    """The registry `{principal_id: {token_sha, rate, burst}}`. Absent/empty file -> {} — auth DISABLED
    (local dev keeps working); a present registry makes Bearer auth mandatory."""
    if not (path and os.path.isfile(path)):
        return {}
    return json.load(open(path)).get("principals", {})


def authenticate(bearer: str, principals: dict):
    """The principal_id whose token_sha matches the bearer's sha256, else None. Constant-time compare so a
    wrong token leaks no timing. An empty/missing bearer is None (govd -> 401)."""
    if not bearer:
        return None
    want = token_sha(bearer)
    for pid, spec in principals.items():
        if hmac.compare_digest(str(spec.get("token_sha", "")), want):
            return pid
    return None


def bearer_of(authorization: str) -> str:
    """Extract the token from an `Authorization: Bearer <token>` header (query tokens are NOT accepted)."""
    if not authorization:
        return ""
    parts = authorization.split(None, 1)
    if len(parts) == 2 and parts[0].lower() == "bearer":
        return parts[1].strip()
    return ""


def rate_ok(bucket: dict, now: float, rate: float, burst: float) -> bool:
    """Token-bucket: refill `rate` tokens/sec up to a `burst` ceiling, then consume one. Mutates `bucket`
    ({tokens, ts}) in place. Returns True iff a token was available (allowed); False throttles (govd -> 429)."""
    last = bucket.get("ts", now)
    tokens = min(burst, bucket.get("tokens", burst) + max(0.0, now - last) * rate)
    if tokens >= 1.0:
        bucket["tokens"] = tokens - 1.0
        bucket["ts"] = now
        return True
    bucket["tokens"] = tokens
    bucket["ts"] = now
    return False


def record_has_principal(record: dict) -> bool:
    """A provenance record carries its principal iff `principal` is present and non-empty."""
    return bool(record.get("principal"))


def principals_selftest() -> dict:
    """P1-T08: a missing/wrong Bearer authenticates to no principal (-> 401); a valid Bearer maps to its id;
    a burst of `burst` is allowed then the next is throttled (-> 429) and the bucket refills over time; the
    token VALUE is never in the registry; and every authenticated provenance record carries its principal
    (a record without one is caught). `ok` iff all hold."""
    reg = {"agent-a": {"token_sha": token_sha("secret-A"), "rate": 1.0, "burst": 3}}
    no_token = authenticate(bearer_of(""), reg) is None
    wrong = authenticate(bearer_of("Bearer nope"), reg) is None
    query_token_rejected = bearer_of("token=secret-A") == ""                # only Authorization: Bearer
    authed = authenticate(bearer_of("Bearer secret-A"), reg) == "agent-a"

    bucket = {}
    burst_allowed = sum(1 for _ in range(3) if rate_ok(bucket, 1000.0, 1.0, 3))   # 3 at the same instant
    throttled = not rate_ok(bucket, 1000.0, 1.0, 3)                               # the 4th is denied
    refills = rate_ok(bucket, 1002.0, 1.0, 3)                                     # 2s later -> a token back

    token_value_never_stored = all("token" not in spec for spec in reg.values())
    every_record_carries_principal = (record_has_principal({"run_id": "r", "principal": "agent-a"})
                                      and not record_has_principal({"run_id": "r"}))

    ok = (no_token and wrong and query_token_rejected and authed and burst_allowed == 3 and throttled
          and refills and token_value_never_stored and every_record_carries_principal)
    return {"no_token_rejected_401": no_token, "wrong_token_rejected": wrong,
            "query_token_rejected": query_token_rejected, "authed_to_principal": authed,
            "burst_then_throttle_429": burst_allowed == 3 and throttled, "bucket_refills": refills,
            "token_value_never_stored": token_value_never_stored,
            "every_record_carries_principal": every_record_carries_principal, "ok": ok}


if __name__ == "__main__":
    import sys
    r = principals_selftest()
    print(json.dumps(r, indent=2))
    sys.exit(0 if r["ok"] else 1)
