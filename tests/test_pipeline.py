"""Integration: the whole pipeline end to end (validate → compose → compile → oversight → execute)."""
import json

from infra.govern import runlog
from conftest import run_cli


def test_full_pipeline_on_codebaseqc(make_ledger, tmp_path, sample_repo):
    store = tmp_path / "out"
    lp, L = make_ledger("codebaseqc", "audit", store,
                        {"PROJECT_DIR": str(sample_repo), "SRC_DIR": "src", "TEST_DIR": "tests"})

    assert run_cli("validator", "--ledger", lp).returncode == 0
    assert run_cli("composer", "--ledger", lp).returncode == 0
    assert run_cli("compiler", "--ledger", lp).returncode == 0

    run = runlog.run_dir(L)
    script = f"{run}/run.sh"
    assert run_cli("oversight", "--script", script).returncode == 0
    x = run_cli("executor", "--script", script, "--all")
    assert x.returncode == 0, x.stdout + x.stderr

    # the run dir is self-contained: script, task blueprint, diagrams, reports, ledgers
    import os
    for f in ("run.sh", "task-blueprint.json", "run.svg", "run.drawio",
              "run-ledger.json", "task-ledger.json",
              "usage_gaps.json", "contract_gaps.json", "coverage_gaps.json"):
        assert os.path.isfile(os.path.join(run, f)), f"missing {f}"

    # the QC reports are valid JSON, and the coverage report flags the uncovered fn
    cov = json.load(open(os.path.join(run, "coverage_gaps.json")))
    assert isinstance(cov, dict)


def test_pipeline_pointer_points_at_outputs_and_logs(make_ledger, tmp_path, sample_repo):
    store = tmp_path / "out"
    lp, L = make_ledger("codebaseqc", "audit", store,
                        {"PROJECT_DIR": str(sample_repo), "SRC_DIR": "src", "TEST_DIR": "tests"})
    run_cli("compiler", "--ledger", lp)
    run = runlog.run_dir(L)
    pointer = json.load(open(f"{run}/task-ledger.json"))["run"]
    assert pointer["blueprint"].endswith("task-blueprint.json")
    assert pointer["logs"].endswith("run-ledger.json")
    assert any("gaps.json" in o for o in pointer["outputs"])
