#!/usr/bin/env python3
# infra/exec/closureverify.py: the materialized-closure INTEGRITY surface (P2-T12), a prose-clean executable
# core. In delegated mode exod re-derives the digest of every file the confined step will source, right
# before the run, then requires it to match what govd signed into the grant. So a post-grant swap of a
# porter / a core (the snippet TOCTOU class) is refused at TIME OF USE, independently of any digest the
# caller computed; a materialized code member the grant never pinned (a smuggled sibling) is refused too.
# exod.py imports closure_decision; this file is the R3 mutation target. Comments here carry NO space-anchored
# operator tokens, so every surviving mutant is a real, test-killable comparison.
from __future__ import annotations
import hashlib
import os

UNPINNED_BY_DESIGN = "contracts.json"      # the lone src member the plan leaves unpinned (compiler drops it); data
_CODE_SUFFIXES = (".sh", ".py")


def digest_file(path):
    # full sha256 hex of a file's bytes; the same digest the skill authenticity index pins into the grant
    with open(path, "rb") as f:
        return hashlib.sha256(f.read()).hexdigest()


def closure_decision(pinned, snip_dir):
    # the per-run closure check, re-derived from the bytes on disk. `pinned` is the grant's name->digest map
    # govd signed; `snip_dir` is the directory the porter actually reads. Returns (refuse, reason). Every
    # pinned member must be present at its blessed digest; a materialized code member the grant did not pin is
    # a smuggled sibling, refused. When the grant pins nothing the gate refuses ONLY where code was staged, so
    # a raw-argv run that materialized no closure stays runnable.
    files = []
    if os.path.isdir(snip_dir):
        for name in sorted(os.listdir(snip_dir)):
            if os.path.isfile(os.path.join(snip_dir, name)):
                files.append(name)
    if not pinned:
        for name in files:
            if name.endswith(_CODE_SUFFIXES):
                return True, "closure:unpinned:" + name
        return False, "ok"
    for name, want in sorted(pinned.items()):
        fp = os.path.join(snip_dir, name)
        if not os.path.isfile(fp):
            return True, "closure:missing:" + name
        if digest_file(fp) != want:
            return True, "closure:mismatch:" + name
    for name in files:
        if name in pinned:
            continue
        if name == UNPINNED_BY_DESIGN:
            continue
        return True, "closure:smuggled:" + name
    return False, "ok"
