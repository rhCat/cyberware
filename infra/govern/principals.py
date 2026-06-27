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


# --- per-actor ACL (M0) — capability scope bound to a token, beside its identity/quota ----------------
# A principal's optional `acl` block: {skills:[canonical id|"*"], perks:{skill:[...]}, max_tier, secrets:bool,
# expires_at?, revoked?}. It carries CANONICAL skill/perk ids + tier LABELS only — never a token value.
# acl_allows is a PURE RESTRICTION: govd APPENDS its problem to problems[] (a hard, non-self-approvable
# reject), never relaxing another gate. The decision is identical for the same inputs (testable both-sides).
_TIER_RANK = {"core": 0, "verified": 1, "community": 2}   # catalog TRUST order (NOT the sandbox backend rank)


def resolve_scope(principals: dict, pid: str):
    """The `acl` block bound to a principal (flat `principals[pid].acl`), or None when unset. Org-nested
    resolution is a later milestone; the flat lookup is the single scope source for govern(). A non-dict
    spec (operator misconfiguration) resolves to None — never RAISES on the trusted-but-fallible registry,
    so a misauthored entry cannot crash the un-try-wrapped WS step path."""
    spec = (principals or {}).get(pid)
    return spec.get("acl") if isinstance(spec, dict) else None


def acl_canonical(pid: str, tok_sha: str, acl) -> str:
    """Canonical JSON over the ACL's authoritative fields, with pid+token_sha FOLDED IN so two principals
    with an identical ACL still get DISTINCT digests (their attestations are not interchangeable)."""
    a = acl or {}
    body = {"pid": pid, "token_sha": tok_sha, "skills": a.get("skills"), "perks": a.get("perks"),
            "max_tier": a.get("max_tier"), "secrets": a.get("secrets")}
    return json.dumps(body, sort_keys=True, separators=(",", ":"))


def acl_sha(pid: str, tok_sha: str, acl) -> str:
    """sha256 over acl_canonical — recomputed by govd from LIVE registry fields (never trusted on faith).
    Consumed by the M1 grant binding; defined here so the in-process core and the limb agree on one digest."""
    return hashlib.sha256(acl_canonical(pid, tok_sha, acl).encode()).hexdigest()


