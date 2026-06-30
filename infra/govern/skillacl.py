#!/usr/bin/env python3
"""skillacl.py — the ACCESS-1 gate: a skill's OWN, intrinsic access policy, independent of WHO claims it.

Three INDEPENDENT govern gates stay delineated (each a fail-closed AND):
  VALIDATE  — the skill's files match its committed index (authenticity).
  ACCESS-1  — THIS gate: may this skill be reached AT ALL, here? (the skill's `access.json`)
  ACCESS-2  — the per-actor token ACL (`principals.acl_allows`): may THIS actor reach it?

Policy. A skill that DECLARES `access.json` is always governed by it — when govd serves OTHERS the skill must
opt in with `"remote": true`, and may further narrow to a `principals` allow-list and a `min_tier` floor. A
skill with NO `access.json` is the back-compat case: it stays remote-OPEN until the operator flips the
`skillacl_enforce` rollout flag, at which point the secure default — LOCAL-OPEN / REMOTE-CLOSED — takes hold
(so the fleet keeps working while skills adopt policies, then one flag reaches the end state). A govd in
`--mode local` (the developer's own), or a principal flagged `local_dev`, is always open (the dev override).
Every branch fails CLOSED.

  access.json:
    { "remote": true,                 # may remote callers reach this skill at all? (absent == false)
      "principals": ["pm", "ci"],     # optional: only these actor ids (when remote)
      "min_tier": "verified" }        # optional: caller must be at least this tier (core>verified>community)
"""
from __future__ import annotations
import json
import os

from infra import registry
from infra.cwp import canonical

_CLOSED = {"remote": False}                              # a malformed/unreadable access.json -> closed to others
_TIER = {"core": 2, "verified": 1, "community": 0}


def load_access(skill, chip=None):
    """The skill's intrinsic access policy (`<skill_dir>/access.json`), or None when ABSENT (the back-compat,
    flag-governed default). Never raises; a malformed/unreadable file resolves to the CLOSED sentinel — a
    declared-but-broken policy fails safe, never silently opens."""
    p = os.path.join(registry.skill_dir(skill, chip), "access.json")
    if not os.path.isfile(p):
        return None
    try:
        a = json.load(open(p))
    except (ValueError, OSError):
        return _CLOSED
    return a if isinstance(a, dict) else _CLOSED


def _tier_at_least(have, need) -> bool:
    """Caller tier `have` meets the floor `need` (core>verified>community). Fail-safe: an unknown/None caller
    tier is the LEAST trusted (community); an unknown floor is the TIGHTEST (core) — never unearned trust."""
    return _TIER.get(have, _TIER["community"]) >= _TIER.get(need, _TIER["core"])


def access_allows(access, *, mode, is_local_dev=False, principal=None, principal_tier=None, perk=None,
                  enforce_default_closed=False):
    """(ok, problem|None) for the ACCESS-1 gate. Local govd `mode` OR a `local_dev` principal -> allow (the dev
    override). Otherwise, when govd serves OTHERS: a skill with NO policy is open unless `enforce_default_closed`
    (the `skillacl_enforce` rollout flag); a skill WITH a policy must opt in via `remote: true` and satisfy any
    `principals` allow-list + `min_tier` floor. Fail-closed throughout (a malformed policy is the CLOSED sentinel)."""
    if mode == "local" or is_local_dev:
        return True, None                                   # local-open, or the per-principal dev override
    if access is None:                                      # no policy declared -> back-compat / flag-governed
        if not enforce_default_closed:
            return True, None                               # remote-OPEN until the operator opts in
        return False, {"id": "skill_remote_closed", "detail": "no access.json (default-closed enforcement on)"}
    if not isinstance(access, dict) or access.get("remote") is not True:
        return False, {"id": "skill_remote_closed", "detail": "skill not exposed to remote callers"}
    allow = access.get("principals")
    if allow is not None and (not isinstance(allow, list) or principal not in allow):
        return False, {"id": "skill_principal_denied", "detail": principal}
    floor = access.get("min_tier")
    if floor is not None and not _tier_at_least(principal_tier, floor):
        return False, {"id": "skill_tier_below_floor", "detail": {"have": principal_tier, "need": floor}}
    return True, None


def access_policy_sha(access) -> str:
    """A stable sha of the EFFECTIVE access policy. Behind the `skillacl_fold` rollout flag it is RECORDED on
    the run as `skillacl_sha` — a field SEPARATE from the grant-bound acl_sha (folding it INTO acl_sha breaks
    exod's acl_join) — so the run's provenance carries the ACCESS-1 decision, ready for exod's off-node re-check
    in Step 7. A skill with no policy hashes as the CLOSED sentinel, so adopting a policy changes it."""
    return canonical.digest(access if isinstance(access, dict) else _CLOSED)


def skillacl_selftest() -> dict:
    """Prove the gate's truth table — local/dev open, remote default governed by the flag, declared policy
    enforced, narrowing + tier floor, malformed fails closed."""
    A = access_allows
    r = {
        "local_open":           A(None, mode="local")[0] is True,
        "dev_override":         A(None, mode="remote", is_local_dev=True)[0] is True,
        "remote_open_unflagged": A(None, mode="remote")[0] is True,
        "remote_closed_flagged": A(None, mode="remote", enforce_default_closed=True)[0] is False,
        "declared_optin":       A({"remote": True}, mode="remote")[0] is True,
        "declared_not_remote":  A({"remote": False}, mode="remote")[0] is False,
        "principal_allowlist":  (A({"remote": True, "principals": ["pm"]}, mode="remote", principal="x")[0] is False
                                 and A({"remote": True, "principals": ["pm"]}, mode="remote", principal="pm")[0] is True),
        "tier_floor":           A({"remote": True, "min_tier": "core"}, mode="remote", principal_tier="community")[0] is False,
        "malformed_closed":     A("not-a-dict", mode="remote")[0] is False,
    }
    r["ok"] = all(r.values())
    return r


if __name__ == "__main__":
    import json as _j
    print(_j.dumps(skillacl_selftest(), indent=2))
