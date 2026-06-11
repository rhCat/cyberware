#!/usr/bin/env python3
"""validator.py — are the task-ledger's claims real?

Walks the task-ledger + the skill's blueprint + the chosen perk's manifesto/contracts and checks the
*validatable* claims before anything is composed or compiled: `record_store` is a writable dir, the
perk's required binaries are reachable, the python runtime is reachable, the contract's required
inputs are present (and not still placeholders), the host is reachable (soft). Pure read-only
inspection — it touches nothing it doesn't own.

  validator.py --ledger task-ledger.json
"""
from __future__ import annotations
import argparse, json, os, shutil, socket, sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def load(p): return json.load(open(p))
def skill_dir(skill): return os.path.join(ROOT, "skills", skill)


def is_placeholder(v):
    return not isinstance(v, str) or v.strip() == "" or v.strip().startswith("<") or v.strip().startswith("${")


def check(name, ok, detail="", gating=True):
    tag = ("PASS" if ok else "FAIL") if gating else ("ok" if ok else "warn")
    print(f"  [{tag}] {name}" + (f" — {detail}" if detail else ""))
    return ok or not gating


def main():
    ap = argparse.ArgumentParser(description="validate a task-ledger's claims")
    ap.add_argument("--ledger", required=True)
    a = ap.parse_args()
    L = load(a.ledger)
    skill, perk = L["skill"], L["perk"]
    store, vars = L.get("record_store", ""), L.get("vars", {})
    sd = skill_dir(skill)
    manifesto = load(os.path.join(sd, "perks", perk, "manifesto.json"))
    contract = load(os.path.join(sd, "perks", perk, "src", "contracts.json"))
    print(f"validator · skill={skill} perk={perk}")
    ok = True

    # 1. record_store is (or can become) a writable dir
    if is_placeholder(store):
        ok &= check("record_store set", False, "still a placeholder")
    elif os.path.isdir(store):
        ok &= check("record_store writable", os.access(store, os.W_OK), store)
    else:
        parent = os.path.dirname(os.path.abspath(store)) or "."
        ok &= check("record_store creatable", os.path.isdir(parent) and os.access(parent, os.W_OK), store)

    # 2. runtimes / required binaries reachable
    ok &= check("python3 reachable", shutil.which("python3") is not None)
    for b in manifesto.get("requires", []):
        ok &= check(f"binary reachable: {b}", shutil.which(b) is not None)

    # 3. contract's required inputs present + concrete
    for k, spec in contract.get("inputs", {}).items():
        if spec.get("required"):
            v = vars.get(k)
            ok &= check(f"required input: {k}", v is not None and not is_placeholder(v),
                        "missing/placeholder" if (v is None or is_placeholder(v)) else "")

    # 4. host reachable — soft (warning only, networks flap)
    host, port = vars.get("PGHOST"), str(vars.get("PGPORT", "5432"))
    if host and not is_placeholder(host):
        reachable = False
        try:
            with socket.create_connection((host, int(port)), timeout=2):
                reachable = True
        except OSError:
            pass
        check(f"host reachable {host}:{port}", reachable, "" if reachable else "not reachable now", gating=False)

    print(f"validator: {'OK' if ok else 'FAIL'}")
    sys.exit(0 if ok else 1)


if __name__ == "__main__":
    main()