def acl_allows(acl, skill, perk, perk_tier, destructive, credentialed, *, now=None, strict=False):
    """(ok, problem|None) for a CANONICAL (skill, perk) claim under an actor scope `acl`. Deny-by-default
    when an acl is present; under `strict` an absent acl denies too (the Phase-B end-state). Every branch
    fails CLOSED; the tier ceiling's fail-safes are SELF-OWNED here (None/unknown perk tier -> community, the
    least-trusted; unknown ceiling -> core, the tightest), never inherited from perk_sandbox_tier's default."""
    if acl is None:
        return (False, {"id": "acl_unscoped"}) if strict else (True, None)
    if not isinstance(acl, dict):                       # a misauthored non-dict acl fails CLOSED, never raises
        return False, {"id": "acl_malformed"}
    if acl.get("revoked"):
        return False, {"id": "acl_revoked"}
    exp = acl.get("expires_at")
    if exp is not None and (now is None or now > exp):  # expiry set but freshness unprovable -> fail CLOSED
        return False, {"id": "acl_expired", "detail": exp}
    skills = acl.get("skills")
    pmap = acl.get("perks") or {}
    allowed_skill = (skills == ["*"]) or (skills is not None and skill in skills) or (skill in pmap)
    if not allowed_skill:
        return False, {"id": "acl_skill_denied", "detail": f"{skill}/{perk}"}
    if skill in pmap and perk not in pmap[skill]:                 # perks[skill] is AUTHORITATIVE for that skill
        return False, {"id": "acl_perk_denied", "detail": f"{skill}/{perk}"}
    if destructive and not (skill in pmap and perk in pmap[skill]):   # a bare-skill grant never admits destructive
        return False, {"id": "acl_destructive_unlisted", "detail": f"{skill}/{perk}"}
    if credentialed and not acl.get("secrets"):                  # the secret axis: may this token reach creds?
        return False, {"id": "acl_secret_denied", "detail": f"{skill}/{perk}"}
    ceiling = acl.get("max_tier")
    if ceiling is not None:
        want = _TIER_RANK.get(perk_tier, 2)                      # SELF-OWNED fail-safe: None/unknown -> community
        cap = _TIER_RANK.get(ceiling, 0)                         # unknown ceiling -> core (tightest)
        if want > cap:
            return False, {"id": "acl_tier_denied", "detail": {"perk_tier": perk_tier, "max_tier": ceiling}}
    return True, None


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

    # per-actor ACL (M0): unscoped passes only when not strict; a present acl is deny-by-default; the
    # destructive/secret/tier gates and the revoked/expired bounds all fail CLOSED; acl_sha folds pid in.
    acl = {"skills": ["cws-fs"], "perks": {"cws-fs": ["read"]}, "max_tier": "verified", "secrets": False}
    bare = {"skills": ["cws-fs"]}
    acl_ok = (acl_allows(None, "x", "y", None, False, False)[0] is True                     # unscoped + lax -> allow
              and acl_allows(None, "x", "y", None, False, False, strict=True)[0] is False   # unscoped + strict -> deny
              and acl_allows(acl, "cws-fs", "read", "verified", False, False)[0] is True    # in scope
              and acl_allows(acl, "cws-net", "get", "core", False, False)[0] is False        # skill out
              and acl_allows(acl, "cws-fs", "write", "verified", False, False)[0] is False   # perk out (list authoritative)
              and acl_allows(bare, "cws-fs", "read", None, False, False)[0] is True          # bare skill -> non-destructive ok
              and acl_allows(bare, "cws-fs", "rm", None, True, False)[0] is False             # destructive needs explicit listing
              and acl_allows({"skills": ["s"]}, "s", "p", None, False, True)[0] is False      # credentialed but secrets=False
              and acl_allows({"skills": ["s"], "max_tier": "core"}, "s", "p", "community", False, False)[0] is False  # over ceiling
              and acl_allows({"skills": ["s"], "max_tier": "core"}, "s", "p", None, False, False)[0] is False         # None tier -> community
              and acl_allows({"skills": ["*"], "revoked": True}, "s", "p", None, False, False)[0] is False            # revoked
              and acl_allows({"skills": ["*"], "expires_at": 100}, "s", "p", None, False, False, now=200)[0] is False  # expired
              and acl_allows({"skills": ["*"], "expires_at": 100}, "s", "p", None, False, False)[0] is False           # expires_at + no `now` -> fail closed
              and acl_allows("not-a-dict", "s", "p", None, False, False)[0] is False                                   # malformed acl -> deny, never raise
              and acl_allows({"skills": ["*"]}, "anything", "p", None, False, False)[0] is True                       # '*' sentinel
              and resolve_scope({"p": {"acl": {"skills": ["x"]}}}, "p") == {"skills": ["x"]}                           # flat acl lookup
              and resolve_scope({"p": "oops"}, "p") is None                                                            # non-dict spec -> None, never raise
              and acl_sha("a", "h", {"skills": ["x"]}) != acl_sha("b", "h", {"skills": ["x"]}))   # pid folded into the digest

    ok = (no_token and wrong and query_token_rejected and authed and burst_allowed == 3 and throttled
          and refills and token_value_never_stored and every_record_carries_principal and acl_ok)
    return {"no_token_rejected_401": no_token, "wrong_token_rejected": wrong,
            "query_token_rejected": query_token_rejected, "authed_to_principal": authed,
            "burst_then_throttle_429": burst_allowed == 3 and throttled, "bucket_refills": refills,
            "token_value_never_stored": token_value_never_stored,
            "every_record_carries_principal": every_record_carries_principal, "acl_ok": acl_ok, "ok": ok}


if __name__ == "__main__":
    import sys
    r = principals_selftest()
    print(json.dumps(r, indent=2))
    sys.exit(0 if r["ok"] else 1)
