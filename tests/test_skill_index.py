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


def test_tamper_and_missing_are_detected(tmp_path, monkeypatch):
    s = "fs"
    shutil.copytree(os.path.join(skill_index.SKILLS, s), tmp_path / "skills" / s)
    monkeypatch.setattr(skill_index, "SKILLS", str(tmp_path / "skills"))
    assert skill_index.verify(s)[0]                              # the copy is authentic

    snippet = tmp_path / "skills" / s / "perks" / "find_large" / "src" / "fs_find_large.sh"
    snippet.write_text("# tampered\n")
    ok, problems = skill_index.verify(s)
    assert not ok and any("changed" in p for p in problems)

    snippet.unlink()
    assert any("missing" in p for p in skill_index.verify(s)[1])
