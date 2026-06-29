"""Regression tests for the blockers the adversarial review surfaced on the namespace cutover.

Each test pins a defect the green suite had MISSED, so it cannot silently come back:
  FIX A — cartridge.compile() must not route a bare id through the fail-closed RESOLVER (skill_dir), which
          collapsed every bare skill onto the `.__ambiguous_or_absent__` sentinel (data loss + fail-open).
  FIX B — govern() exposes the CANONICAL id it resolved, so the record (and every downstream re-check) keys
          off the same string the claim was authorized against.
  FIX C — a canonical `general:fs` claim still honours a LEGACY bare ACL entry (`fs`) — pre-cutover per-actor
          ACLs keep working instead of failing closed.
  FIX D — fleetd `/fleet/find` matches a bare query against a namespaced roster by leaf.
"""
from __future__ import annotations
import json
import os
import tempfile

from infra import registry
from infra.govern import fleetd
from infra.govern import principals as P
from infra.tool import cartridge, skill_index

SENTINELS = {".__ambiguous_or_absent__", ".__invalid_skill_id__"}


def _tree(root):
    out = set()
    for dp, dns, _ in os.walk(root):
        for d in dns:
            out.add(d)
    return out


# ───────────────────────── FIX A — cartridge write-path ─────────────────────────
def test_bare_single_skill_compiles_flat_not_into_the_sentinel():
    cart = os.path.join(tempfile.mkdtemp(), "c")
    cartridge.compile(["alchemy"], cart, source=skill_index.SKILLS)        # BARE id
    assert os.path.isfile(os.path.join(cart, "alchemy", "perks.json"))      # flat <out>/<name>
    assert not (SENTINELS & _tree(cart))                                    # sentinel NOT materialized
    assert cartridge.verify(cart)["ok"]


def test_bare_roster_does_not_collapse_or_lose_skills():
    cart = os.path.join(tempfile.mkdtemp(), "c")
    cartridge.compile(["alchemy", "ci-codeqc"], cart, source=skill_index.SKILLS)
    assert os.path.isfile(os.path.join(cart, "alchemy", "perks.json"))      # BOTH present — no overwrite
    assert os.path.isfile(os.path.join(cart, "ci-codeqc", "perks.json"))
    shas = {e["skill"]: e["skill_sha"] for e in json.load(open(os.path.join(cart, "index.json")))["skills"]}
    assert shas["alchemy"] != shas["ci-codeqc"]                            # distinct bodies, not one masquerading
    assert cartridge.verify(cart)["ok"]


def test_namespaced_roster_nests_and_verifies():
    cart = os.path.join(tempfile.mkdtemp(), "c")
    cartridge.compile(["general:alchemy", "cws:cws-pm"], cart, source=skill_index.SKILLS)
    assert os.path.isfile(os.path.join(cart, "general", "alchemy", "perks.json"))
    assert os.path.isfile(os.path.join(cart, "cws", "cws-pm", "perks.json"))
    assert not (SENTINELS & _tree(cart))
    assert cartridge.verify(cart)["ok"]


def test_unknown_id_in_a_compiled_cartridge_still_fails_closed():
    cart = os.path.join(tempfile.mkdtemp(), "c")
    cartridge.compile(["alchemy"], cart, source=skill_index.SKILLS)
    d = registry.skill_dir("does-not-exist", cart)                          # resolver still routes unknown ->
    assert os.path.basename(d) == ".__ambiguous_or_absent__"               #   the sentinel, which is NOT a skill
    assert not os.path.isfile(os.path.join(d, "perks.json"))


def test_compiled_skill_dst_rejects_a_traversing_id():
    import pytest
    for bad in ["../escape", "a/b", "..", "x:../y"]:
        with pytest.raises(ValueError):
            registry.compiled_skill_dst(bad, "/tmp/out")


