"""Unit: compiler.build_script + compiler.task_blueprint."""
from infra.govern import compiler
from infra.govern import runlog


def test_build_script_emits_step_per_tool_and_dispatcher():
    L = {"skill": "codebaseqc", "perk": "audit", "record_store": "/tmp/x",
         "vars": {"PROJECT_DIR": "/tmp/r", "SRC_DIR": "src", "TEST_DIR": "tests"}}
    text, seq = compiler.build_script(L)
    assert seq == ["cbqc_usage", "cbqc_contract", "cbqc_coverage"]
    for i, tool in enumerate(seq, 1):
        assert f"step{i}()" in text and tool in text
    assert "--list)" in text and "--step)" in text and "--all)" in text
    assert "set -uo pipefail" in text


def test_build_script_quotes_vars_against_injection():
    L = {"skill": "search", "perk": "grep", "record_store": "/tmp/x",
         "vars": {"PATTERN": "a; rm -rf ~", "SEARCH_DIR": "/tmp/r"}}
    text, _ = compiler.build_script(L)
    # the dangerous value must be single-quoted in the export line, not bare
    assert "'a; rm -rf ~'" in text


def test_build_script_appends_contract_output_check_after_last_step():
    L = {"skill": "codebaseqc", "perk": "audit", "record_store": "/tmp/x",
         "vars": {"PROJECT_DIR": "/tmp/r", "SRC_DIR": "src", "TEST_DIR": "tests"}}
    text, _ = compiler.build_script(L)
    assert "CONTRACT FAIL" in text and "coverage_gaps.json" in text


def test_task_blueprint_carries_resolved_task_and_contract(tmp_path):
    L = {"skill": "codebaseqc", "perk": "audit", "record_store": str(tmp_path),
         "vars": {"PROJECT_DIR": "/tmp/r", "SRC_DIR": "src", "TEST_DIR": "tests"}}
    run = runlog.run_dir(L)
    bp = compiler.task_blueprint(L, run)
    task = bp["task"]
    assert task["skill"] == "codebaseqc" and task["perk"] == "audit"
    assert task["tools"] == ["cbqc_usage", "cbqc_contract", "cbqc_coverage"]
    c = task["contract"]
    assert c["inputs"]["PROJECT_DIR"] == {"value": "/tmp/r", "type": "dir", "required": True}
    # the resolved check keeps the FULL path (not $RUN — that abbreviation is display-only)
    assert c["checks"]["output_exists"] == f"{run}/coverage_gaps.json"


def test_task_blueprint_binds_each_gate_to_a_concrete_check(tmp_path):
    L = {"skill": "codebaseqc", "perk": "audit", "record_store": str(tmp_path),
         "vars": {"PROJECT_DIR": "/tmp/r", "SRC_DIR": "src", "TEST_DIR": "tests"}}
    bp = compiler.task_blueprint(L, runlog.run_dir(L))
    gp = bp["gates"]["g_prepared"]["binding"]
    assert "PROJECT_DIR=/tmp/r" in gp and "writable" in gp
    gg = bp["gates"]["g_governed"]["binding"]
    assert "executor.py" in gg and "coverage_gaps.json" in gg
    # abstract atoms must be gone — every predicate resolved
    assert "inputs_present" not in gp and "contract_checks_pass" not in gg
