#!/usr/bin/env python3
"""infra/tool/cartridge.py — compile a skillChip down to a flexible cartridge.

The skillChip is a **cartridge**: the dev tree carries many skills, but what govd LOADS is whatever the
cartridge's root `index.json` (the chip manifest, carrying `chip_sha`) declares — not whatever happens to sit
on disk. `compile()` cuts a standalone cartridge containing exactly a DECLARED set of skills (in the limit,
**one skill**) plus a fresh root manifest. Point `$CYBERWARE_SKILLCHIP` at it and govd needs only **the skill
itself + the root json's sha** — an undeclared dir cannot ride along, because it is not in the cartridge.

  * a **single-skill cartridge** — `compile(["cws-release"], out)` — is the compiled form: one skill + root
    json. govd serves that skill and nothing else; `chip_sha` is the one-skill roll-up.
  * a **roster cartridge** — `compile(["cws-conform","cws-ledgercheck",...], out)` — is the dev chip scoped
    to a declared roster, so foreign skills scaffolded into the source tree never enter the manifest.

`verify()` is the load-time check: every declared skill is present + authentic (its files match its
`skill_sha`), and the manifest's `chip_sha` equals the roll-up over those skills. Nothing else is consulted.
"""
from __future__ import annotations
import json
import os
import shutil

from infra import registry
from infra.cwp import canonical
from infra.tool import skill_index

INDEX = skill_index.INDEX                                     # per-skill index.json
MANIFEST = skill_index.MANIFEST                              # chip-level index.json


def compile(skills, out_dir: str, source=None) -> dict:
    """Cut a cartridge containing exactly `skills` (a list; one skill = the compiled single-skill form) into
    `out_dir`, with a freshly-pinned root manifest. Each source skill must be authentic. Returns
    {skills, chip_sha, path, count}."""
    source = source or skill_index.SKILLS
    if isinstance(skills, str):
        skills = [skills]
    if not skills:
        raise ValueError("a cartridge must declare at least one skill")
    os.makedirs(out_dir, exist_ok=True)
    for sk in skills:
        src = registry.skill_dir(sk, source)                 # resolve in the source chip — flat OR source-grouped
        if not os.path.isfile(os.path.join(src, "perks.json")):
            raise ValueError(f"no such skill in the source chip: {sk}")
        ok, drift = skill_index.verify(sk, source)
        if not ok:
            raise ValueError(f"refusing to compile an unauthentic skill {sk}: {str(drift)[:80]}")
        dst = registry.skill_dir(sk, out_dir)            # namespaced id -> <out>/<ns>/<name>; bare -> flat <out>/<name>
        os.makedirs(os.path.dirname(dst), exist_ok=True)
        if os.path.exists(dst):
            shutil.rmtree(dst)
        shutil.copytree(src, dst, ignore=shutil.ignore_patterns("__pycache__", "*.pyc", ".git"))
    # write the cartridge's authoritative root manifest over EXACTLY the declared skills
    entries = []
    for sk in sorted(skills):
        idx_p = os.path.join(registry.skill_dir(sk, out_dir), INDEX)
        idx = json.load(open(idx_p)) if os.path.isfile(idx_p) else {}
        entries.append({"skill": sk, "skill_sha": idx.get("skill_sha"), "file_count": idx.get("file_count")})
    roll = canonical.digest({e["skill"]: e["skill_sha"] for e in entries})
    manifest = {"chip": "skillChip", "count": len(entries), "skills": entries, "chip_sha": roll,
                "cartridge": True}
    open(os.path.join(out_dir, MANIFEST), "w").write(json.dumps(manifest, indent=2) + "\n")
    return {"skills": sorted(skills), "chip_sha": roll, "path": out_dir, "count": len(entries)}


def declared_skills(cartridge_dir: str) -> list:
    """The cartridge's load set — the skills its root manifest declares (NOT a directory scan)."""
    mp = os.path.join(cartridge_dir, MANIFEST)
    if not os.path.isfile(mp):
        return []
    return [s["skill"] for s in json.load(open(mp)).get("skills", [])]


