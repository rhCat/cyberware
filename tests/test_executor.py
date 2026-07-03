"""Integration: executor.py — THE governed channel. Tamper, in-channel oversight, upstream, provenance.

These pin the governance contract: every exit code below is a refusal the framework promises
(4=tamper, 5=upstream, 6=timeout, 7=oversight, 8=snippet drift).
"""
import hashlib
import json
import os

from conftest import compiler_shaped_script, run_cli
from infra import registry


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


def test_upstream_satisfied_allows_next_step(tmp_path):
    """The complement of the block: once step 1 is RECORDED run-ok, step 2 is allowed. Pins that the ran-set
    is built from status=='ok' records (a successfully-run upstream UNblocks the next step)."""
    store = tmp_path / "out"
    s = compiler_shaped_script(tmp_path / "run.sh", store, ['echo a', 'echo b'])
    assert run_cli("executor", "--script", s, "--step", "1").returncode == 0
    r = run_cli("executor", "--script", s, "--step", "2")   # upstream (1) ran ok -> allowed
    assert r.returncode == 0
    assert {x["step"] for x in ledger(store)["runs"] if x.get("status") == "ok"} == {"1", "2"}


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
    # P1-T06: the executor derives the step→tool map from the perk's manifesto sequence (the blessed plan),
    # not the script's --list, and AUTHENTICATES the manifesto against its blessed sha — so a faithful
    # compiled-script mock ships the manifesto AND blesses its sha in index.json (as a real index does).
    mbody = json.dumps({"sequence": ["tool"]}).encode()
    (tmp_path / "chip" / "sk" / "perks" / "pk" / "manifesto.json").write_bytes(mbody)
    (tmp_path / "chip" / "sk" / "index.json").write_text(json.dumps({"files": {
        "perks/pk/src/tool.sh": blessed,
        "perks/pk/manifesto.json": hashlib.sha256(mbody).hexdigest()}}))
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


def test_present_but_unblessed_porter_fails_closed(tmp_path):
    """The fail-open the review found: a real perk whose porter EXISTS and is sourced, but whose authenticity
    index no longer blesses it (a corrupt/emptied index — _blessed_snippets returns {}), must be REFUSED at
    that step, NOT run with the per-step re-hash silently skipped. Keep the manifesto blessed so the plan still
    declares the step; drop only the porter's src digest."""
    run, store, _porter, _blessed = _compiled_with_snippet(tmp_path)
    idx = tmp_path / "chip" / "sk" / "index.json"
    files = json.loads(idx.read_text())["files"]
    idx.write_text(json.dumps({"files": {"perks/pk/manifesto.json": files["perks/pk/manifesto.json"]}}))
    r = run_cli("executor", "--script", run, "--step", "1")
    assert r.returncode == 8 and "SNIPPET" in r.stdout and "UNBLESSED" in r.stdout
    ev = [x for x in ledger(store)["runs"] if x.get("event") == "snippet_refused"]
    assert len(ev) == 1 and ev[0]["step"] == "1" and ev[0]["expected"] is None    # present porter, no blessing


def test_snippet_refused_is_evidence_not_corruption(tmp_path):
    """A recorded snippet_refused is a PASS to cws-ledgercheck/verify (meta-rule M4) — the redemption path."""
    import importlib.util
    run, store, porter, _ = _compiled_with_snippet(tmp_path)
    run_cli("executor", "--script", run, "--step", "1")
    porter.write_text(porter.read_text() + "# mutated\n")
    run_cli("executor", "--script", run, "--step", "1")
    spec = importlib.util.spec_from_file_location(
        "lv", os.path.join(registry.skill_dir("cws-ledgercheck"), "perks", "verify", "src", "cws_ledgerverify.py"))
    lv = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(lv)
    _records, bad, mode = lv.verify(json.loads((store / "run-ledger.json").read_text()))
    assert mode == "structural" and bad == []


