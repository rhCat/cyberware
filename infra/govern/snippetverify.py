#!/usr/bin/env python3
# infra/govern/snippetverify.py: the per-step snippet TOCTOU decision (P1-T05), extracted from executor.py
# as a prose-clean executable core. executor.py imports it; the R3 mutation gate (cws-mutate /
# mut-snippet-verify, P1-T10) mutates this file. Comments here carry NO space-anchored operator tokens, so
# every surviving mutant is a real, test-killable comparison rather than an un-killable operator-word.
from __future__ import annotations
import hashlib
import os


def sha256_full(b):
    # full sha256 hex; the executor's truncated sha() never matches index.json's full digest
    return hashlib.sha256(b if isinstance(b, bytes) else b.encode()).hexdigest()


def snippet_decision(snip_verify, st, step_tool, blessed, snip):
    # the per-step snippet check: returns (refuse, fname, want, found). refuse iff the porter's on-disk digest
    # does NOT equal the step's blessed digest. That single equality covers every drift class: a post-bless
    # MUTATION (blessed digest exists but differs); a blessed porter that is MISSING (found None vs a digest);
    # an UNBLESSED-but-PRESENT porter (a digest vs None — an emptied/corrupt index, a smuggled sibling, which
    # the old `want is not None` guard let run UNVERIFIED). It stays a no-op only when nothing needs verifying
    # while nothing is blessed (found None, want None → equal): verification off; the step has no tool; an
    # inline step whose on-disk porter is absent, whose blessed digest is absent (the porter-less channel case).
    if not (snip_verify and st in step_tool):
        return False, None, None, None
    fname = step_tool[st] + ".sh"
    want = blessed.get(fname)
    fp = os.path.join(snip, fname)
    found = sha256_full(open(fp, "rb").read()) if os.path.isfile(fp) else None
    refuse = found != want
    return refuse, fname, want, found
