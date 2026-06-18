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


def source_groups(chip: str = None) -> list:
    """The chip's SOURCE groups — immediate subdirs that themselves hold skills (`cws/`, `general/`, and as
    other sources are merged, `nvidia/`, `claude/`, …). A dir qualifies iff it contains a `*/perks.json`.
    The legacy flat layout (skills directly at the chip root) has none."""
    chip = chip or SKILLCHIP
    if not os.path.isdir(chip):
        return []
    groups = []
    for d in sorted(os.listdir(chip)):
        p = os.path.join(chip, d)
        if os.path.isdir(p) and any(
                os.path.isfile(os.path.join(p, s, "perks.json"))
                for s in os.listdir(p) if os.path.isdir(os.path.join(p, s))):
            groups.append(d)
    return groups


def valid_skill_name(skill) -> bool:
    """A skill NAME is a single path segment — no separators, no parent/cur refs, not absolute. This is the
    gate that keeps a (possibly agent-supplied) name from escaping the chip when joined into a path."""
    return (isinstance(skill, str) and skill not in ("", ".", "..")
            and not os.path.isabs(skill)
            and "/" not in skill and "\\" not in skill and os.sep not in skill
            and (os.altsep is None or os.altsep not in skill))


def skill_dir(skill: str, chip: str = None) -> str:
    """Resolve a skill NAME to its directory — whether the chip is FLAT (`<chip>/<skill>`, e.g. a compiled
    single-skill cartridge) or SOURCE-grouped (`<chip>/<source>/<skill>`, the dev feed-stock). Skill names
    are unique across sources. Returns the flat path if not found (the caller handles absence).

    An INVALID name (containing `/`, `..`, an absolute path, …) never reaches `os.path.join` — it resolves to
    a deterministically-absent path *inside* the chip, so a `..`/`/etc` name can't traverse out and every
    `is_present`/`isdir`/`isfile` check on the result simply reports absence (fail-closed, no exception)."""
    chip = chip or SKILLCHIP
    if not valid_skill_name(skill):
        return os.path.join(chip, ".__invalid_skill_name__")    # cannot exist; cannot escape the chip
    flat = os.path.join(chip, skill)
    if os.path.isfile(os.path.join(flat, "perks.json")):
        return flat
    for src in source_groups(chip):
        cand = os.path.join(chip, src, skill)
        if os.path.isfile(os.path.join(cand, "perks.json")):
            return cand
    return flat


def source_for(skill: str) -> str:
    """The SOURCE group a skill belongs to BY CONVENTION: cyberware's own `cws-*` skills live under `cws/`,
    every other skill under `general/`. Skills merged from a named upstream (nvidia/, claude/, …) are placed
    in that source's dir explicitly when imported — this only governs where a freshly-scaffolded skill lands."""
    return "cws" if skill.startswith("cws-") else "general"


def new_skill_dir(skill: str, chip: str = None) -> str:
    """Where a freshly-scaffolded skill of this NAME belongs on the dev feed-stock: its source-grouped dir
    (`<chip>/cws/<skill>` or `<chip>/general/<skill>`). The scaffolder creates the source dir as needed."""
    chip = chip or SKILLCHIP
    return os.path.join(chip, source_for(skill), skill)


def manifest_path() -> str:
    """The chip-level manifest cyberware retrieves to discover + verify the whole chip."""
    return os.path.join(SKILLCHIP, CHIP_MANIFEST)
