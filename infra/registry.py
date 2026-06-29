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


#: a non-id sentinel canonicalize() returns when a bare name is owned by >=2 namespaces (or is invalid) —
#: distinct from any real id (it contains a NUL), so callers fail CLOSED instead of guessing a winner.
AMBIGUOUS = "\x00AMBIGUOUS"


def parse_skill_id(skill_id):
    """Split a skill id into (namespace, name). EXACTLY one ':' -> (ns, name); ZERO ':' -> (None, name) [bare];
    TWO OR MORE ':' (or a non-str) -> (None, None) [invalid]. Segments are NOT validated here — callers gate
    each via valid_skill_name (the split happens BEFORE that gate, never loosening it to admit ':')."""
    if not isinstance(skill_id, str):
        return (None, None)
    parts = skill_id.split(":")
    if len(parts) == 1:
        return (None, parts[0])
    if len(parts) == 2:
        return (parts[0], parts[1])
    return (None, None)


def canonicalize(skill_id, chip: str = None) -> str:
    """The CANONICAL `ns:name` for a skill id — the back-compat shim govd uses to rewrite a BARE claim before
    governing. A namespaced id (both segments valid) passes through; a bare name -> `ns:name` iff EXACTLY ONE
    namespace owns it; -> AMBIGUOUS if >=2 own it (or the id is invalid); -> the bare name UNCHANGED if it is a
    flat compiled-cartridge skill or unknown (absence is reported downstream). Never raises."""
    chip = chip or SKILLCHIP
    ns, name = parse_skill_id(skill_id)
    if name is None or not valid_skill_name(name) or (ns is not None and not valid_skill_name(ns)):
        return AMBIGUOUS
    if ns is not None:
        return f"{ns}:{name}"
    if os.path.isfile(os.path.join(chip, name, "perks.json")):       # flat cartridge -> stays bare
        return name
    owners = [src for src in source_groups(chip)
              if os.path.isfile(os.path.join(chip, src, name, "perks.json"))]
    if len(owners) == 1:
        return f"{owners[0]}:{name}"
    if len(owners) >= 2:
        return AMBIGUOUS                                             # never first-source-wins (fail-closed)
    return name                                                     # unknown -> unchanged


def skill_dir(skill: str, chip: str = None) -> str:
    """Resolve a skill id to its directory. NAMESPACED (`ns:name`) resolves DIRECTLY to `<chip>/<ns>/<name>`.
    BARE (`name`) resolves FLAT (`<chip>/<name>`, a compiled cartridge) or to its source-group iff EXACTLY ONE
    namespace owns it; an AMBIGUOUS bare name (>=2 owners — the prior silent first-wins behaviour) or an
    UNKNOWN one resolves to a deterministically-absent path so every is_present check fails CLOSED.

    Path-safety: each segment is gated by the UNCHANGED valid_skill_name (split on ':' BEFORE the gate), so a
    `..`/`/etc`/absolute segment in either the namespace or the name resolves to a sentinel INSIDE the chip — it
    can neither escape nor exist. Never raises."""
    chip = chip or SKILLCHIP
    ns, name = parse_skill_id(skill)
    if name is None or not valid_skill_name(name) or (ns is not None and not valid_skill_name(ns)):
        return os.path.join(chip, ".__invalid_skill_id__")          # cannot exist; cannot escape
    if ns is not None:
        return os.path.join(chip, ns, name)                         # namespaced -> direct
    flat = os.path.join(chip, name)
    if os.path.isfile(os.path.join(flat, "perks.json")):
        return flat                                                 # flat compiled cartridge
    owners = [src for src in source_groups(chip)
              if os.path.isfile(os.path.join(chip, src, name, "perks.json"))]
    if len(owners) == 1:
        return os.path.join(chip, owners[0], name)
    return os.path.join(chip, ".__ambiguous_or_absent__")           # 0 (unknown) or >=2 (ambiguous): fail-closed


def source_for(skill: str) -> str:
    """The SOURCE group a skill belongs to BY CONVENTION: cyberware's own `cws-*` skills live under `cws/`,
    every other skill under `general/`. Skills merged from a named upstream (nvidia/, claude/, …) are placed
    in that source's dir explicitly when imported — this only governs where a freshly-scaffolded skill lands."""
    return "cws" if skill.startswith("cws-") else "general"


def new_skill_dir(skill: str, chip: str = None, namespace: str = None) -> str:
    """Where a freshly-scaffolded skill belongs on the dev feed-stock: its source-grouped dir
    (`<chip>/<namespace>/<name>`). The namespace is taken from (1) an explicit `namespace=`, else (2) a
    namespaced `ns:name` id, else (3) the `source_for` convention (`cws-*` -> `cws/`, otherwise `general/`).
    Validates BOTH the namespace and the name (same gate as `skill_dir`) — the WRITE path must not let a
    `..`/absolute segment escape the chip; raises rather than returning a sentinel, since creating a skill
    with a bad id is never intended."""
    chip = chip or SKILLCHIP
    ns, name = parse_skill_id(skill)
    if name is None:
        raise ValueError(f"invalid skill id {skill!r}: at most one ':' (namespace:name)")
    ns = namespace or ns or source_for(name)
    if not (valid_skill_name(ns) and valid_skill_name(name)):
        raise ValueError(f"invalid namespace/name {ns!r}/{name!r}: each must be a single path segment")
    return os.path.join(chip, ns, name)


def manifest_path() -> str:
    """The chip-level manifest cyberware retrieves to discover + verify the whole chip."""
    return os.path.join(SKILLCHIP, CHIP_MANIFEST)
