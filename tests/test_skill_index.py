"""Unit: the per-skill sha256 authenticity index (infra/tool/skill_index)."""
import os
import shutil

from infra.tool import skill_index


def test_every_skill_has_an_authentic_index():
    skills = skill_index.all_skills()
    assert len(skills) >= 15
    for s in skills:
        ok, problems = skill_index.verify(s)
        assert ok, f"{s} index drift: {problems}"


def test_index_shape():
    idx = skill_index.build_index("fs")
    assert idx["skill"] == "fs" and len(idx["skill_sha"]) == 64
    assert idx["file_count"] == len(idx["files"])
    assert "perks/find_large/src/fs_find_large.sh" in idx["files"]
    assert "index.json" not in idx["files"]                      # the index never indexes itself


def test_catalog_is_value_free_and_covers_every_skill():
    c = skill_index.catalog()
    assert c["count"] == len(c["skills"]) == len(skill_index.all_skills())
    assert {s["skill"] for s in c["skills"]} == set(skill_index.all_skills())
    fs = next(s for s in c["skills"] if s["skill"] == "general:fs")
    assert fs["verified"] and len(fs["skill_sha"]) == 64 and fs["drift"] is None
    fl = next(p for p in fs["perks"] if p["id"] == "find_large")
    assert fl["vars"]["required"] == ["SEARCH_DIR"] and "MIN_SIZE" in fl["vars"]["optional"]
    assert any(p["destructive"] for s in c["skills"] for p in s["perks"])      # e.g. pg_ops/migrate surfaced
    # value-free: every var entry is a KEY name (a shell identifier), never a value
    import re
    name = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")
    for s in c["skills"]:
        for p in s["perks"]:
            assert all(name.match(k) for k in p["vars"]["required"] + p["vars"]["optional"])


def test_catalog_tags_a_foreign_registry(tmp_path):
    """catalog() over an arbitrary registry dir — the shared builder both govd and the agent use."""
    shutil.copytree(skill_index.SKILLS, tmp_path / "skills")
    skill_index.write_index("fs", str(tmp_path / "skills"))                    # regenerate so it's authentic
    c = skill_index.catalog(str(tmp_path / "skills"))
    assert next(s for s in c["skills"] if s["skill"] == "general:fs")["verified"]


def test_tamper_and_missing_are_detected(tmp_path, monkeypatch):
    s = "fs"
    shutil.copytree(skill_index._sd(s), tmp_path / "skills" / s)   # resolve fs wherever it lives (any source)
    monkeypatch.setattr(skill_index, "SKILLS", str(tmp_path / "skills"))
    assert skill_index.verify(s)[0]                              # the copy is authentic

    snippet = tmp_path / "skills" / s / "perks" / "find_large" / "src" / "fs_find_large.sh"
    snippet.write_text("# tampered\n")
    ok, problems = skill_index.verify(s)
    assert not ok and any("changed" in p for p in problems)

    snippet.unlink()
    assert any("missing" in p for p in skill_index.verify(s)[1])
