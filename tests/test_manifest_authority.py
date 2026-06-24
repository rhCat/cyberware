"""S4 — the skillChip load set is manifest-authoritative (the cartridge model): enumeration reads the root
manifest's PERMITTED roster, never a directory scan. An undeclared dir on disk does not load; a declared-but-
absent skill is dropped; a skill is loadable iff permitted AND present; and the roster is mutated explicitly
(--scan / --add / --remove), never auto-absorbed. Pure stdlib."""
from __future__ import annotations
import os
import shutil

from infra import registry
from infra.tool import skill_index as si


def _mini_chip(tmp_path, skills=("git_ops", "fs")):
    """A throwaway (flat) chip: copy a couple real skills + seed the manifest by scan (the bootstrap path).
    The copy SOURCE is resolved wherever each skill lives on the real chip (any source group)."""
    chip = tmp_path / "chip"
    chip.mkdir()
    for s in skills:
        shutil.copytree(registry.skill_dir(s), chip / s)
    si.write_manifest(str(chip), roster=si.scan_skills(str(chip)))
    return str(chip)


def test_load_set_is_the_manifest_not_the_directory(tmp_path):
    chip = _mini_chip(tmp_path, ("git_ops", "fs"))
    assert sorted(si.all_skills(chip)) == ["fs", "git_ops"]
    # drop an UNDECLARED dir on disk → it must NOT be enumerated (not permitted)
    shutil.copytree(registry.skill_dir("markdown"), os.path.join(chip, "markdown"))
    assert "markdown" not in si.all_skills(chip)                 # present but not in the manifest → ignored
    assert si.loadable("markdown", chip) == (False, "not_permitted")
    assert si.loadable("fs", chip) == (True, "ok")


def test_declared_but_absent_is_dropped_from_the_load_set(tmp_path):
    chip = _mini_chip(tmp_path, ("git_ops", "fs"))
    shutil.rmtree(os.path.join(chip, "fs"))                      # permitted in the manifest, but gone from disk
    assert si.all_skills(chip) == ["git_ops"]                   # absent skill dropped
    assert si.loadable("fs", chip) == (False, "absent")


def test_repin_does_not_auto_absorb_a_stray_dir(tmp_path):
    chip = _mini_chip(tmp_path, ("git_ops", "fs"))
    shutil.copytree(registry.skill_dir("markdown"), os.path.join(chip, "markdown"))
    si.write_manifest(str(chip))                                # plain re-pin: refresh shas, do NOT absorb markdown
    assert "markdown" not in si.permitted_skills(chip)
    # explicit --add semantics: only an intentional roster op permits it
    si.write_manifest(str(chip), roster=sorted(set(si.permitted_skills(chip)) | {"markdown"}))
    assert "markdown" in si.permitted_skills(chip) and "markdown" in si.all_skills(chip)


def test_scan_seeds_a_fresh_chip(tmp_path):
    chip = tmp_path / "fresh"
    chip.mkdir()
    for s in ("git_ops", "fs", "markdown"):
        shutil.copytree(registry.skill_dir(s), chip / s)
    # no manifest yet → all_skills bootstraps by scan
    assert sorted(si.all_skills(str(chip))) == ["fs", "git_ops", "markdown"]
    si.write_manifest(str(chip), roster=si.scan_skills(str(chip)))
    assert sorted(si.permitted_skills(str(chip))) == ["fs", "git_ops", "markdown"]


def test_the_real_chip_is_41_and_authentic():
    assert len(si.all_skills()) == 41
    assert set(si.all_skills()) == set(si.permitted_skills())    # permitted == present, no drift


def test_skill_dir_rejects_traversal_and_absolute_names(tmp_path):
    """The resolver is the single chokepoint every SKILLCHIP/<skill> join now flows through, and the skill
    name can be agent-supplied — so a `..`/absolute/separator name must never escape the chip, and must
    resolve to a deterministically-ABSENT path (fail-closed), not raise."""
    chip = _mini_chip(tmp_path, ("fs",))
    root = os.path.realpath(chip)
    assert os.path.realpath(registry.skill_dir("fs", chip)).startswith(root)   # a real name resolves inside
    assert si.is_present("fs", chip)
    for bad in ("../evil", "/etc", "", ".", "..", "a/b", "cws/fs", "x\\y"):
        d = registry.skill_dir(bad, chip)
        assert os.path.realpath(d).startswith(root), f"{bad!r} escaped the chip -> {d}"
        assert not si.is_present(bad, chip)                       # invalid name => treated as absent
    assert registry.valid_skill_name("fs") and not registry.valid_skill_name("../x")