def test_flat_leaf_with_a_grouped_owner_fails_closed(tmp_path):
    """FIX #17 (review, minor): a chip carrying BOTH a flat `<chip>/dup` AND a grouped `<chip>/general/dup` for
    the same leaf must not let the flat entry silently shadow the cross-namespace ambiguity — it fails CLOSED
    (AMBIGUOUS / sentinel), never first-layout-wins."""
    chip = str(tmp_path)
    for d in (os.path.join(chip, "dup"), os.path.join(chip, "general", "dup")):
        os.makedirs(d, exist_ok=True)
        open(os.path.join(d, "perks.json"), "w").write('{"skill":"dup","perks":[]}')
    assert registry.canonicalize("dup", chip) == registry.AMBIGUOUS
    assert os.path.basename(registry.skill_dir("dup", chip)) == ".__ambiguous_or_absent__"


# ───────────────────────── FIX B — govern() exposes the canonical id ─────────────────────────
def test_govern_returns_the_canonical_skill():
    from infra.govern import govd
    cfg = govd.load_config()
    v = govd.govern({"skill": "fs", "perk": "archive", "var_keys": ["SOURCE_DIR"]}, cfg)
    assert v.get("skill") == "general:fs"          # bare claim -> the record/grant/step-time all key off THIS


# ───────────────────────── FIX C — legacy bare ACLs admit the canonical claim ─────────────────────────
def _allows(acl, skill, perk, destructive=False, credentialed=False):
    return P.acl_allows(acl, skill, perk, "community", destructive, credentialed)[0]


def test_legacy_bare_skills_list_admits_canonical_claim():
    acl = {"skills": ["fs", "py_qc"]}                                       # pre-cutover ACL (bare)
    assert _allows(acl, "general:fs", "archive")                           # canonical claim still allowed
    assert _allows(acl, "general:py_qc", "lint")
    assert not _allows(acl, "general:sec", "secrets")                      # an unlisted leaf is still denied


def test_namespaced_acl_stays_precise():
    acl = {"skills": ["general:fs"]}
    assert _allows(acl, "general:fs", "archive")
    assert not _allows(acl, "magnumopus:fs", "archive")                    # a DIFFERENT namespace is NOT admitted
    assert P.acl_allows({"skills": ["general:*"]}, "general:anything", "x", "community", False, False)[0]


def test_legacy_bare_perksmap_governs_canonical_claim():
    acl = {"perks": {"fs": ["archive"]}}                                    # pre-cutover perks-map (bare)
    assert _allows(acl, "general:fs", "archive")                           # listed perk allowed via leaf
    assert not _allows(acl, "general:fs", "find_large")                    # perks-map authoritative -> deny other
    assert _allows(acl, "general:fs", "archive", destructive=True)         # explicit perk listing ADMITS destructive


def test_destructive_denied_under_a_bare_skills_grant():
    acl = {"skills": ["fs"]}                                                # legacy bare SKILLS-list, no perks-map
    assert _allows(acl, "general:fs", "find_large")                        # non-destructive allowed via leaf
    assert not _allows(acl, "general:fs", "find_large", destructive=True)  # a bare-skill grant never admits destructive


# ───────────────────────── FIX D — fleetd discovery matches across the cutover ─────────────────────────
def test_fleet_find_skill_match_is_leaf_tolerant():
    assert fleetd._skill_matches("fs", "general:fs")                       # bare query -> namespaced roster
    assert fleetd._skill_matches("fs", "fs")                               # bare -> flat node
    assert fleetd._skill_matches("fs", "magnumopus:fs")                    # bare -> any namespace's leaf
    assert fleetd._skill_matches("general:fs", "general:fs")               # exact
    assert fleetd._skill_matches("general:fs", "fs")                       # ns query -> legacy flat advertisement
    assert not fleetd._skill_matches("general:fs", "magnumopus:fs")        # ns query stays precise
    assert not fleetd._skill_matches("fs", "fsx")                          # no spurious leaf match
