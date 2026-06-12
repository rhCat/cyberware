#!/usr/bin/env python3
"""registry.py — where the **skillChip** (cyberware's skill feed-stock) lives.

cyberware is the *engine*; the skillChip is the *cartridge* — a separate, swappable registry of skills
(its own git repo, vendored here as the `skillChip/` submodule). The infra reads every skill and its
`index.json` from the skillChip, located by a **hardcoded default** (`<repo>/skillChip`) or overridden by
`$CYBERWARE_SKILLCHIP`. The chip is **self-describing**: `<skillChip>/index.json` is its manifest — each
skill with its `skill_sha`, plus a roll-up `chip_sha` — which cyberware retrieves to discover + verify the
chip as a unit. Per-skill `index.json` stays for file-level authenticity.

The infra never reaches outside this one path: swap the chip (point `$CYBERWARE_SKILLCHIP` at another) and
the same engine governs a different feed-stock, unchanged.
"""
from __future__ import annotations
import os

_REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))   # infra/ -> the cyberware repo root

#: the skillChip root — hardcoded default (the bundled submodule), overridable for a different cartridge
SKILLCHIP = os.path.abspath(os.environ.get("CYBERWARE_SKILLCHIP") or os.path.join(_REPO, "skillChip"))

CHIP_MANIFEST = "index.json"   # the chip-level manifest at <skillChip>/index.json


def skill_dir(skill: str) -> str:
    """The directory of one skill on the chip."""
    return os.path.join(SKILLCHIP, skill)


def manifest_path() -> str:
    """The chip-level manifest cyberware retrieves to discover + verify the whole chip."""
    return os.path.join(SKILLCHIP, CHIP_MANIFEST)