def _compiled_with_snippets(tmp_path, tools):
    """N-step variant of _compiled_with_snippet: one porter per tool, each blessed in index.json, with a
    faithful manifesto sequence. Returns (run.sh, store, [porter_paths], [blessed_digests])."""
    src = tmp_path / "chip" / "sk" / "perks" / "pk" / "src"
    src.mkdir(parents=True)
    porters, blessed = [], {}
    for t in tools:
        p = src / f"{t}.sh"
        p.write_text("#!/usr/bin/env bash\necho ok\n")
        porters.append(p)
        blessed[f"perks/pk/src/{t}.sh"] = hashlib.sha256(p.read_bytes()).hexdigest()
    mbody = json.dumps({"sequence": list(tools)}).encode()
    (tmp_path / "chip" / "sk" / "perks" / "pk" / "manifesto.json").write_bytes(mbody)
    blessed["perks/pk/manifesto.json"] = hashlib.sha256(mbody).hexdigest()   # the manifesto is blessed too
    (tmp_path / "chip" / "sk" / "index.json").write_text(json.dumps({"files": blessed}))
    store = tmp_path / "rec"
    run = tmp_path / "run.sh"
    lines = ["#!/usr/bin/env bash", "# COMPILED by cyberware · skill=sk perk=pk",
             f"SNIP={src}", f"RECORD_STORE={store}"]
    for i, t in enumerate(tools, 1):
        lines += [f"step{i}() {{   # {t}", f'  echo "[step {i}] {t}"', f'  bash "$SNIP/{t}.sh" || exit $?', "}"]
    listing = "\\n".join(f"{i}\\t{t}" for i, t in enumerate(tools, 1))
    lines += ['case "${1:-}" in', f'  --list) printf "{listing}\\n" ;;',
              '  --step) shift; "step${1:?step number}" ;;',
              '  --all) ' + " && ".join(f"step{i}" for i in range(1, len(tools) + 1)) + " ;;",
              '  *) echo usage >&2; exit 2 ;;', "esac"]
    run.write_text("\n".join(lines) + "\n")
    return run, store, porters, [blessed[f"perks/pk/src/{t}.sh"] for t in tools]


def test_refused_step_does_not_satisfy_a_downstream_upstream_requirement(tmp_path):
    """A snippet-refused step must NOT count as 'run' for the next step's upstream gate — the ran-set is
    status=='ok' records only. (Without the status check, a refused step still carries a 'step' key, so it
    would falsely UNblock its successor.) Pins the 'and' in the ran-set comprehension."""
    run, store, porters, _ = _compiled_with_snippets(tmp_path, ["tool1", "tool2"])
    porters[0].write_text(porters[0].read_text() + "# drift\n")     # step1 porter no longer matches blessed
    assert run_cli("executor", "--script", run, "--step", "1").returncode == 8   # snippet_refused, NOT ok
    r = run_cli("executor", "--script", run, "--step", "2")
    assert r.returncode == 5 and "UPSTREAM" in r.stdout             # step1 refused -> step2 still blocked


def test_manifest_swap_cannot_decouple_step_tool_from_snippet_verify(tmp_path):
    """SECURITY (the P1-T06 blocker): mutating a porter AND renaming it in the sibling manifesto (so the
    step→tool map would name a tool NOT in the blessed set, making snippet-verify silently no-op) must NOT
    run the tampered porter. The executor authenticates the manifesto against its blessed index.json sha, so
    the swap fails the plan check and the step is refused — the tampered porter never executes."""
    run, store, porters, _ = _compiled_with_snippets(tmp_path, ["tool1"])
    assert run_cli("executor", "--script", run, "--step", "1").returncode == 0   # clean blessing run
    porters[0].write_text(porters[0].read_text() + "\necho INJECTED-VIA-MANIFEST-DECOUPLE\n")
    mpath = tmp_path / "chip" / "sk" / "perks" / "pk" / "manifesto.json"
    mpath.write_text(json.dumps({"sequence": ["renamed_so_snippet_check_misses"]}))   # post-bless swap
    r = run_cli("executor", "--script", run, "--step", "1")
    assert r.returncode != 0                                         # refused, not run
    assert "INJECTED-VIA-MANIFEST-DECOUPLE" not in r.stdout          # the tampered porter never executed


def test_missing_manifesto_fails_closed_for_all_and_step(tmp_path):
    """The fail-closed contract end-to-end: a compiled script whose blessed plan (manifesto) is absent
    declares no steps — BOTH --step and --all refuse (exit 2), never a silent exit-0 'done (governed)'."""
    run, store, _porters, _ = _compiled_with_snippets(tmp_path, ["tool1"])
    (tmp_path / "chip" / "sk" / "perks" / "pk" / "manifesto.json").unlink()      # delete the blessed plan
    assert run_cli("executor", "--script", run, "--step", "1").returncode == 2
    r = run_cli("executor", "--script", run, "--all")
    assert r.returncode == 2 and "no declared steps" in r.stdout     # NOT a silent successful full run
