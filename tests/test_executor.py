"""Integration: executor.py — THE governed channel. Tamper, in-channel oversight, upstream, provenance.

These pin the governance contract: every exit code below is a refusal the framework promises.
"""
import json

from conftest import compiler_shaped_script, run_cli


def ledger(run_dir):
    return json.loads((run_dir / "run-ledger.json").read_text())


def test_clean_script_runs_and_is_recorded(tmp_path):
    store = tmp_path / "out"
    s = compiler_shaped_script(tmp_path / "run.sh", store, ['echo ok > "$RECORD_STORE/m.txt"'])
    r = run_cli("executor", "--script", s, "--all")
    assert r.returncode == 0
    assert "done (governed)" in r.stdout
    recs = ledger(store)["runs"]
    assert any(x.get("step") == "1" and x["status"] == "ok" and "stdout_sha" in x for x in recs)


def test_first_run_snapshots_then_drift_is_refused(tmp_path):
    store = tmp_path / "out"
    s = compiler_shaped_script(tmp_path / "run.sh", store, ['echo v1'])
    assert run_cli("executor", "--script", s, "--all").returncode == 0   # snapshot taken
    s.write_text(s.read_text() + "\n# tampered\n")                       # edit after snapshot
    r = run_cli("executor", "--script", s, "--all")
    assert r.returncode == 4 and "TAMPER" in r.stdout
    assert any(x.get("event") == "tamper_refused" for x in ledger(store)["runs"])


def test_unchanged_script_matches_snapshot(tmp_path):
    store = tmp_path / "out"
    s = compiler_shaped_script(tmp_path / "run.sh", store, ['echo v1'])
    run_cli("executor", "--script", s, "--all")
    r = run_cli("executor", "--script", s, "--step", "1")
    assert r.returncode == 0 and "matches snapshot" in r.stdout


def test_in_channel_oversight_refuses_dangerous_script(tmp_path):
    store = tmp_path / "out"
    s = compiler_shaped_script(tmp_path / "run.sh", store, ['echo "sudo rm -rf /"'])
    r = run_cli("executor", "--script", s, "--all")
    assert r.returncode == 7 and "OVERSIGHT" in r.stdout
    assert any(x.get("event") == "oversight_refused" for x in ledger(store)["runs"])


def test_approvable_violation_runs_only_with_executor_approve(tmp_path):
    store = tmp_path / "out"
    s = compiler_shaped_script(tmp_path / "run.sh", store, ['echo "TRUNCATE t;"'])
    assert run_cli("executor", "--script", s, "--all").returncode == 7         # refused
    r = run_cli("executor", "--script", s, "--all", "--approve", "truncate")   # waived
    assert r.returncode == 0
    assert any(x.get("event") == "oversight_waived" for x in ledger(store)["runs"])


def test_non_approvable_violation_cannot_be_waived(tmp_path):
    store = tmp_path / "out"
    s = compiler_shaped_script(tmp_path / "run.sh", store, ['echo "sudo id"'])
    r = run_cli("executor", "--script", s, "--all", "--approve", "sudo")
    assert r.returncode == 7


def test_upstream_step_must_run_first(tmp_path):
    store = tmp_path / "out"
    s = compiler_shaped_script(tmp_path / "run.sh", store, ['echo a', 'echo b'])
    r = run_cli("executor", "--script", s, "--step", "2")   # step 1 never ran
    assert r.returncode == 5 and "UPSTREAM" in r.stdout


def test_bad_step_refused_without_traceback(tmp_path):
    store = tmp_path / "out"
    s = compiler_shaped_script(tmp_path / "run.sh", store, ['echo a'])
    for bad in ("foo", "0", "99"):
        r = run_cli("executor", "--script", s, "--step", bad)
        assert r.returncode == 2, f"--step {bad}"
        assert "Traceback" not in r.stderr, f"--step {bad} leaked a traceback"
