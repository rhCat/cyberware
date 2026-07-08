"""Mutation-pinning slice for infra/exec/closureverify.py — exod's materialized-closure integrity surface.

In delegated mode exod re-derives the digest of every file the confined step will source and refuses a
post-grant swap (TOCTOU) or a smuggled sibling. These pin BOTH sides of every comparison + the True/False
returns with exact (refuse, reason) tuples, so a single-token mutation flips an assertion. Imports
cwd-relative (resolves to the mutator's sandbox copy)."""
import hashlib
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from infra.exec import closureverify as C  # noqa: E402


def _write(d, name, content):
    p = os.path.join(d, name)
    with open(p, "w") as f:
        f.write(content)
    return hashlib.sha256(content.encode()).hexdigest()


# ── digest_file: the re-derivation primitive ─────────────────────────────────────────────────────────

def test_digest_file_matches_sha256(tmp_path):
    sha = _write(str(tmp_path), "x.sh", "echo hi\n")
    assert C.digest_file(os.path.join(str(tmp_path), "x.sh")) == sha


# ── unpinned grant: refuse ONLY where code was staged (raw-argv runs stay runnable) ──────────────────

def test_empty_pin_no_files_is_ok(tmp_path):
    assert C.closure_decision({}, str(tmp_path)) == (False, "ok")


def test_empty_pin_missing_dir_is_ok(tmp_path):
    assert C.closure_decision({}, os.path.join(str(tmp_path), "nope")) == (False, "ok")


def test_empty_pin_only_data_file_is_ok(tmp_path):
    _write(str(tmp_path), "contracts.json", "{}")
    assert C.closure_decision({}, str(tmp_path)) == (False, "ok")


def test_empty_pin_with_staged_code_is_refused(tmp_path):
    _write(str(tmp_path), "evil.sh", "rm -rf /\n")
    assert C.closure_decision({}, str(tmp_path)) == (True, "closure:unpinned:evil.sh")


def test_empty_pin_with_staged_py_is_refused(tmp_path):
    _write(str(tmp_path), "evil.py", "import os\n")
    assert C.closure_decision({}, str(tmp_path)) == (True, "closure:unpinned:evil.py")


def test_empty_pin_with_noncode_file_is_refused(tmp_path):
    # denylist, not a suffix allowlist: ANY staged file other than contracts.json is refused under an empty pin
    _write(str(tmp_path), "evil.env", "SECRET=1\n")
    assert C.closure_decision({}, str(tmp_path)) == (True, "closure:unpinned:evil.env")


# ── pinned grant: every member present at its blessed digest, re-hashed at time of use ────────────────

def test_pinned_member_present_and_matching_is_ok(tmp_path):
    sha = _write(str(tmp_path), "a.sh", "echo a\n")
    assert C.closure_decision({"a.sh": sha}, str(tmp_path)) == (False, "ok")


def test_pinned_member_missing_is_refused(tmp_path):
    assert C.closure_decision({"a.sh": "deadbeef"}, str(tmp_path)) == (True, "closure:missing:a.sh")


def test_pinned_member_mismatch_is_refused(tmp_path):
    _write(str(tmp_path), "a.sh", "echo a\n")
    assert C.closure_decision({"a.sh": "deadbeef"}, str(tmp_path)) == (True, "closure:mismatch:a.sh")


def test_post_grant_swap_is_caught_at_time_of_use(tmp_path):
    blessed = _write(str(tmp_path), "a.sh", "echo benign\n")          # govd's blessed digest
    _write(str(tmp_path), "a.sh", "echo PWNED\n")                     # the porter swapped after the grant
    assert C.closure_decision({"a.sh": blessed}, str(tmp_path)) == (True, "closure:mismatch:a.sh")


def test_swapped_core_is_caught_even_when_porter_is_pristine(tmp_path):
    porter = _write(str(tmp_path), "cws.sh", "exec python3 cws.py\n")
    core = _write(str(tmp_path), "cws.py", "print('ok')\n")
    _write(str(tmp_path), "cws.py", "print('PWNED')\n")               # the .py the porter execs, swapped
    assert C.closure_decision({"cws.sh": porter, "cws.py": core}, str(tmp_path)) \
        == (True, "closure:mismatch:cws.py")


def test_multi_member_all_matching_is_ok(tmp_path):
    a = _write(str(tmp_path), "a.sh", "echo a\n")
    b = _write(str(tmp_path), "b.py", "print('b')\n")
    assert C.closure_decision({"a.sh": a, "b.py": b}, str(tmp_path)) == (False, "ok")


# ── reverse direction: no smuggled sibling; contracts.json is the lone unpinned member allowed ───────

def test_contracts_json_is_allowed_unpinned(tmp_path):
    sha = _write(str(tmp_path), "a.sh", "echo a\n")
    _write(str(tmp_path), "contracts.json", "{}")
    assert C.closure_decision({"a.sh": sha}, str(tmp_path)) == (False, "ok")


def test_smuggled_code_sibling_is_refused(tmp_path):
    sha = _write(str(tmp_path), "a.sh", "echo a\n")
    _write(str(tmp_path), "evil.py", "import os\n")                   # an unpinned sibling a porter could source
    assert C.closure_decision({"a.sh": sha}, str(tmp_path)) == (True, "closure:smuggled:evil.py")


def test_smuggled_noncode_sibling_is_refused(tmp_path):
    sha = _write(str(tmp_path), "a.sh", "echo a\n")
    _write(str(tmp_path), "evil.txt", "data")                        # not contracts.json -> still refused
    assert C.closure_decision({"a.sh": sha}, str(tmp_path)) == (True, "closure:smuggled:evil.txt")


def test_nested_pinned_member_not_staged_fails_closed(tmp_path):
    # delegated mode materializes flat top-level src; a perk pinning a NESTED member (unsupported) fails
    # CLOSED with a clear closure:missing rather than running unverified — the documented flat-src boundary.
    sha = _write(str(tmp_path), "a.sh", "echo a\n")
    assert C.closure_decision({"a.sh": sha, "lib/helper.py": "deadbeef"}, str(tmp_path)) \
        == (True, "closure:missing:lib/helper.py")


def test_nested_pinned_member_is_verified(tmp_path):
    a = _write(str(tmp_path), "a.sh", "echo a\n")
    os.makedirs(os.path.join(str(tmp_path), "example"))
    nested = _write(str(tmp_path), os.path.join("example", "svc.py"), "def f(): pass\n")
    assert C.closure_decision({"a.sh": a, "example/svc.py": nested}, str(tmp_path)) == (False, "ok")


def test_nested_smuggled_sibling_is_refused(tmp_path):
    """The recursive smuggle scan must catch an unpinned file in a SUBDIR, not only at top level — else the
    identical file refused at top level slips through one directory down (the gap the recursive staging
    newly makes reachable)."""
    a = _write(str(tmp_path), "a.sh", "echo a\n")
    os.makedirs(os.path.join(str(tmp_path), "example"))
    _write(str(tmp_path), os.path.join("example", "evil.py"), "import os\n")
    assert C.closure_decision({"a.sh": a}, str(tmp_path)) == (True, "closure:smuggled:example/evil.py")
