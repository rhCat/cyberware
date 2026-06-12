#!/usr/bin/env python3
"""skill_index.py — the per-skill authenticity manifest.

Each skill carries `skills/<skill>/index.json`: the sha256 of every file in the skill, plus a roll-up
`skill_sha`. It is the authenticity reference — govd blesses a plan against it, and the agent verifies
its OWN registry against it before running. Only hashes (never file bodies) cross the wire, so a skill's
authenticity is checkable without passing files back and forth.

  python3 -m infra.tool.skill_index --all              # (re)generate every skill's index.json
  python3 -m infra.tool.skill_index --skill pg_ops     # one skill
  python3 -m infra.tool.skill_index --check            # verify files match the index (CI; exit 1 on drift)
"""
from __future__ import annotations
import argparse, hashlib, json, os, sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))            # infra/tool/ -> repo root
SKILLS = os.path.join(ROOT, "skills")
INDEX = "index.json"


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

def build_index(skill, skills_dir=None):
    skills_dir = skills_dir or SKILLS
    files = {rel: sha256_file(ap) for rel, ap in sorted(skill_files(os.path.join(skills_dir, skill)).items())}
    roll = hashlib.sha256(json.dumps(files, sort_keys=True).encode()).hexdigest()
    return {"skill": skill, "skill_sha": roll, "file_count": len(files), "files": files}


def write_index(skill, skills_dir=None):
    skills_dir = skills_dir or SKILLS
    idx = build_index(skill, skills_dir)
    open(os.path.join(skills_dir, skill, INDEX), "w").write(json.dumps(idx, indent=2) + "\n")
    return idx


def verify(skill, skills_dir=None):
    """(ok, problems) comparing the skill's files on disk to its committed index.json."""
    skills_dir = skills_dir or SKILLS
    sd = os.path.join(skills_dir, skill)
    ip = os.path.join(sd, INDEX)
    if not os.path.isfile(ip):
        return False, ["no index.json — run --skill " + skill]
    want = json.load(open(ip)).get("files", {})
    have = {rel: sha256_file(ap) for rel, ap in skill_files(sd).items()}
    problems = ([f"changed: {r}" for r in want if r in have and have[r] != want[r]]
                + [f"missing: {r}" for r in want if r not in have]
                + [f"untracked: {r}" for r in have if r not in want])
    return (not problems), problems


def all_skills(skills_dir=None):
    skills_dir = skills_dir or SKILLS
    return sorted(d for d in os.listdir(skills_dir) if os.path.isdir(os.path.join(skills_dir, d)))


def skill_sha(skill, skills_dir=None):
    """The committed roll-up hash from index.json (None if the skill has no index yet)."""
    ip = os.path.join(skills_dir or SKILLS, skill, INDEX)
    return (json.load(open(ip)) or {}).get("skill_sha") if os.path.isfile(ip) else None


def _perk_vars(skills_dir, skill, perk):
    """The var KEYS a perk declares — required vs optional — read from its contracts.json (names only)."""
    cp = os.path.join(skills_dir, skill, "perks", perk, "src", "contracts.json")
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
        pj = os.path.join(skills_dir, s, "perks.json")
        perks = [{"id": p.get("id"), "summary": p.get("summary", ""),
                  "destructive": bool(p.get("destructive", False)),
                  "vars": _perk_vars(skills_dir, s, p.get("id", ""))}
                 for p in (json.load(open(pj)) or {}).get("perks", [])] if os.path.isfile(pj) else []
        skills.append({"skill": s, "verified": bool(ok), "skill_sha": skill_sha(s, skills_dir),
                       "drift": (None if ok else problems[:5]), "perks": perks})
    return {"skills": skills, "count": len(skills)}


def main():
    ap = argparse.ArgumentParser(description="generate / check per-skill sha256 authenticity indexes")
    ap.add_argument("--skill")
    ap.add_argument("--all", action="store_true")
    ap.add_argument("--check", action="store_true", help="verify files match the index (no writes)")
    a = ap.parse_args()
    skills = [a.skill] if a.skill else all_skills()

    if a.check:
        drift = 0
        for s in skills:
            ok, probs = verify(s)
            print(f"  [{'ok' if ok else 'DRIFT'}] {s}" + ("" if ok else " — " + "; ".join(probs)))
            drift += 0 if ok else 1
        print(f"skill_index: {'all authentic' if not drift else f'{drift} skill(s) drifted'}")
        sys.exit(1 if drift else 0)

    for s in skills:
        idx = write_index(s)
        print(f"  indexed {s}: {idx['file_count']} files · skill_sha {idx['skill_sha'][:16]}")
    print(f"skill_index: wrote {len(skills)} index.json")


if __name__ == "__main__":
    main()
