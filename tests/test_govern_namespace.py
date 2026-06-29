"""Step 3 — the govern namespace shim + the ns:* ACL wildcard.

The bare->ns:name canonicalize shim at the claim boundary (existing bare claims keep working; an ambiguous
bare name is REJECTED, never silently routed) and the per-namespace `ns:*` ACL wildcard."""
from __future__ import annotations
import os

from infra import registry
from infra.govern import govd
from infra.govern import principals as P
from infra.tool import skill_index as SI


def _mkskill(chip, ns, name):
    d = os.path.join(chip, ns, name)
    os.makedirs(d, exist_ok=True)
    open(os.path.join(d, "perks.json"), "w").write('{"skill":"%s","perks":[]}' % name)
    open(os.path.join(d, "x.sh"), "w").write("x")


# ── the ns:* ACL wildcard (principals) ──
def test_skill_listed_wildcard():
    assert P._skill_listed("magnumopus:search", ["magnumopus:*"]) is True       # namespace wildcard
    assert P._skill_listed("general:search", ["magnumopus:*"]) is False         # a DIFFERENT namespace
    assert P._skill_listed("magnumopus:search", ["magnumopus:search"]) is True  # exact id
    assert P._skill_listed("magnumopus:search", []) is False
    assert P._skill_listed("magnumopus:search", None) is False                  # fail-closed on a non-list


def test_acl_allows_ns_wildcard():
    acl = {"skills": ["magnumopus:*", "general:search"]}
    assert P.acl_allows(acl, "magnumopus:anything", "x", None, False, False)[0]      # ns:* admits the namespace
    ok, prob = P.acl_allows(acl, "general:fs", "x", None, False, False)
    assert not ok and prob["id"] == "acl_skill_denied"                              # not listed, no general:* wildcard
    assert P.acl_allows(acl, "general:search", "x", None, False, False)[0]          # exact id still works
    assert P.acl_allows({"skills": ["*"]}, "anything:goes", "x", None, False, False)[0]  # super-wildcard unaffected


# ── the canonicalize shim in govern() ──
def test_govern_rejects_ambiguous_bare(tmp_path, monkeypatch):
    chip = str(tmp_path)
    _mkskill(chip, "general", "search")
    _mkskill(chip, "magnumopus", "search")                       # bare 'search' now owned by TWO namespaces
    monkeypatch.setattr(registry, "SKILLCHIP", chip)
    v = govd.govern({"skill": "search", "perk": "grep"}, {})
    assert v["decision"] == "reject" and v["problems"][0]["id"] == "ambiguous_skill_id"


def test_govern_namespaced_passes_the_shim(tmp_path, monkeypatch):
    chip = str(tmp_path)
    _mkskill(chip, "general", "search")
    _mkskill(chip, "magnumopus", "search")
    monkeypatch.setattr(registry, "SKILLCHIP", chip)
    v = govd.govern({"skill": "magnumopus:search", "perk": "grep"}, {})       # explicit namespace disambiguates
    assert v["decision"] == "reject"                                          # the stub skill has no real perk...
    assert all(p.get("id") != "ambiguous_skill_id" for p in v.get("problems", []))  # ...but it got PAST the shim
