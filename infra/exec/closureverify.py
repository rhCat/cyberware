#!/usr/bin/env python3
# infra/exec/closureverify.py: the materialized-closure INTEGRITY surface (P2-T12), a prose-clean executable
# core. In delegated mode exod re-derives the digest of every file in the materialized SNIP closure (the perk
# src the porter reads), right before the run, then requires it to match what govd signed into the grant. So a
# post-grant swap of a porter / a core (the snippet TOCTOU class) is refused at TIME OF USE, independently of
# any digest the caller computed; a materialized member the grant never pinned (a smuggled sibling) is refused
# too. The step's ENTRY wrapper (run.sh) lives OUTSIDE this closure; its integrity rests on the plan-hash that
# govd pins (the agent must present the matching plan_sha to run at all) plus govd writing it server-side.
# exod.py imports closure_decision; this file is the R3 mutation target. Comments here carry NO space-anchored
# operator tokens, so every surviving mutant is a real, test-killable comparison.
from __future__ import annotations
import hashlib
import os

UNPINNED_BY_DESIGN = "contracts.json"      # the lone src member the plan leaves unpinned (compiler drops it); data


def digest_file(path):
    # full sha256 hex of a file's bytes; the same digest the skill authenticity index pins into the grant
    with open(path, "rb") as f:
        return hashlib.sha256(f.read()).hexdigest()


def closure_decision(pinned, snip_dir):
    # the per-run closure check, re-derived from the bytes on disk. `pinned` is the grant's name->digest map
    # govd signed; `snip_dir` is the directory the porter actually reads. Returns (refuse, reason). Every
    # pinned member must be present at its blessed digest; any staged member the grant did not pin is refused
    # as a smuggled sibling (only contracts.json is allowed unpinned, both branches). When the grant pins
    # nothing the gate refuses any staged member too, so a raw-argv run that materialized no closure stays
    # runnable while an empty-pin run that staged a file is fail-closed.
    files = []
    if os.path.isdir(snip_dir):
        for name in sorted(os.listdir(snip_dir)):
            if os.path.isfile(os.path.join(snip_dir, name)):
                files.append(name)
    if not pinned:
        for name in files:
            if name == UNPINNED_BY_DESIGN:
                continue
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
