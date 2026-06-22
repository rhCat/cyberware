#!/usr/bin/env python3
"""infra/govern/orgs.py — multi-tenant orgs over principals (P5-T03, P5).

Extends P1-T08's principal auth to ORGS: each principal belongs to an org and carries a SPIFFE identity
(`spiffe://<trust-domain>/<org>/<principal>`); each org has its own record root + quotas + a revocation
scope. The invariant is **org isolation** — a principal authenticated to org A can read/claim only within
org A; every cross-org cell of the endpoint matrix is refused. Revoked principals authenticate to nobody.
Builds on `principals.token_sha` / the same sha-only-never-the-value discipline.
"""
from __future__ import annotations
import hmac
import os

from infra.govern import principals

TRUST_DOMAIN = "cyberware"


def spiffe_id(org: str, pid: str) -> str:
    return f"spiffe://{TRUST_DOMAIN}/{org}/{pid}"


def authorize(bearer: str, registry: dict):
    """Resolve a Bearer token to {org, principal, spiffe} across all orgs, honoring revocation; None if no
    match or revoked. registry: {org: {principals: {pid: {token_sha, rate, burst, revoked?}}}}."""
    if not bearer:
        return None
    want = principals.token_sha(bearer)
    for org, ospec in registry.items():
        for pid, spec in ospec.get("principals", {}).items():
            if spec.get("revoked"):
                continue
            if hmac.compare_digest(str(spec.get("token_sha", "")), want):
                return {"org": org, "principal": pid, "spiffe": spiffe_id(org, pid)}
    return None


def record_root_for(base: str, org: str) -> str:
    """Per-org record root — one org's runs never share a directory with another's."""
    return os.path.join(base, "org", org)


def can_access(requester_org: str, target_org: str) -> bool:
    """Org isolation: a principal may read/claim only within its own org."""
    return requester_org == target_org


def orgs_selftest() -> dict:
    """P5-T03: tokens resolve to their org + a well-formed SPIFFE id; a revoked principal authenticates to
    none; per-org record roots are distinct; and EVERY cross-org cell of the access matrix is refused while
    same-org is allowed (org_isolation across the endpoint matrix). `ok` iff all hold."""
    reg = {
        "org-a": {"principals": {"a1": {"token_sha": principals.token_sha("tok-A")}}},
        "org-b": {"principals": {"b1": {"token_sha": principals.token_sha("tok-B")},
                                 "b2": {"token_sha": principals.token_sha("tok-B2"), "revoked": True}}},
    }
    a, b = authorize("tok-A", reg), authorize("tok-B", reg)
    resolves_per_org = bool(a) and a["org"] == "org-a" and bool(b) and b["org"] == "org-b"
    spiffe_identity = a["spiffe"] == "spiffe://cyberware/org-a/a1"
    revocation = authorize("tok-B2", reg) is None                       # revoked -> no principal
    base = "/srv/govd"
    per_org_record_roots = record_root_for(base, "org-a") != record_root_for(base, "org-b")

    orgs = ["org-a", "org-b"]
    matrix = {(r, t): can_access(r, t) for r in orgs for t in orgs}
    endpoint_matrix_isolated = all(allowed == (r == t) for (r, t), allowed in matrix.items())
    cross_org_refused = matrix[("org-a", "org-b")] is False and matrix[("org-b", "org-a")] is False

    ok = (resolves_per_org and spiffe_identity and revocation and per_org_record_roots
          and endpoint_matrix_isolated and cross_org_refused)
    return {"resolves_per_org": resolves_per_org, "spiffe_identity": spiffe_identity,
            "revocation": revocation, "per_org_record_roots": per_org_record_roots,
            "endpoint_matrix_isolated": endpoint_matrix_isolated, "cross_org_refused": cross_org_refused,
            "ok": ok}


if __name__ == "__main__":
    import json
    import sys
    r = orgs_selftest()
    print(json.dumps(r, indent=2))
    sys.exit(0 if r["ok"] else 1)
