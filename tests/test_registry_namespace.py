"""Step 1 — the namespaced skill resolver (infra/registry.py).

Pins parse_skill_id / canonicalize / skill_dir / new_skill_dir for <namespace>:<skill> addressing:
namespaced -> direct; bare -> unique-resolve else FAIL-CLOSED (no silent first-source-wins); every bad
segment (in either the namespace or the name) resolves to a sentinel INSIDE the chip — can neither escape
nor exist."""
from __future__ import annotations
import os

import pytest

from infra import registry as R


def _mkskill(chip, ns, name):
    d = os.path.join(chip, ns, name)
    os.makedirs(d, exist_ok=True)
    open(os.path.join(d, "perks.json"), "w").write("{}")
    return d


def test_parse_skill_id():
    assert R.parse_skill_id("general:search") == ("general", "search")   # exactly one colon
    assert R.parse_skill_id("search") == (None, "search")                # bare
    assert R.parse_skill_id("a:b:c") == (None, None)                     # >=2 colons -> invalid
    assert R.parse_skill_id(":x") == ("", "x")                           # empty ns (caller gates it)
    assert R.parse_skill_id("x:") == ("x", "")                           # empty name (caller gates it)
    assert R.parse_skill_id(123) == (None, None)                         # non-str -> invalid


def test_namespaced_resolves_direct(tmp_path):
    chip = str(tmp_path)
    _mkskill(chip, "magnumopus", "search")
    assert R.skill_dir("magnumopus:search", chip) == os.path.join(chip, "magnumopus", "search")


def test_bare_unique_resolves(tmp_path):
    chip = str(tmp_path)
    _mkskill(chip, "general", "alchemy")
    assert R.skill_dir("alchemy", chip) == os.path.join(chip, "general", "alchemy")


def test_bare_ambiguous_fails_closed(tmp_path):
    chip = str(tmp_path)
    _mkskill(chip, "general", "search")
    _mkskill(chip, "magnumopus", "search")
    d = R.skill_dir("search", chip)                                       # owned by TWO namespaces
    assert not os.path.isdir(d)                                           # NOT a silent first-source-win
    assert d.startswith(chip) and "ambiguous_or_absent" in d


def test_bad_segments_fail_closed_inside_chip(tmp_path):
    chip = str(tmp_path)
    for bad in ("..", "../etc", "/etc", "a:..", "..:b", "a:b:c", ":x", "x:", "ns:../x"):
        d = R.skill_dir(bad, chip)
        assert d.startswith(chip) and not os.path.isdir(d)               # sentinel inside the chip, cannot exist


def test_canonicalize(tmp_path):
    chip = str(tmp_path)
    _mkskill(chip, "general", "alchemy")
    _mkskill(chip, "general", "search")
    _mkskill(chip, "magnumopus", "search")
    assert R.canonicalize("magnumopus:search", chip) == "magnumopus:search"   # namespaced passes through
    assert R.canonicalize("alchemy", chip) == "general:alchemy"               # bare unique -> ns:name
    assert R.canonicalize("search", chip) == R.AMBIGUOUS                      # bare, 2 owners -> AMBIGUOUS
    assert R.canonicalize("nope", chip) == "nope"                            # unknown -> unchanged
    assert R.canonicalize("a:b:c", chip) == R.AMBIGUOUS                      # invalid -> AMBIGUOUS
    assert R.canonicalize("a:..", chip) == R.AMBIGUOUS                       # bad segment -> AMBIGUOUS


def test_flat_cartridge_bare_stays_bare(tmp_path):
    chip = str(tmp_path)                                                  # a compiled single-skill cartridge
    d = os.path.join(chip, "onlyskill"); os.makedirs(d)
    open(os.path.join(d, "perks.json"), "w").write("{}")
    assert R.skill_dir("onlyskill", chip) == d
    assert R.canonicalize("onlyskill", chip) == "onlyskill"


def test_new_skill_dir(tmp_path):
    chip = str(tmp_path)
    assert R.new_skill_dir("cws-fs", chip) == os.path.join(chip, "cws", "cws-fs")          # source_for convention
    assert R.new_skill_dir("alchemy", chip) == os.path.join(chip, "general", "alchemy")
    assert R.new_skill_dir("search", chip, namespace="magnumopus") == os.path.join(chip, "magnumopus", "search")
    assert R.new_skill_dir("nvidia:nim", chip) == os.path.join(chip, "nvidia", "nim")       # namespaced id
    for bad in ("../evil", "a:..", "..:b", "a:b:c"):
        with pytest.raises(ValueError):
            R.new_skill_dir(bad, chip)
