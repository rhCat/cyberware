"""ACL-gated shared-cargo bind — the `cargo` axis (v1.5).

A delegated run may request the shared /cyberware_cargo dir be bound into its confined step ("ro"|"rw"),
gated by the actor's `cargo` ACL axis. Like `params`/`secrets`: folds into acl_sha, threaded through the
attestation, RE-ENFORCED off-node by exod before the bind is added; the grant may only NARROW, never widen.
"""
import dataclasses
import os

from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

from infra.govern import principals as P
from infra.exec.sandbox import SandboxProfile


# ── the axis: acl_allows(cargo=...) ─────────────────────────────────────────────────────────────
def test_cargo_axis_denies_and_allows():
    base = {"skills": ["*"]}
    # a cargo request WITHOUT the grant is refused (fail-closed, like the secrets/params axes)
    ok, prob = P.acl_allows(base, "general:fs", "find", "core", False, False, cargo="ro")
    assert not ok and prob["id"] == "acl_cargo_denied"
    # WITH cargo:ro granted, an ro request is allowed
    ok, _ = P.acl_allows({**base, "cargo": "ro"}, "general:fs", "find", "core", False, False, cargo="ro")
    assert ok
    # a non-cargo claim is unaffected whether or not cargo is granted
    assert P.acl_allows(base, "general:fs", "find", "core", False, False, cargo=None)[0]
    assert P.acl_allows({**base, "cargo": "rw"}, "general:fs", "find", "core", False, False)[0]


def test_cargo_grant_never_widens_ro_to_rw():
    base = {"skills": ["*"], "cargo": "ro"}
    # rw requested against an ro-only grant -> refused (the grant narrows, never widens)
    ok, prob = P.acl_allows(base, "general:fs", "find", "core", False, False, cargo="rw")
    assert not ok and prob["id"] == "acl_cargo_rw_denied"
    # rw granted admits BOTH ro and rw requests
    rw = {"skills": ["*"], "cargo": "rw"}
    assert P.acl_allows(rw, "general:fs", "find", "core", False, False, cargo="rw")[0]
    assert P.acl_allows(rw, "general:fs", "find", "core", False, False, cargo="ro")[0]


def test_cargo_malformed_request_fails_closed():
    ok, prob = P.acl_allows({"skills": ["*"], "cargo": "rw"}, "general:fs", "find", "core", False, False, cargo="RWX")
    assert not ok and prob["id"] == "acl_cargo_malformed"


def test_cargo_rides_the_acl_digest():
    # the capability folds into acl_sha, so a grant/attestation binds it off-node (no cross-boundary replay)
    a = P.acl_sha("pid", "toksha", {"skills": ["*"]})
    b = P.acl_sha("pid", "toksha", {"skills": ["*"], "cargo": "ro"})
    c = P.acl_sha("pid", "toksha", {"skills": ["*"], "cargo": "rw"})
    assert a != b and b != c and a != c            # None, ro, rw are all distinct digests


# ── the attestation triangle (the H01 lesson: cargo must thread through issue + attested_acl) ────
def test_attestation_join_holds_for_cargo_actor():
    from infra.govern import issue
    from infra.exec.aclverify import verify_acl_attestation, attested_acl, attestation_body
    op = Ed25519PrivateKey.generate()
    acl = {"skills": ["*"], "cargo": "rw"}
    grant_sha = P.acl_sha("pid", "toksha", acl)                 # what govd binds into the grant (cargo-inclusive)
    att = issue.mint_attestation(op, pid="pid", token_sha="toksha", acl=acl, nbf=0, exp=10**12, attestation_id="c1")
    ok, why = verify_acl_attestation(op.public_key(), att, now=1, expect_acl_sha=grant_sha)
    assert ok, f"join must hold for a cargo actor, got: {why}"
    assert attested_acl(attestation_body(att)).get("cargo") == "rw"


def test_attested_acl_carries_cargo():
    from infra.exec.aclverify import attested_acl
    assert attested_acl({"skills": ["*"], "cargo": "ro"}).get("cargo") == "ro"
    assert attested_acl({"skills": ["*"]}).get("cargo") is None    # absent -> None (matches a cargo-less grant)


# ── the sandbox bind: SandboxProfile realizes the mode (bwrap + OCI) ─────────────────────────────
def test_bwrap_binds_cargo_ro_and_rw_only_when_set_and_present(tmp_path):
    cargo = str(tmp_path / "cargo"); os.makedirs(cargo)
    def flat(mode, path=cargo):
        return " ".join(SandboxProfile(workspace=str(tmp_path / "ws"), cargo=mode, cargo_path=path).bwrap_argv(["true"]))
    # rw -> a rw --bind of the cargo path; ro -> a --ro-bind; None -> no cargo bind at all
    rw = flat("rw")
    assert f"--bind {cargo} {cargo}" in rw
    ro = flat("ro")
    assert f"--ro-bind {cargo} {cargo}" in ro and f"--bind {cargo} {cargo}" not in ro
    assert cargo not in flat(None)                                       # no mode -> never bound
    # a granted mode whose dir is NOT mounted binds nothing (fail-safe, no silent widening)
    assert "/nope-not-here" not in flat("rw", path="/nope-not-here")


