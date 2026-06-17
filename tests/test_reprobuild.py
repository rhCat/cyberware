"""Reproducible engine build baseline for SV-1 (P0-T13): the Go anchor builds byte-identically from the same
source on two independent builders, so the published binary is provably the source. A flipped byte breaks the
match (the check discriminates). `diffoscope: empty` is proven by the byte-identity (a sha256 match is a sound
proof of an empty diff) and, where diffoscope is installed, confirmed by running it. Needs the go toolchain;
skips otherwise."""
from __future__ import annotations
import shutil

import pytest

from infra.cwp import reprobuild as RB

pytestmark = pytest.mark.skipif(shutil.which("go") is None, reason="reproducible build needs the go toolchain")


def test_selftest_holds():
    r = RB.reprobuild_selftest()
    assert r["ok"], r


def test_two_independent_builds_are_byte_identical():
    r = RB.dual_build()
    try:
        assert r["byte_identical"] and r["digest_a"] == r["digest_b"]
        assert len(r["digest_a"]) == 64                          # a real sha256, not an empty placeholder
    finally:
        shutil.rmtree(r["dir"], ignore_errors=True)


def test_a_flipped_byte_breaks_the_match():
    r = RB.reprobuild_selftest()
    assert r["tamper_detected"] and r["tamper_seen_by_diffoscope"]


def test_diff_is_empty_for_an_identical_pair():
    # either diffoscope ran and reported empty, or the byte-identity is the empty-diff proof
    r = RB.reprobuild_selftest()
    assert r["diff_empty"]
