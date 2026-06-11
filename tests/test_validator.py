"""Integration: validator.py — does it pass real claims and fail placeholders?"""
from conftest import run_cli


def test_passes_when_required_inputs_present(make_ledger, tmp_path, sample_repo):
    lp, _ = make_ledger("codebaseqc", "audit", tmp_path / "out",
                        {"PROJECT_DIR": str(sample_repo), "SRC_DIR": "src", "TEST_DIR": "tests"})
    r = run_cli("validator", "--ledger", lp)
    assert r.returncode == 0, r.stdout + r.stderr
    assert "OK" in r.stdout


def test_fails_when_required_input_is_a_placeholder(make_ledger, tmp_path):
    lp, _ = make_ledger("codebaseqc", "audit", tmp_path / "out",
                        {"PROJECT_DIR": "<fill me>", "SRC_DIR": "src"})
    r = run_cli("validator", "--ledger", lp)
    assert r.returncode == 1
    assert "FAIL" in r.stdout and "PROJECT_DIR" in r.stdout


def test_fails_when_required_input_missing(make_ledger, tmp_path):
    lp, _ = make_ledger("codebaseqc", "audit", tmp_path / "out", {"SRC_DIR": "src"})
    r = run_cli("validator", "--ledger", lp)
    assert r.returncode == 1
