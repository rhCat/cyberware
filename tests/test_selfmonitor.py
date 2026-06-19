"""Unit: the ouroboros gate added after the source-subfolder migration — porter path hygiene.

The migration's only real regressions were porters that reached the repo/chip root by a FIXED-DEPTH `..` walk:
the added `cws/<skill>` level shifted every porter's depth by one and silently broke them. `check_porter_path_
hygiene` is the recurrence guard — a skill must be RELOCATABLE, reaching outside itself only via the registry
resolver / CYBERWARE_ROOT / an upward marker-search, never by counting directories. The live chip passes; a
planted fragile porter is flagged.
"""
import os

from infra import registry
from infra.tool import selfmonitor, skill_index as si


def test_real_chip_passes_porter_path_hygiene():
    ok, offenders = selfmonitor.check_porter_path_hygiene()
    assert ok, f"the live chip has fragile porters: {offenders[:5]}"


def test_fragile_porters_are_flagged(tmp_path, monkeypatch):
    chip = tmp_path / "chip"
    (chip / "general" / "demo" / "perks" / "go" / "src").mkdir(parents=True)
    (chip / "general" / "demo" / "perks.json").write_text(
        '{"skill": "demo", "perks": [{"id": "go", "summary": "x", "destructive": false, "tools": ["go"]}]}')
    src = chip / "general" / "demo" / "perks" / "go" / "src"
    (src / "go.sh").write_text('#!/usr/bin/env bash\nREPO="$(cd "$HERE/../../../../.." && pwd)"\n')   # raw depth-5 walk
    (src / "core.py").write_text('import os\nR = os.path.join(H, "..", "..", "..", "..")\nP = "skillChip/demo/x"\n')
    si.write_manifest(str(chip), roster=["demo"])                       # permit the skill (manifest authority)
    monkeypatch.setattr(registry, "SKILLCHIP", str(chip))
    monkeypatch.setattr(si, "SKILLS", str(chip))

    ok, offenders = selfmonitor.check_porter_path_hygiene()
    assert not ok
    joined = " ".join(offenders)
    assert "go.sh" in joined and "core.py" in joined                    # both languages caught
    assert any("fixed-depth" in o for o in offenders)                   # the `..`-walk smell (shell + python forms)
    assert any("skillChip/" in o for o in offenders)                    # the hardcoded-chip-path smell


def test_intra_skill_parent_walk_is_allowed(tmp_path, monkeypatch):
    """Reaching a porter's OWN skill root is `../../..` (3 up) and STABLE — it must NOT be flagged."""
    chip = tmp_path / "chip"
    (chip / "general" / "demo" / "perks" / "go" / "src").mkdir(parents=True)
    (chip / "general" / "demo" / "perks.json").write_text(
        '{"skill": "demo", "perks": [{"id": "go", "summary": "x", "destructive": false, "tools": ["go"]}]}')
    src = chip / "general" / "demo" / "perks" / "go" / "src"
    # depth-3 reaches the OWN skill root — allowed both as a bare `cd` and as a file read (`../../../SKILL.md`);
    # the gate must key on `..` SEGMENT depth (>=4 escapes), not on a trailing slash.
    (src / "go.sh").write_text('#!/usr/bin/env bash\nSKILL="$(cd "$HERE/../../.." && pwd)"\ncat "$HERE/../../../SKILL.md"\n')
    si.write_manifest(str(chip), roster=["demo"])
    monkeypatch.setattr(registry, "SKILLCHIP", str(chip))
    monkeypatch.setattr(si, "SKILLS", str(chip))

    ok, offenders = selfmonitor.check_porter_path_hygiene()
    assert ok, f"an intra-skill `../../..` walk was wrongly flagged: {offenders}"
    assert not os.path.exists(os.path.join(str(chip), "__pycache__"))   # sanity: walk didn't spawn artifacts
