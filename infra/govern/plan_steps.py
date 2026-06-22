#!/usr/bin/env python3
"""infra/govern/plan_steps.py — P1-T06 step-truth derivation (prose-clean enforcement core).

Derive the declared step ids with the step-to-tool map from the perk manifesto sequence (the blessed plan,
never the script list), AFTER authenticating manifesto.json against its blessed sha256 in the skill
index.json -- the same root of trust as the per-step porter digests. A missing / unblessed / tampered /
sequence-less manifesto yields the empty plan, so the executor declares zero steps, then refuses; a
post-bless manifesto swap cannot decouple the step-to-tool map from snippet verification.
"""
from __future__ import annotations
import hashlib
import json
import os


def blessed_sequence(snip):
    if not snip:
        return []
    perk_dir = os.path.dirname(snip)
    skill_dir = os.path.dirname(os.path.dirname(perk_dir))
    rel = "perks/" + os.path.basename(perk_dir) + "/manifesto.json"
    try:
        index = json.load(open(os.path.join(skill_dir, "index.json")))
        want = index.get("files", {}).get(rel)
        body = open(os.path.join(perk_dir, "manifesto.json"), "rb").read()
        if not want or hashlib.sha256(body).hexdigest() != want:
            return []
        return list(json.loads(body).get("sequence") or [])
    except Exception:
        return []


def plan_steps(snip):
    seq = blessed_sequence(snip)
    declared = [str(i) for i in range(1, len(seq) + 1)]
    step_tool = {str(i): tool for i, tool in enumerate(seq, 1)}
    return declared, step_tool
