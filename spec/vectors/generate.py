#!/usr/bin/env python3
"""Generate spec/vectors/corpus.json — the JCS canonicalization vector corpus (P0-T07, canonicalization
+ digest slice; signature + chip-fixture vectors are ROADMAP, pending infra/cwp/sign.py).

Each vector is `{name, input}` — just the input JSON value. The corpus is the shared input set; the
cross-language harness (tests/test_crosslang.py) computes the canonical bytes + sha256 with BOTH
infra/cwp/canonical.py and the independent Go verifier and asserts they agree byte-for-byte. Deterministic
(no randomness) so the corpus is reproducible.

  python3 spec/vectors/generate.py        # writes spec/vectors/corpus.json
"""
from __future__ import annotations
import json
import os

HERE = os.path.dirname(os.path.abspath(__file__))


def vectors():
    v = []

    # literals + empties
    for name, val in [("null", None), ("true", True), ("false", False), ("empty_str", ""),
                      ("empty_obj", {}), ("empty_arr", [])]:
        v.append((f"lit_{name}", val))

    # integers, including values beyond float64's exact range (must stay exact — int path, not ES6)
    for i in (0, 1, -1, 42, -42, 1000, 2**53, 2**53 + 1, 2**63, 10**30, -(10**30)):
        v.append((f"int_{i}", i))

    # ES6 Number::toString edges (floats), curated + a swept range across the fixed/exponential boundaries
    for f in (0.0, 4.5, 0.002, 1e30, 1e-27, 1e20, 1e21, 1e22, 1e-6, 1e-7, 1e15, 1e16,
              123456789.0, 3.141592653589793, 2.5e-10, 9.999999999999999e22, 5e-324):
        v.append((f"flt_{f!r}", f))
    for exp in range(-25, 26):
        for m in (1.0, 2.5, 9.99):
            v.append((f"sweep_{m}e{exp}", m * (10.0 ** exp)))

    # strings: every C0 control (→ \u00xx or a short escape), quote/backslash/slash, non-ASCII, surrogate pair
    for cp in range(0x00, 0x20):
        v.append((f"ctrl_{cp:02x}", chr(cp)))
    for name, s in [("quote", '"'), ("backslash", "\\"), ("slash", "/"), ("euro", "€"),
                    ("check", "✓"), ("eacute", "é"), ("zhong", "中"), ("emoji", "😀"),
                    ("mixed", 'a"b\\c/d\te\n€✓中😀')]:
        v.append((f"str_{name}", s))

    # object key ordering by UTF-16 code units (BMP + astral)
    v.append(("sort_basic", {"z": 1, "a": 2, "b": 3, "A": 4, "é": 5, "😀": 6, "中": 7}))
    v.append(("sort_prefix", {"ab": 1, "a": 2, "abc": 3, "": 4}))
    v.append(("sort_astral_vs_bmp", {"\U0001F600": 1, "￿": 2, "z": 3}))

    # nesting to depth, alternating object/array
    cur = "leaf"
    for d in range(1, 13):
        cur = {"k": cur, "n": d} if d % 2 else [cur, d]
        v.append((f"nest_{d}", cur))

    # the RFC 8785 Appendix B example (input) — cross-checked Py==Go
    v.append(("rfc8785_appendix_b", {
        "numbers": [333333333.33333329, 1e30, 4.50, 2e-3, 0.000000000000000000000000001],
        "string": "€$\nA'B\"\\\\\"/",
        "literals": [None, True, False],
    }))

    # representative real cyberware records (the shapes actually canonicalized)
    v.append(("rec_done_ledger_entry", {"seq": 1, "ts": "2026-06-13T00:00:00Z", "task_id": "P0-T12",
                                        "validator": "cws-conform", "verdict": "pass",
                                        "evidence_sha": "0" * 64, "prev": "0" * 64}))
    v.append(("rec_plan", {"skill": "cws-conform", "perk": "doclint", "sequence": ["cws_doclint"],
                           "snippet_shas": {"cws_doclint.py": "ab" * 32}, "skill_sha": "cd" * 32}))

    # chip fixtures — the authenticity shapes whose digest IS the chip's identity (covers "chip")
    v.append(("chip_skill_index", {"skill": "cws-conform", "skill_sha": "ab" * 32, "file_count": 9,
                                   "files": {"SKILL.md": "cd" * 32, "blueprint.json": "ef" * 32,
                                             "perks.json": "01" * 32}}))
    v.append(("chip_manifest", {"chip": "skillChip", "count": 3,
                                "skills": [{"skill": "cws-conform", "skill_sha": "11" * 32, "file_count": 9},
                                           {"skill": "cws-mutate", "skill_sha": "22" * 32, "file_count": 7},
                                           {"skill": "cws-observe", "skill_sha": "33" * 32, "file_count": 12}],
                                "chip_sha": "44" * 32}))
    v.append(("chip_empty_manifest", {"chip": "skillChip", "count": 0, "skills": [], "chip_sha": "00" * 32}))

    # P0-T04 digest-cutover call-site payloads — the EXACT objects the cutover routes through canonical_bytes,
    # so cws-conform/crosslang proves the Go anchor reproduces THESE bytes (not just the JCS engine):
    #  - the full 6-key plan_sha input INCLUDING `wrapper` (the one input carrying \n/\t/${} control chars)
    v.append(("rec_plan_full", {"skill": "cws-conform", "perk": "doclint", "sequence": ["cws_doclint"],
                                "wrapper": "set -e\nstep1() {\n\ttool ${X}\n}\n",
                                "snippet_shas": {"cws_doclint.py": "ab" * 32}, "skill_sha": "cd" * 32}))
    #  - the BARE maps skill_index actually hashes (skill_index.py:50 hashes `files`; :123 hashes {skill:skill_sha})
    v.append(("chip_files_map", {"SKILL.md": "cd" * 32, "blueprint.json": "ef" * 32, "perks.json": "01" * 32}))
    v.append(("chip_skillsha_map", {"cws-conform": "11" * 32, "cws-observe": "22" * 32}))
    v.append(("chip_skillsha_map_empty", {}))   # the chip roll of a chip with no skills
    #  - the v2 done-ledger genesis cross-reference record (decision-4 migration; tamper-bound cross-language)
    v.append(("rec_ledger_genesis", {"type": "genesis", "schema": 2, "supersedes": "done-ledger",
                                     "supersedes_file": "done-ledger.json", "supersedes_schema": 1,
                                     "supersedes_head": "00" * 32, "supersedes_count": 10, "prev": "0" * 64}))
    return v


def published():
    """The cyberphone/json-canonicalization reference vectors (external truth): each carries its
    published canonical `expected` output, which cws-conform/vectors verifies byte-for-byte (P0-T02)."""
    pub = os.path.join(HERE, "published")
    out = []
    idir = os.path.join(pub, "input")
    if os.path.isdir(idir):
        for fn in sorted(os.listdir(idir)):
            inp = json.load(open(os.path.join(idir, fn)))
            exp = open(os.path.join(pub, "output", fn), encoding="utf-8").read().rstrip("\n")
            out.append({"name": f"pub_{fn[:-5]}", "input": inp, "expected": exp})
    return out


def main():
    corpus = [{"name": n, "input": val} for n, val in vectors()] + published()
    out = os.path.join(HERE, "corpus.json")
    with open(out, "w") as f:
        json.dump(corpus, f, ensure_ascii=False, indent=2)
        f.write("\n")
    print(f"wrote {len(corpus)} vectors ({sum('expected' in v for v in corpus)} with published expected) → {out}")


if __name__ == "__main__":
    main()
