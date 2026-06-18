#!/usr/bin/env python3
"""skill_index.py — the per-skill authenticity manifest.

Each skill carries `skillChip/<skill>/index.json`: the sha256 of every file in the skill, plus a roll-up
`skill_sha`. It is the authenticity reference — govd blesses a plan against it, and the agent verifies
its OWN registry against it before running. Only hashes (never file bodies) cross the wire, so a skill's
authenticity is checkable without passing files back and forth.

  python3 -m infra.tool.skill_index --all              # (re)generate every skill's index.json
  python3 -m infra.tool.skill_index --skill pg_ops     # one skill
  python3 -m infra.tool.skill_index --check            # verify files match the index (CI; exit 1 on drift)
"""
from __future__ import annotations
import argparse, hashlib, json, os, sys

from infra import registry
from infra.cwp import canonical

SKILLS = registry.SKILLCHIP                             # the skillChip — the skill feed-stock cyberware reads
INDEX = "index.json"
MANIFEST = registry.CHIP_MANIFEST                       # the chip-level manifest at <skillChip>/index.json


def sha256_file(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


def skill_files(skill_dir):
    """relpath -> abspath for every file in the skill, excluding index.json itself + caches."""
    out = {}
    for dp, dirs, files in os.walk(skill_dir):
        dirs[:] = [d for d in dirs if d != "__pycache__"]
        for f in files:
            if f == INDEX or f.endswith(".pyc") or f == ".DS_Store":
                continue
            ap = os.path.join(dp, f)
            out[os.path.relpath(ap, skill_dir)] = ap
    return out


# Every path-taking helper resolves `skills_dir or SKILLS` at CALL time (not as a default arg) so the
# module-global SKILLS stays monkeypatchable, while callers can point at a different registry explicitly.

def _sd(skill, skills_dir=None):
    """The skill's directory, resolved flat OR source-grouped (`<chip>/<source>/<skill>`) via the registry."""
    return registry.skill_dir(skill, skills_dir or SKILLS)


def build_index(skill, skills_dir=None):
    skills_dir = skills_dir or SKILLS
    files = {rel: sha256_file(ap) for rel, ap in sorted(skill_files(_sd(skill, skills_dir)).items())}
    roll = canonical.digest(files)
    return {"skill": skill, "skill_sha": roll, "file_count": len(files), "files": files}


def write_index(skill, skills_dir=None):
    skills_dir = skills_dir or SKILLS
    idx = build_index(skill, skills_dir)
    open(os.path.join(_sd(skill, skills_dir), INDEX), "w").write(json.dumps(idx, indent=2) + "\n")
    return idx


def verify(skill, skills_dir=None):
    """(ok, problems) comparing the skill's files on disk to its committed index.json."""
    skills_dir = skills_dir or SKILLS
    sd = _sd(skill, skills_dir)
    ip = os.path.join(sd, INDEX)
    if not os.path.isfile(ip):
        return False, ["no index.json — run --skill " + skill]
    want = json.load(open(ip)).get("files", {})
    have = {rel: sha256_file(ap) for rel, ap in skill_files(sd).items()}
    problems = ([f"changed: {r}" for r in want if r in have and have[r] != want[r]]
                + [f"missing: {r}" for r in want if r not in have]
                + [f"untracked: {r}" for r in have if r not in want])
    return (not problems), problems


def scan_skills(skills_dir=None):
    """A DIRECTORY SCAN for skill dirs (any carrying a perks.json), across BOTH layouts — flat
    (`<chip>/<skill>`, e.g. a compiled cartridge) and source-grouped (`<chip>/<source>/<skill>`, the dev
    feed-stock). This is the ONLY place that lists the chip directory, and it is used ONLY to SEED a fresh
    chip's roster (`--chip --scan`) or as a no-manifest bootstrap — NEVER as the runtime load set. Routing
    the load set through a dir scan is what let foreign dirs ride along; the manifest is the authority
    instead (see `all_skills`)."""
    skills_dir = skills_dir or SKILLS
    found = set()
    for d in sorted(os.listdir(skills_dir)):
        dp = os.path.join(skills_dir, d)
        if not os.path.isdir(dp):
            continue
        if os.path.isfile(os.path.join(dp, "perks.json")):          # a flat skill at the chip root
            found.add(d)
        else:                                                        # maybe a SOURCE group — scan one level in
            for s in os.listdir(dp):
                if os.path.isfile(os.path.join(dp, s, "perks.json")):
                    found.add(s)
    return sorted(found)


def permitted_skills(skills_dir=None):
    """The cartridge's PERMIT LIST: the skills the root manifest (index.json) declares. Empty if no manifest
    (a fresh chip). This is the authority for what may load — an on-disk dir not in here is not permitted."""
    skills_dir = skills_dir or SKILLS
    mp = os.path.join(skills_dir, MANIFEST)
    if not os.path.isfile(mp):
        return []
    return sorted(s.get("skill") for s in (json.load(open(mp)) or {}).get("skills", []) if s.get("skill"))


def is_present(skill, skills_dir=None):
    """True iff the skill is actually on disk — a dir carrying a perks.json (flat OR source-grouped)."""
    skills_dir = skills_dir or SKILLS
    return os.path.isfile(os.path.join(_sd(skill, skills_dir), "perks.json"))


def loadable(skill, skills_dir=None):
    """(ok, reason) — a skill may load iff it is PERMITTED (declared in the manifest) AND PRESENT (on disk).
    reason ∈ {ok, not_permitted, absent}. The two-part check the cartridge model requires."""
    skills_dir = skills_dir or SKILLS
    if not permitted_skills(skills_dir):
        return (is_present(skill, skills_dir), "ok" if is_present(skill, skills_dir) else "absent")  # no manifest yet
    if skill not in permitted_skills(skills_dir):
        return False, "not_permitted"
    if not is_present(skill, skills_dir):
        return False, "absent"
    return True, "ok"


def all_skills(skills_dir=None):
    """The authoritative runtime load set: the manifest's PERMITTED skills that are also PRESENT on disk —
    NOT a directory scan. An undeclared dir (not permitted) never loads; a declared-but-absent skill is
    dropped from the load set. With NO manifest (a fresh chip), falls back ONCE to a directory scan to
    bootstrap. The root index.json is the authority — `os.listdir` is confined to `scan_skills`."""
    skills_dir = skills_dir or SKILLS
    permitted = permitted_skills(skills_dir)
    if not permitted:                                    # fresh chip, no manifest yet — bootstrap by scan
        return scan_skills(skills_dir)
    return [s for s in permitted if is_present(s, skills_dir)]


def skill_sha(skill, skills_dir=None):
    """The committed roll-up hash from index.json (None if the skill has no index yet)."""
    ip = os.path.join(_sd(skill, skills_dir), INDEX)
    return (json.load(open(ip)) or {}).get("skill_sha") if os.path.isfile(ip) else None


def _perk_vars(skills_dir, skill, perk):
    """The var KEYS a perk declares — required vs optional — read from its contracts.json (names only)."""
    cp = os.path.join(_sd(skill, skills_dir), "perks", perk, "src", "contracts.json")
    inputs = (json.load(open(cp)) or {}).get("inputs", {}) if os.path.isfile(cp) else {}
    return {"required": sorted(k for k, s in inputs.items() if (s or {}).get("required")),
            "optional": sorted(k for k, s in inputs.items() if not (s or {}).get("required"))}


def catalog(skills_dir=None):
    """The value-free discovery catalog of a registry: every skill, its authenticity status + skill_sha,
    and each perk's id/summary/destructive/var-KEYS. Names + hashes only — never a value. Both govd
    (/catalog over ITS registry) and the agent (local view of its own registry) build it from HERE, so the
    two can be compared by skill_sha without anything but metadata crossing the wire."""
    skills_dir = skills_dir or SKILLS
    skills = []
    for s in all_skills(skills_dir):
        ok, problems = verify(s, skills_dir)
        pj = os.path.join(_sd(s, skills_dir), "perks.json")
        perks = [{"id": p.get("id"), "summary": p.get("summary", ""),
                  "destructive": bool(p.get("destructive", False)),
                  "vars": _perk_vars(skills_dir, s, p.get("id", ""))}
                 for p in (json.load(open(pj)) or {}).get("perks", [])] if os.path.isfile(pj) else []
        skills.append({"skill": s, "verified": bool(ok), "skill_sha": skill_sha(s, skills_dir),
                       "drift": (None if ok else problems[:5]), "perks": perks})
    return {"skills": skills, "count": len(skills)}


def chip_manifest(skills_dir=None, roster=None):
    """The chip-level manifest: every skill in the cartridge + its skill_sha, plus a roll-up chip_sha.
    `roster` is the explicit member list to pin; default re-pins the CURRENTLY-permitted set (`all_skills`),
    so a re-pin refreshes shas WITHOUT absorbing an undeclared on-disk dir. cyberware retrieves this one file
    (`<skillChip>/index.json`) to discover + verify the whole cartridge as a unit."""
    skills_dir = skills_dir or SKILLS
    members = sorted(roster) if roster is not None else all_skills(skills_dir)
    entries = []
    for s in members:
        sip = os.path.join(_sd(s, skills_dir), INDEX)
        idx = json.load(open(sip)) if os.path.isfile(sip) else {}
        entries.append({"skill": s, "skill_sha": idx.get("skill_sha"), "file_count": idx.get("file_count")})
    roll = canonical.digest({e["skill"]: e["skill_sha"] for e in entries})
    # version + cartridge marker: the manifest is the authoritative roster (cartridge model). The dev chip is
    # the full feedstock (cartridge:false); a single-skill/roster cut by `cartridge.compile` sets cartridge:true.
    # chip_sha is the roll-up over skill_shas ONLY, so these descriptive fields never shift the chip identity.
    return {"chip": "skillChip", "version": 1, "cartridge": False,
            "count": len(entries), "skills": entries, "chip_sha": roll}


def write_manifest(skills_dir=None, roster=None):
    skills_dir = skills_dir or SKILLS
    m = chip_manifest(skills_dir, roster)
    open(os.path.join(skills_dir, MANIFEST), "w").write(json.dumps(m, indent=2) + "\n")
    return m


def verify_chip(skills_dir=None):
    """(ok, detail) — does the committed chip manifest match the skills actually on the chip?"""
    skills_dir = skills_dir or SKILLS
    mp = os.path.join(skills_dir, MANIFEST)
    if not os.path.isfile(mp):
        return False, "no chip manifest (index.json) — run --chip"
    want, have = json.load(open(mp)), chip_manifest(skills_dir)
    if want.get("chip_sha") != have["chip_sha"]:
        w = {e["skill"]: e["skill_sha"] for e in want.get("skills", [])}
        h = {e["skill"]: e["skill_sha"] for e in have["skills"]}
        changed = sorted(set(w) ^ set(h)) or [s for s in h if w.get(s) != h[s]]
        return False, f"chip_sha mismatch (skills changed: {changed[:5]})"
    return True, "chip authentic"


def main():
    ap = argparse.ArgumentParser(description="generate / check the skillChip's sha256 authenticity indexes")
    ap.add_argument("--skill")
    ap.add_argument("--all", action="store_true")
    ap.add_argument("--chip", action="store_true", help="(re)write the chip manifest (index.json) over the permitted roster")
    ap.add_argument("--add", nargs="+", metavar="SKILL", help="with --chip: add skill(s) to the permitted roster (must be present)")
    ap.add_argument("--remove", nargs="+", metavar="SKILL", help="with --chip: remove skill(s) from the permitted roster")
    ap.add_argument("--scan", action="store_true", help="with --chip: SEED the roster from a directory scan (bootstrap a fresh chip)")
    ap.add_argument("--check", action="store_true", help="verify files match the indexes + the chip manifest (no writes)")
    a = ap.parse_args()
    skills = [a.skill] if a.skill else all_skills()

    if a.check:
        drift = 0
        for s in skills:
            ok, probs = verify(s)
            print(f"  [{'ok' if ok else 'DRIFT'}] {s}" + ("" if ok else " — " + "; ".join(probs)))
            drift += 0 if ok else 1
        cok, cdetail = verify_chip()
        print(f"  [{'ok' if cok else 'DRIFT'}] chip manifest — {cdetail}")
        drift += 0 if cok else 1
        print(f"skill_index: {'all authentic' if not drift else f'{drift} drift(s)'}")
        sys.exit(1 if drift else 0)

    if a.chip:
        roster = None
        if a.scan:
            roster = scan_skills()                       # bootstrap: seed the roster from disk (explicit)
        elif a.add or a.remove:
            roster = set(permitted_skills() or scan_skills())
            for s in (a.add or []):
                if not is_present(s):
                    sys.exit(f"skill_index: cannot add absent skill {s}")
                roster.add(s)
            roster -= set(a.remove or [])
            roster = sorted(roster)
        m = write_manifest(roster=roster)
        print(f"skill_index: wrote chip manifest — {m['count']} skills · chip_sha {m['chip_sha'][:16]}")
        return

    for s in skills:
        idx = write_index(s)
        print(f"  indexed {s}: {idx['file_count']} files · skill_sha {idx['skill_sha'][:16]}")
    m = write_manifest()                                 # any per-skill change rolls up into the chip manifest
    print(f"skill_index: wrote {len(skills)} index.json + the chip manifest (chip_sha {m['chip_sha'][:16]})")


if __name__ == "__main__":
    main()
