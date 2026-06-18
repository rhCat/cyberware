"""The skillChip cartridge: compile the dev chip down to a flexible cartridge whose ROOT manifest (index.json
+ chip_sha) is the authoritative load set — in the limit one skill. govd then needs only the declared skill(s)
+ the root sha; an undeclared dir on disk cannot ride along, and a tampered file breaks the root verification.
Pure stdlib."""
from __future__ import annotations
import os

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
    # only the rostered skills exist in the cartridge; the rest of the dev chip is absent
    present = sorted(d for d in os.listdir(out) if os.path.isdir(os.path.join(out, d)))
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
    # mutate a file inside the cartridge → the root-sha / skill_sha verification must catch it
    import glob
    victim = next(iter(glob.glob(os.path.join(out, target, "**", "*.json"), recursive=True)), None)
    assert victim
    with open(victim, "a") as f:
        f.write("\n")
    v = cartridge.verify(out)
    assert not v["ok"] and v["problems"]
