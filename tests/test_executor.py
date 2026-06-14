"""Integration: executor.py — THE governed channel. Tamper, in-channel oversight, upstream, provenance.

These pin the governance contract: every exit code below is a refusal the framework promises
(4=tamper, 5=upstream, 6=timeout, 7=oversight, 8=snippet drift).
"""
import hashlib
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


# ── per-step snippet verification (P1-T05 / SV-2) ──────────────────────────────────────────────────

def _compiled_with_snippet(tmp_path, porter_body="echo ok"):
    """Hand-build a compiler-shaped script + its registry (a SNIP src dir with one porter, and the
    skill's index.json holding that porter's blessed sha256) — the exact shape compiler.py emits: a
    `SNIP=` line, a `<i>\\t<tool>` listing, and `bash "$SNIP/<tool>.sh"` per step. Returns
    (run.sh, store, porter_path, blessed_digest)."""
    src = tmp_path / "chip" / "sk" / "perks" / "pk" / "src"
    src.mkdir(parents=True)
    porter = src / "tool.sh"
    porter.write_text("#!/usr/bin/env bash\n" + porter_body + "\n")
    blessed = hashlib.sha256(porter.read_bytes()).hexdigest()
    (tmp_path / "chip" / "sk" / "index.json").write_text(
        json.dumps({"files": {"perks/pk/src/tool.sh": blessed}}))
    store = tmp_path / "rec"
    run = tmp_path / "run.sh"
    run.write_text(
        "#!/usr/bin/env bash\n"
        "# COMPILED by cyberware · skill=sk perk=pk\n"
        f"SNIP={src}\n"
        f"RECORD_STORE={store}\n"
        'step1() {   # tool\n'
        '  echo "[step 1] tool"\n'
        '  bash "$SNIP/tool.sh" || exit $?\n'
        '}\n'
        'case "${1:-}" in\n'
        '  --list) printf "1\\ttool\\n" ;;\n'
        '  --step) shift; "step${1:?step number}" ;;\n'
        '  --all) step1 ;;\n'
        '  *) echo usage >&2; exit 2 ;;\n'
        'esac\n')
    return run, store, porter, blessed


def test_clean_snippet_runs_with_no_false_refusal(tmp_path):
    run, store, _porter, _blessed = _compiled_with_snippet(tmp_path)
    r = run_cli("executor", "--script", run, "--step", "1")
    assert r.returncode == 0
    assert not any(x.get("event") == "snippet_refused" for x in ledger(store)["runs"])


def test_post_bless_snippet_mutation_refuses_exactly_that_step(tmp_path):
    """SV-2 / P1-T05: a perk source mutated AFTER blessing but BEFORE the step runs is refused at exactly
    that step, with expected-vs-found digests recorded — closing the snippet time-of-check/time-of-use gap."""
    run, store, porter, blessed = _compiled_with_snippet(tmp_path)
    assert run_cli("executor", "--script", run, "--step", "1").returncode == 0     # snapshot run.sh, clean
    porter.write_text(porter.read_text() + "# post-bless mutation\n")              # mutate the PORTER, not run.sh
    r = run_cli("executor", "--script", run, "--step", "1")
    assert r.returncode == 8 and "SNIPPET" in r.stdout and "REFUSED" in r.stdout
    runs = ledger(store)["runs"]
    ev = [x for x in runs if x.get("event") == "snippet_refused"]
    assert len(ev) == 1 and ev[0]["step"] == "1" and ev[0]["tool"] == "tool"
    assert ev[0]["expected"] == blessed and ev[0]["found"] != blessed
    assert len(ev[0]["expected"]) == 64 and len(ev[0]["found"]) == 64
    assert runs[-1]["event"] == "snippet_refused"                                  # the step did NOT run after refusal


def test_snippet_refused_is_evidence_not_corruption(tmp_path):
    """A recorded snippet_refused is a PASS to cws-ledgercheck/verify (meta-rule M4) — the redemption path."""
    import importlib.util
    run, store, porter, _ = _compiled_with_snippet(tmp_path)
    run_cli("executor", "--script", run, "--step", "1")
    porter.write_text(porter.read_text() + "# mutated\n")
    run_cli("executor", "--script", run, "--step", "1")
    spec = importlib.util.spec_from_file_location(
        "lv", "skillChip/cws-ledgercheck/perks/verify/src/cws_ledgerverify.py")
    lv = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(lv)
    _records, bad, mode = lv.verify(json.loads((store / "run-ledger.json").read_text()))
    assert mode == "structural" and bad == []
