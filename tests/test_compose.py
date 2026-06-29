"""Step 4 — multi-source compose + reconcile (infra/tool/compose.py).

Merge N source chips into one composed chip, each skill placed by NAMESPACE. An exact `ns:name` duplicate
across sources is a HARD ERROR (manual reconciliation, never first-source-wins); a shared LEAF across
DIFFERENT namespaces coexists. The composed chip re-pins its own authentic v2 manifest, and re-composing is
idempotent.
"""
from __future__ import annotations
import os

import pytest

from infra import registry
from infra.tool import compose, skill_index


def _mk_source(root, ns, name, body="impl"):
    """A minimal authentic source chip: one namespaced skill, pinned + manifested."""
    d = os.path.join(root, ns, name)
    os.makedirs(d, exist_ok=True)
    open(os.path.join(d, "perks.json"), "w").write('{"skill":"%s","perks":[]}' % name)
    open(os.path.join(d, "tool.sh"), "w").write(body)
    skill_index.write_index(f"{ns}:{name}", root)
    skill_index.write_manifest(root)
    return root


def test_compose_two_sources_merges(tmp_path):
    a = _mk_source(str(tmp_path / "a"), "general", "alpha")
    b = _mk_source(str(tmp_path / "b"), "magnumopus", "beta")
    out = str(tmp_path / "composed")
    r = compose.compose([a, b], out)
    assert set(r["skills"]) == {"general:alpha", "magnumopus:beta"} and r["count"] == 2
    assert os.path.isfile(os.path.join(out, "general", "alpha", "perks.json"))
    assert os.path.isfile(os.path.join(out, "magnumopus", "beta", "perks.json"))
    assert skill_index.verify_chip(out)[0]                              # composed chip is authentic
    assert set(skill_index.all_skills(out)) == {"general:alpha", "magnumopus:beta"}


def test_exact_dup_is_a_hard_error_and_writes_nothing(tmp_path):
    a = _mk_source(str(tmp_path / "a"), "general", "dup", body="A")
    b = _mk_source(str(tmp_path / "b"), "general", "dup", body="B")          # SAME ns:name, different bytes
    out = str(tmp_path / "composed")
    with pytest.raises(compose.ComposeConflict) as ei:
        compose.compose([a, b], out)
    assert "general:dup" in ei.value.conflicts                              # the duplicate is named
    assert not os.path.exists(out)                                          # fail-closed: out_dir untouched


def test_same_leaf_across_namespaces_coexists(tmp_path):
    a = _mk_source(str(tmp_path / "a"), "general", "search")
    b = _mk_source(str(tmp_path / "b"), "magnumopus", "search")             # SAME leaf, DIFFERENT namespace
    out = str(tmp_path / "composed")
    r = compose.compose([a, b], out)
    assert set(r["skills"]) == {"general:search", "magnumopus:search"}      # both kept, distinct
    assert skill_index.verify_chip(out)[0]


def test_namespace_override_rehomes_a_source(tmp_path):
    a = _mk_source(str(tmp_path / "a"), "general", "widget")
    out = str(tmp_path / "composed")
    r = compose.compose([{"path": a, "namespace": "magnumopus"}], out)      # re-home general:widget -> magnumopus:
    assert r["skills"] == ["magnumopus:widget"]
    assert os.path.isfile(os.path.join(out, "magnumopus", "widget", "perks.json"))


def test_compose_is_idempotent(tmp_path):
    a = _mk_source(str(tmp_path / "a"), "general", "alpha")
    b = _mk_source(str(tmp_path / "b"), "magnumopus", "beta")
    out = str(tmp_path / "composed")
    first = compose.compose([a, b], out)["chip_sha"]
    second = compose.compose([a, b], out)["chip_sha"]                       # re-register
    assert first == second                                                 # byte-identical chip


def test_flat_source_without_namespace_is_rejected(tmp_path):
    # a FLAT source (skill at the chip root, no source-group) is ambiguous to compose without a namespace
    flat = str(tmp_path / "flat")
    d = os.path.join(flat, "loose")
    os.makedirs(d)
    open(os.path.join(d, "perks.json"), "w").write('{"skill":"loose","perks":[]}')
    open(os.path.join(d, "x.sh"), "w").write("x")
    skill_index.write_index("loose", flat)                                  # authentic flat chip (pinned)
    skill_index.write_manifest(flat)
    with pytest.raises(ValueError, match="explicit namespace"):
        compose.compose([flat], str(tmp_path / "composed"))
    # …but WITH a namespace it composes
    r = compose.compose([{"path": flat, "namespace": "vendor"}], str(tmp_path / "c2"))
    assert r["skills"] == ["vendor:loose"]


def test_unauthentic_source_is_refused(tmp_path):
    a = _mk_source(str(tmp_path / "a"), "general", "alpha")
    with open(os.path.join(a, "general", "alpha", "tool.sh"), "a") as f:
        f.write("\n# tamper\n")                                            # files no longer match the pinned manifest
    with pytest.raises(ValueError, match="unauthentic source"):
        compose.compose([a], str(tmp_path / "composed"))


def test_compose_real_skillchip_roundtrips(tmp_path):
    """Integration: composing the live skillChip (preserving its source-groups) reproduces its load set."""
    out = str(tmp_path / "composed")
    r = compose.compose([registry.SKILLCHIP], out)
    assert r["count"] == len(skill_index.all_skills(registry.SKILLCHIP))
    assert skill_index.verify_chip(out)[0]
    assert set(r["skills"]) == set(skill_index.all_skills(registry.SKILLCHIP))
