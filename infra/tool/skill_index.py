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


def build_index(skill):
    files = {rel: sha256_file(ap) for rel, ap in sorted(skill_files(os.path.join(SKILLS, skill)).items())}
    roll = hashlib.sha256(json.dumps(files, sort_keys=True).encode()).hexdigest()
    return {"skill": skill, "skill_sha": roll, "file_count": len(files), "files": files}


def write_index(skill):
    idx = build_index(skill)
    open(os.path.join(SKILLS, skill, INDEX), "w").write(json.dumps(idx, indent=2) + "\n")
    return idx


def verify(skill):
    """(ok, problems) comparing the skill's files on disk to its committed index.json."""
    sd = os.path.join(SKILLS, skill)
    ip = os.path.join(sd, INDEX)
    if not os.path.isfile(ip):
        return False, ["no index.json — run --skill " + skill]
    want = json.load(open(ip)).get("files", {})
    have = {rel: sha256_file(ap) for rel, ap in skill_files(sd).items()}
    problems = ([f"changed: {r}" for r in want if r in have and have[r] != want[r]]
                + [f"missing: {r}" for r in want if r not in have]
                + [f"untracked: {r}" for r in have if r not in want])
    return (not problems), problems


def all_skills():
    return sorted(d for d in os.listdir(SKILLS) if os.path.isdir(os.path.join(SKILLS, d)))


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