def test_oci_config_mirrors_the_cargo_bind(tmp_path):
    from infra.exec.sandbox import oci_config
    cargo = str(tmp_path / "cargo"); os.makedirs(cargo)
    spec = oci_config(SandboxProfile(workspace=str(tmp_path / "ws"), cargo="ro", cargo_path=cargo), ["true"])
    m = [x for x in spec["mounts"] if x["destination"] == cargo]
    assert len(m) == 1 and "ro" in m[0]["options"] and m[0]["source"] == cargo
    none = oci_config(SandboxProfile(workspace=str(tmp_path / "ws"), cargo_path=cargo), ["true"])
    assert not [x for x in none["mounts"] if x["destination"] == cargo]  # None -> not mounted


# ── exod's OFF-NODE re-enforcement, driven through the REAL _acl_check ───────────────────────────
from infra.cwp import sign as _sign
from infra.exec.exod import Exod as _Exod
from infra.govern import issue as _issue

_GRANT = _sign.keygen_from_seed(b"cargo-grant".ljust(32, b"0"))
_EXODK = _sign.keygen_from_seed(b"cargo-exod".ljust(32, b"0"))
_OP = _sign.keygen_from_seed(b"cargo-acl-issuer".ljust(32, b"0"))


def _exod():
    return _Exod(_EXODK, grant_issuer_pub=_GRANT.public_key(), acl_issuer_pub=_OP.public_key(),
                 runner=lambda *a, **k: None)


def _req(acl):
    att = _issue.mint_attestation(_OP, pid="agent-1", token_sha="tok", acl=acl, nbf=1000, exp=5000, attestation_id="ca")
    return {"attestation": att, "env": {"PATH": "/usr/bin", "SNIP": "/s", "RECORD_STORE": "/r"}}


def _gbody(acl, cargo):
    return {"acl_sha": P.acl_sha("agent-1", "tok", acl), "skill": "general:fs", "perk": "find",
            "sandbox_tier": None, "destructive": False, "credentials": [], "cargo": cargo}


def test_exod_refuses_a_cargo_grant_the_acl_does_not_grant():
    """A grant asserting cargo="rw" for an actor whose attested ACL grants NO cargo -> exod denies off-node
    (a compromised govd cannot bind /cyberware_cargo past the operator-attested ceiling)."""
    acl = {"skills": ["*"], "max_tier": "community", "secrets": False}      # no cargo grant
    assert _exod()._acl_check(_req(acl), _gbody(acl, "rw"), now=1500) == "acl_cargo_denied"


def test_exod_refuses_rw_grant_against_ro_only_acl():
    acl = {"skills": ["*"], "max_tier": "community", "secrets": False, "cargo": "ro"}
    assert _exod()._acl_check(_req(acl), _gbody(acl, "rw"), now=1500) == "acl_cargo_rw_denied"


def test_exod_passes_a_cargo_grant_within_the_acl():
    acl = {"skills": ["*"], "max_tier": "community", "secrets": False, "cargo": "rw"}
    assert _exod()._acl_check(_req(acl), _gbody(acl, "rw"), now=1500) is None       # rw within rw grant
    assert _exod()._acl_check(_req(acl), _gbody(acl, "ro"), now=1500) is None       # ro within rw grant
    assert _exod()._acl_check(_req(acl), _gbody(acl, None), now=1500) is None       # no cargo requested


# ── the grant carries the mode (emitted only when set: legacy bodies unchanged) ──────────────────
def test_grant_emits_cargo_only_when_set():
    from infra.exec.grants import mint_grant
    from infra.exec.grantverify import grant_body
    gk = Ed25519PrivateKey.generate()
    base = dict(run_id="r", plan_sha="p", nbf=0, exp=9, nonce="n")
    assert "cargo" not in grant_body(mint_grant(gk, **base))                        # no cargo -> absent
    assert grant_body(mint_grant(gk, cargo="rw", **base))["cargo"] == "rw"          # set -> present


# ── govd.govern integration: the cargo mode rides the verdict ONLY on an allow (govd.py:330) ─────
def test_govern_does_not_propagate_cargo_past_a_reject():
    """A rejected cargo claim (here: cargo denied by the scope) carries cargo=None — pins the
    `decision == "allow"` guard in govd.govern so it can't flip to propagate a mode past a reject."""
    import json, os
    from infra.govern import govd
    from infra.tool import skill_index
    from infra import registry
    skill = sorted(skill_index.all_skills())[0]
    perk = json.load(open(os.path.join(registry.skill_dir(skill), "perks.json")))["perks"][0]["id"]
    ledger = {"skill": skill, "perk": perk, "var_keys": [], "cargo": "rw"}
    v = govd.govern(ledger, {}, scope={"skills": ["*"]})     # grants the skill but NOT cargo -> acl_cargo_denied
    assert v["decision"] == "reject"
    assert any(p["id"] == "acl_cargo_denied" for p in v.get("problems", []))
    assert v.get("cargo") is None                            # NOT propagated on a non-allow (kills the == -> != mutant)
