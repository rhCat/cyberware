"""Mutation-pinning slice for infra/govern/snippetverify.py — the R3 gate cws-mutate/mut-snippet-verify
(P1-T10). Pins both sides of the per-step snippet TOCTOU decision so a single-token mutation flips an
assertion. Imports cwd-relative (resolves to the mutator's sandbox copy)."""
import hashlib
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from infra.govern.snippetverify import sha256_full, snippet_decision  # noqa: E402


def _write(d, name, data):
    open(os.path.join(str(d), name), "wb").write(data)


def test_clean_match_no_refusal(tmp_path):
    _write(tmp_path, "tool.sh", b"BODY")
    refuse, fname, want, found = snippet_decision(True, "1", {"1": "tool"},
                                                  {"tool.sh": sha256_full(b"BODY")}, str(tmp_path))
    assert refuse is False and fname == "tool.sh" and found == sha256_full(b"BODY")


def test_drift_refused(tmp_path):
    _write(tmp_path, "tool.sh", b"MUTATED")
    refuse, _f, _w, found = snippet_decision(True, "1", {"1": "tool"},
                                             {"tool.sh": sha256_full(b"BODY")}, str(tmp_path))
    assert refuse is True and found == sha256_full(b"MUTATED")


def test_missing_file_refused(tmp_path):
    refuse, _f, want, found = snippet_decision(True, "1", {"1": "tool"},
                                               {"tool.sh": sha256_full(b"BODY")}, str(tmp_path))
    assert refuse is True and found is None and want == sha256_full(b"BODY")


def test_snip_verify_off_is_noop(tmp_path):
    assert snippet_decision(False, "1", {"1": "tool"}, {}, str(tmp_path)) == (False, None, None, None)


def test_step_not_in_tool_is_noop(tmp_path):
    assert snippet_decision(True, "9", {"1": "tool"}, {}, str(tmp_path)) == (False, None, None, None)


def test_unblessed_file_not_refused(tmp_path):
    _write(tmp_path, "tool.sh", b"BODY")
    refuse, _f, want, found = snippet_decision(True, "1", {"1": "tool"}, {}, str(tmp_path))
    assert refuse is False and want is None and found == sha256_full(b"BODY")


def test_concat_builds_the_right_key(tmp_path):
    _write(tmp_path, "tool.sh", b"MUTATED")                       # blessed differs -> must be FOUND + refused
    refuse, fname, _w, _f = snippet_decision(True, "1", {"1": "tool"},
                                             {"tool.sh": sha256_full(b"BODY")}, str(tmp_path))
    assert fname == "tool.sh" and refuse is True                  # if + -> -, fname is wrong, drift missed


def test_sha256_full_str_and_bytes():
    assert sha256_full("x") == sha256_full(b"x") == hashlib.sha256(b"x").hexdigest()
