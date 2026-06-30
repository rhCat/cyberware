"""The skillChip cartridge: compile the dev chip down to a flexible cartridge whose ROOT manifest (index.json
+ chip_sha) is the authoritative load set — in the limit one skill. govd then needs only the declared skill(s)
+ the root sha; an undeclared dir on disk cannot ride along, and a tampered file breaks the root verification.
Pure stdlib."""
from __future__ import annotations
import os

from infra import registry
from infra.tool import cartridge, skill_index


def test_selftest():
    r = cartridge.cartridge_selftest()
    assert r["ok"], r
    assert r["single_skill_cartridge_loads"] and r["chip_sha_is_one_skill_rollup"]
    assert r["only_declared_skill_present"] and r["tamper_breaks_root_sha"]


def test_single_skill_cartridge_declares_only_itself(tmp_path):
    src = skill_index.SKILLS
    target = "git_ops" if os.path.isdir(os.path.join(src, "git_ops")) else skill_index.all_skills(src)[0]
    out = str(tmp_path / "cart")
    info = cartridge.compile([target], out, source=src)
    assert info["count"] == 1 and info["skills"] == [target]
    # the root manifest is the load set — exactly the declared skill, nothing scanned in
    assert cartridge.declared_skills(out) == [target]
    v = cartridge.verify(out)
    assert v["ok"] and v["skills"] == [target] and v["chip_sha"] == info["chip_sha"]


def test_roster_cartridge_excludes_undeclared(tmp_path):
    src = skill_index.SKILLS
    avail = skill_index.all_skills(src)
    roster = [s for s in ("git_ops", "fs", "markdown") if s in avail][:2] or avail[:2]
    out = str(tmp_path / "roster")
    cartridge.compile(roster, out, source=src)
    # only the rostered skills exist in the cartridge; the rest of the dev chip is absent (scan_skills walks
    # the namespaced layout — <out>/<ns>/<name> — and returns the same ids the manifest declares)
    present = sorted(skill_index.scan_skills(out))
    assert present == sorted(roster)
    assert cartridge.verify(out)["ok"]


def test_compile_refuses_a_missing_skill(tmp_path):
    import pytest
    with pytest.raises(ValueError):
        cartridge.compile(["no-such-skill-xyz"], str(tmp_path / "x"))


def test_tampered_cartridge_fails_verify(tmp_path):
    src = skill_index.SKILLS
    target = "git_ops" if os.path.isdir(os.path.join(src, "git_ops")) else skill_index.all_skills(src)[0]
    out = str(tmp_path / "cart")
    cartridge.compile([target], out, source=src)
    assert cartridge.verify(out)["ok"]
    # mutate a skill SOURCE file → its hash no longer matches skill_sha → caught. (Deterministic: a fixed
    # file in the skill_sha set, NOT a glob — glob order is filesystem-dependent and could land on the
    # self-referential index.json, whose own bytes skill_sha cannot include.)
    with open(os.path.join(registry.skill_dir(target, out), "perks.json"), "a") as f:
        f.write("\n")
    v = cartridge.verify(out)
    assert not v["ok"] and v["problems"]


def test_rewritten_skill_manifest_fails_verify(tmp_path):
    """The sharper attack: tamper a file AND re-pin the skill's OWN index.json so files match it again —
    skill_index.verify then passes, but the per-skill manifest's skill_sha has drifted from the root chip
    manifest. verify must bind the two, or the cartridge isn't sealed (the root chip_sha is the load-set
    identity)."""
    src = skill_index.SKILLS
    target = "git_ops" if os.path.isdir(os.path.join(src, "git_ops")) else skill_index.all_skills(src)[0]
    out = str(tmp_path / "cart")
    cartridge.compile([target], out, source=src)
    with open(os.path.join(registry.skill_dir(target, out), "perks.json"), "a") as f:
        f.write("\n")
    skill_index.write_index(target, out)        # re-pin: files now match the skill's REWRITTEN index.json …
    v = cartridge.verify(out)
    assert not v["ok"] and v["problems"]         # … but its skill_sha no longer matches the root manifest
