"""Step 2 — namespaced chip manifest (infra/tool/skill_index.py).

scan_skills emits `ns:skill`; chip_manifest keys the roll-up on `ns:skill` + bumps the manifest to v2; the
per-skill index keeps the BARE leaf so skill_sha is placement-invariant. A name shared across two namespaces
yields TWO distinct manifest entries (the collision fix), neither dropped."""
from __future__ import annotations
import json
import os

from infra.tool import skill_index as SI


def _mkskill(chip, ns, name, body="x"):
    d = os.path.join(chip, ns, name)
    os.makedirs(d, exist_ok=True)
    open(os.path.join(d, "perks.json"), "w").write('{"skill":"%s","perks":[]}' % name)
    open(os.path.join(d, "tool.sh"), "w").write(body)            # a content file -> a real skill_sha
    SI.write_index(f"{ns}:{name}", chip)                          # per-skill index, addressed namespaced
    return d


def test_scan_emits_namespaced(tmp_path):
    chip = str(tmp_path)
    _mkskill(chip, "general", "alchemy")
    _mkskill(chip, "cws", "cws-fs")
    assert set(SI.scan_skills(chip)) == {"general:alchemy", "cws:cws-fs"}


def test_per_skill_index_stays_bare(tmp_path):
    chip = str(tmp_path)
    _mkskill(chip, "magnumopus", "search")
    idx = json.load(open(os.path.join(chip, "magnumopus", "search", "index.json")))
    assert idx["skill"] == "search"                              # BARE leaf, NOT "magnumopus:search"


def test_manifest_keys_on_namespace_and_v2(tmp_path):
    chip = str(tmp_path)
    _mkskill(chip, "general", "search", body="general-impl")
    _mkskill(chip, "magnumopus", "search", body="mo-impl")       # SAME leaf, two namespaces
    SI.write_manifest(chip)
    m = json.load(open(os.path.join(chip, "index.json")))
    assert m["version"] == 2
    ids = {e["skill"] for e in m["skills"]}
    assert ids == {"general:search", "magnumopus:search"}        # BOTH present, distinct (collision fix)
    nss = {e["skill"]: e["namespace"] for e in m["skills"]}
    assert nss["general:search"] == "general" and nss["magnumopus:search"] == "magnumopus"
    shas = {e["skill"]: e["skill_sha"] for e in m["skills"]}
    assert shas["general:search"] != shas["magnumopus:search"]   # distinct content -> two distinct members


def test_skill_sha_placement_invariant(tmp_path):
    a = str(tmp_path / "a"); b = str(tmp_path / "b")
    os.makedirs(a); os.makedirs(b)
    _mkskill(a, "general", "x", body="same-bytes")
    _mkskill(b, "magnumopus", "x", body="same-bytes")            # same content, different namespace
    ia = json.load(open(os.path.join(a, "general", "x", "index.json")))
    ib = json.load(open(os.path.join(b, "magnumopus", "x", "index.json")))
    assert ia["skill_sha"] == ib["skill_sha"]                    # placement-invariant -> compose copies verbatim


def test_load_set_and_catalog_namespaced(tmp_path):
    chip = str(tmp_path)
    _mkskill(chip, "general", "alchemy")
    _mkskill(chip, "magnumopus", "search")
    SI.write_manifest(chip)
    assert set(SI.all_skills(chip)) == {"general:alchemy", "magnumopus:search"}   # load set namespaced
    cat = SI.catalog(chip)
    assert {s["skill"] for s in cat["skills"]} == {"general:alchemy", "magnumopus:search"}
    assert all(s["verified"] for s in cat["skills"])             # per-skill verify passes for namespaced ids