def verify(cartridge_dir: str) -> dict:
    """Load-time verification — all govd needs: the root manifest's declared skills are each present +
    authentic (files match skill_sha), and the manifest's chip_sha equals the roll-up over them. Returns
    {ok, chip_sha, skills, problems}. An undeclared dir on disk is irrelevant (it is not in the cartridge)."""
    mp = os.path.join(cartridge_dir, MANIFEST)
    if not os.path.isfile(mp):
        return {"ok": False, "problems": ["no root manifest (index.json)"]}
    man = json.load(open(mp))
    declared = man.get("skills", [])
    problems = []
    for e in declared:
        sk = e["skill"]
        if not os.path.isfile(os.path.join(registry.skill_dir(sk, cartridge_dir), "perks.json")):
            problems.append(f"{sk}: declared but absent")
            continue
        ok, drift = skill_index.verify(sk, cartridge_dir)
        if not ok:
            problems.append(f"{sk}: files do not match skill_sha ({str(drift)[:60]})")
        # bind the per-skill manifest to the root: the skill's OWN index.json skill_sha must equal what the
        # root manifest declares for it. Without this, tampering a file AND re-pinning the skill's index.json
        # would pass skill_index.verify (files match the rewritten index) while the root chip_sha — the load
        # set's identity — silently diverges. The per-skill manifest must not drift from the root.
        try:
            on_disk_sha = json.load(open(os.path.join(registry.skill_dir(sk, cartridge_dir), INDEX))).get("skill_sha")
        except Exception:
            on_disk_sha = None
        if on_disk_sha != e.get("skill_sha"):
            problems.append(f"{sk}: index.json skill_sha {str(on_disk_sha)[:12]} != manifest "
                            f"{str(e.get('skill_sha'))[:12]} (per-skill manifest drifted from the root)")
    roll = canonical.digest({e["skill"]: e.get("skill_sha") for e in declared})
    if roll != man.get("chip_sha"):
        problems.append(f"chip_sha mismatch: manifest={str(man.get('chip_sha'))[:12]} recomputed={roll[:12]}")
    return {"ok": not problems, "chip_sha": man.get("chip_sha"),
            "skills": [e["skill"] for e in declared], "problems": problems}


def cartridge_selftest() -> dict:
    """Compile a SINGLE-skill cartridge from the dev chip and prove the model: it loads with only the skill +
    the root json (verify ok, chip_sha = one-skill roll-up); a skill NOT in the cartridge is absent; and a
    tampered skill file breaks the root-sha verification (the cartridge is sealed). Hermetic."""
    import tempfile
    src = skill_index.SKILLS
    # pick a real, authentic, self-contained skill from the dev chip
    target = "git_ops" if os.path.isdir(os.path.join(src, "git_ops")) else skill_index.all_skills(src)[0]
    d = tempfile.mkdtemp(prefix="cartridge-")
    cart = os.path.join(d, "cart")
    info = compile([target], cart, source=src)

    v = verify(cart)
    single_skill = v["ok"] and v["skills"] == [target] and len(declared_skills(cart)) == 1
    sha_is_rollup = v["chip_sha"] == info["chip_sha"]
    foreign_absent = not os.path.isdir(os.path.join(cart, "cws-release"))   # only the declared skill is present

    # seal check: tamper a file inside the cartridge skill → root verification must fail
    import glob
    victim = next(iter(glob.glob(os.path.join(registry.skill_dir(target, cart), "perks", "*", "src", "*"))), None)
    tamper_caught = True
    if victim and os.path.isfile(victim):
        open(victim, "a").write("\n# tamper\n")
        tamper_caught = not verify(cart)["ok"]

    return {"single_skill_cartridge_loads": single_skill, "chip_sha_is_one_skill_rollup": sha_is_rollup,
            "only_declared_skill_present": foreign_absent, "tamper_breaks_root_sha": tamper_caught,
            "chip_sha": info["chip_sha"][:16],
            "ok": single_skill and sha_is_rollup and foreign_absent and tamper_caught}


if __name__ == "__main__":
    import argparse
    ap = argparse.ArgumentParser(description="compile a skillChip cartridge (one or more declared skills)")
    ap.add_argument("--compile", nargs="+", metavar="SKILL", help="skills to include in the cartridge")
    ap.add_argument("--out", help="output cartridge directory")
    ap.add_argument("--verify", metavar="DIR", help="verify a compiled cartridge directory")
    a = ap.parse_args()
    if a.verify:
        print(json.dumps(verify(a.verify), indent=2))
    elif a.compile and a.out:
        print(json.dumps(compile(a.compile, a.out), indent=2))
    else:
        ap.error("use --compile SKILL... --out DIR, or --verify DIR")
