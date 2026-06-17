#!/usr/bin/env python3
"""infra/cwp/reprobuild.py — reproducible engine build baseline (P0-T13, SV-1 / M1).

The engine anchor — the Go verifier under `verifiers/go` — must build **byte-identically** from the same
source on two independent builders (CI and anyone else), so the published binary is provably the source and
nothing smuggled in. We build it twice with deterministic flags (`-trimpath`, `CGO_ENABLED=0`,
`-buildvcs=false`, a pinned `SOURCE_DATE_EPOCH`) in *isolated* build caches — two independent builders — and
compare digests. `diffoscope: empty` is the acceptance: when the two artifacts are byte-identical the diff is
empty *by construction* (a sha256 match is a sound proof of an empty diffoscope report); where diffoscope is
installed we run it too and assert it agrees. A flipped byte in one artifact must break the match — the check
discriminates, it is not vacuously green.
"""
from __future__ import annotations
import hashlib
import os
import shutil
import subprocess
import tempfile

_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
ANCHOR_DIR = os.path.join(_ROOT, "verifiers", "go")
SOURCE_DATE_EPOCH = "1700000000"


def _det_env(gocache: str) -> dict:
    """A deterministic build environment: no cgo, no VCS stamping, a pinned epoch, an isolated cache (so the
    second build cannot reuse the first builder's cache — it is a genuinely independent build)."""
    env = dict(os.environ)
    env.update({"CGO_ENABLED": "0", "GOFLAGS": "-buildvcs=false", "SOURCE_DATE_EPOCH": SOURCE_DATE_EPOCH,
                "GOCACHE": gocache})
    return env


def _sha256(path: str) -> str:
    return hashlib.sha256(open(path, "rb").read()).hexdigest()


def build_anchor(out_path: str, gocache: str, src_dir: str = ANCHOR_DIR) -> str:
    """Build the Go anchor deterministically into `out_path`; return its sha256. `-trimpath` strips absolute
    paths so the binary does not depend on where it was built."""
    subprocess.run(["go", "build", "-trimpath", "-o", out_path, "."],
                   cwd=src_dir, env=_det_env(gocache), check=True, capture_output=True)
    return _sha256(out_path)


def dual_build(src_dir: str = ANCHOR_DIR) -> dict:
    """Two independent builds (isolated caches) of the same source. Returns digests + whether they match."""
    d = tempfile.mkdtemp(prefix="reprobuild-")
    a = build_anchor(os.path.join(d, "anchor.a"), os.path.join(d, "cache.a"), src_dir)
    b = build_anchor(os.path.join(d, "anchor.b"), os.path.join(d, "cache.b"), src_dir)
    return {"dir": d, "digest_a": a, "digest_b": b, "byte_identical": a == b,
            "path_a": os.path.join(d, "anchor.a"), "path_b": os.path.join(d, "anchor.b")}


def diffoscope_diff(path_a: str, path_b: str):
    """Returns (ran, empty). If diffoscope is installed, run it and report whether it found NO differences;
    otherwise (False, None) — the caller falls back to the byte-identity proof."""
    if not shutil.which("diffoscope"):
        return False, None
    r = subprocess.run(["diffoscope", "--exclude-directory-metadata=recursive", path_a, path_b],
                       capture_output=True, text=True)
    return True, (r.returncode == 0 and r.stdout.strip() == "")


def reprobuild_selftest(src_dir: str = ANCHOR_DIR) -> dict:
    """The hermetic P0-T13 demonstration: build the anchor twice and assert byte-identical (the dual-builder
    property); prove the diff is empty (diffoscope where present, else the sha256 match IS the empty-diff
    proof); then FLIP one byte in a copy and confirm the match breaks (and that diffoscope, where present,
    now reports a difference). `ok` iff identical + empty + the tamper is caught. Needs the go toolchain."""
    res = dual_build(src_dir)
    byte_identical = res["byte_identical"]

    ran, empty = diffoscope_diff(res["path_a"], res["path_b"])
    diff_empty = empty if ran else byte_identical            # byte-identical ⟹ empty diffoscope report

    # tamper: flip the last byte of a copy; the digest must change and (if available) diffoscope must object
    tpath = res["path_a"] + ".tampered"
    data = bytearray(open(res["path_a"], "rb").read())
    data[-1] ^= 0xFF
    open(tpath, "wb").write(bytes(data))
    tamper_detected = _sha256(tpath) != res["digest_a"]
    t_ran, t_empty = diffoscope_diff(res["path_a"], tpath)
    tamper_seen_by_diffoscope = (not t_empty) if t_ran else tamper_detected

    shutil.rmtree(res["dir"], ignore_errors=True)
    return {"byte_identical": byte_identical, "digest": res["digest_a"],
            "diffoscope_ran": ran, "diff_empty": diff_empty,
            "tamper_detected": tamper_detected, "tamper_seen_by_diffoscope": tamper_seen_by_diffoscope,
            "ok": byte_identical and diff_empty and tamper_detected and tamper_seen_by_diffoscope}
