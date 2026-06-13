"""Adversarial negatives for the buildable-now validator skills.

The in-skill self-tests prove the happy path; these central tests prove the DETECTORS flag *corruption*
and *discriminate* — the property a validator is actually for. A green self-test that only ever sees good
input is the exact false confidence the plan warns about (tool-skills §3, cws-mutate's "self-evident"
residue), so each detector here is driven against input that MUST make it fail.
"""
import importlib.util
import json
import os
import shutil
import subprocess
import sys
import tempfile

from infra import registry

CHIP = registry.SKILLCHIP
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def _core(skill, perk, mod):
    return os.path.join(CHIP, skill, "perks", perk, "src", f"{mod}.py")


def _load(skill, perk, mod):
    """Import a perk's core directly from its source file (the cores are plain modules)."""
    spec = importlib.util.spec_from_file_location(f"{skill}_{mod}", _core(skill, perk, mod))
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


def _drive(skill, perk, mod, vars_, out_name):
    """Run a perk's core through a real subprocess (env-driven, like the executor does) and return
    (returncode, report_dict). Used for the cores that write files / import infra."""
    store = tempfile.mkdtemp(prefix=f"cwsneg-{skill}-")
    env = {**os.environ, "RECORD_STORE": store, "CYBERWARE_ROOT": ROOT, **vars_}
    p = subprocess.run([sys.executable, _core(skill, perk, mod)], env=env,
                       capture_output=True, text=True, cwd=ROOT)
    report = None
    op = os.path.join(store, out_name)
    if os.path.isfile(op):
        report = json.load(open(op))
    shutil.rmtree(store, ignore_errors=True)
    return p.returncode, report


# ── cws-ledgercheck ──────────────────────────────────────────────────────────────────────────────

def test_ledgercheck_accepts_a_sound_chain_and_flags_an_ordering_gap():
    lv = _load("cws-ledgercheck", "verify", "cws_ledgerverify")
    good = {"script": "run.sh", "runs": [
        {"ts": "t", "step": "1", "status": "ok", "exit": 0, "stdout_sha": "a"},
        {"ts": "t", "step": "2", "status": "ok", "exit": 0, "stdout_sha": "b"}]}
    assert lv.verify(good)[1] == []
    holed = {"script": "run.sh", "runs": [                       # step 2 never recorded ok — an out-of-band run
        {"ts": "t", "step": "1", "status": "ok", "exit": 0, "stdout_sha": "a"},
        {"ts": "t", "step": "3", "status": "ok", "exit": 0, "stdout_sha": "c"}]}
    bad = lv.verify(holed)[1]
    assert bad and any("gap" in b for b in bad)


def test_ledgercheck_flags_a_step_missing_its_provenance_hash():
    lv = _load("cws-ledgercheck", "verify", "cws_ledgerverify")
    miss = {"script": "run.sh", "runs": [{"ts": "t", "step": "1", "status": "ok", "exit": 0}]}
    bad = lv.verify(miss)[1]
    assert bad and any("stdout_sha" in b for b in bad)


def test_ledgercheck_flags_a_sub_one_step_number():
    lv = _load("cws-ledgercheck", "verify", "cws_ledgerverify")
    zero = {"script": "run.sh", "runs": [{"ts": "t", "step": "0", "status": "ok", "exit": 0, "stdout_sha": "a"}]}
    bad = lv.verify(zero)[1]
    assert bad and any("below 1" in b for b in bad)


def test_ledgercheck_accepts_recorded_refusal_events_as_evidence():
    lv = _load("cws-ledgercheck", "verify", "cws_ledgerverify")
    refused = {"script": "run.sh", "runs": [
        {"ts": "t", "event": "oversight_refused", "rules": ["pipe_to_shell"], "sha": "x"}]}
    assert lv.verify(refused)[1] == []                          # a recorded refusal is a pass (meta-rule M4)
    unknown = {"script": "run.sh", "runs": [{"ts": "t", "event": "mystery"}]}
    assert lv.verify(unknown)[1]


# ── cws-modelcheck ───────────────────────────────────────────────────────────────────────────────

def test_modelcheck_accepts_a_sound_blueprint_and_flags_a_deadlock():
    ck = _load("cws-modelcheck", "check", "cws_check")
    good = {"entry_state": "a", "states": {"a": {}, "z": {}}, "terminal_states": {"z": {}},
            "transitions": [{"from": "a", "to": "z"}]}
    assert ck.check_blueprint(good)["status"] == "ok"
    deadlock = {"entry_state": "a", "states": {"a": {}, "stuck": {}}, "terminal_states": {},
                "transitions": [{"from": "a", "to": "stuck"}]}
    cert = ck.check_blueprint(deadlock)
    assert cert["status"] == "fail" and cert["structural"]


def test_modelcheck_corpus_fixtures_each_trip_exactly_one_defect_class():
    """MC-1 backstop: each corpus fixture must fire its OWN class and no other — so deleting any one of
    the three structural detectors makes a specific fixture slip (the corpus genuinely guards all three)."""
    from infra.govern import composer
    cdir = os.path.join(CHIP, "cws-modelcheck", "perks", "corpus", "test", "fixture", "corpus")
    expected = {
        "deadlock.blueprint.json": "deadlock: non-terminal state",
        "unreachable.blueprint.json": "unreachable:",
        "no-terminal.blueprint.json": "no terminal state reachable",
    }
    others = list(expected.values())
    for fn, want in expected.items():
        issues = composer.structural(json.load(open(os.path.join(cdir, fn))))
        joined = " || ".join(issues)
        assert want in joined, f"{fn}: expected {want!r} in {issues}"
        for other in others:
            if other != want:
                assert other not in joined, f"{fn} also tripped {other!r} — not class-isolated: {issues}"


# ── cws-mutate ───────────────────────────────────────────────────────────────────────────────────

def test_mutate_generates_the_operator_flips_it_relies_on():
    mut = _load("cws-mutate", "mutate", "cws_mutate")
    ids = [mid for mid, _ in mut.mutants("    if a != b:\n        return True\n")]
    assert any(i.startswith("!=->==") for i in ids)
    assert any(i.startswith("True->False") for i in ids)


def test_mutate_reports_a_survivor_when_the_slice_does_not_pin_a_branch(tmp_path):
    """MUT-1: the kill/score PIPELINE (not just the generator) must discriminate. A weak slice that tests
    only the positive branch leaves a known mutant alive — the harness must report it, score < 1, exit !=0.
    A gutted core that hardcodes score 1.0 / survived [] fails this test."""
    proj = tmp_path / "proj"
    proj.mkdir()
    (proj / "gate.py").write_text(
        "def authorize(plan_sha, expected):\n"
        "    if plan_sha != expected:\n"
        "        return False\n"
        "    return True\n")
    (proj / "weak_check.py").write_text(                        # only ever checks the equal case
        "import sys\n"
        "from gate import authorize\n"
        "sys.exit(0 if authorize('abc', 'abc') is True else 1)\n")
    rc, report = _drive("cws-mutate", "mutate", "cws_mutate",
                        {"PROJECT_DIR": str(proj), "TARGET": "gate.py",
                         "TEST_CMD": "python3 weak_check.py", "THRESHOLD": "0.90"},
                        "mutate.json")
    assert rc != 0, "weak slice must drive a sub-threshold score"
    assert report and report["mutants"] > 0
    assert report["mutation_score"] < 1.0
    assert report["survived"], "the unpinned branch must leave a surviving mutant"
    assert any(s.startswith("False->True") for s in report["survived"])


# ── cws-conform ──────────────────────────────────────────────────────────────────────────────────

def test_conform_repin_flags_pre_existing_drift(tmp_path):
    """CONFORM-1/3: repin's signal must be falsifiable. Take the committed fixture chip, corrupt a tracked
    file, and re-pin: the committed index no longer matches, so pre_drift must name the skill, status must
    be 'drift', exit nonzero. A core that re-pins-then-verifies-itself (the tautology) would pass green."""
    src = os.path.join(CHIP, "cws-conform", "perks", "repin", "test", "fixture", "chip")
    chip = tmp_path / "chip"
    shutil.copytree(src, chip)
    # corrupt a tracked file WITHOUT re-pinning — the committed index.json now disagrees with disk
    md = chip / "demoskill" / "SKILL.md"
    md.write_text(md.read_text() + "\n<!-- drift -->\n")
    rc, report = _drive("cws-conform", "repin", "cws_repin", {"TARGET_CHIP": str(chip)}, "repin.json")
    assert rc != 0, "stale committed pins must exit nonzero"
    assert report and report["status"] == "drift"
    assert report["drift_count"] >= 1
    assert any(d["skill"] == "demoskill" for d in report["pre_drift"])


# ── cws-observe ──────────────────────────────────────────────────────────────────────────────────

def _run(skill, perk, mod, vars_, store):
    """Run a perk core to a persistent store (so the test can inspect the files it wrote)."""
    env = {**os.environ, "RECORD_STORE": str(store), "CYBERWARE_ROOT": ROOT, **vars_}
    return subprocess.run([sys.executable, _core(skill, perk, mod)], env=env,
                          capture_output=True, text=True, cwd=ROOT).returncode


def _mini_swarm(d, tasks, ledger_entries=None):
    """tasks = [(task_id, validated_by, depends_on)]; optional done-ledger entries."""
    d.mkdir(parents=True, exist_ok=True)
    for tid, vby, deps in tasks:
        (d / f"{tid}.json").write_text(json.dumps({"task_id": tid, "validated_by": vby, "depends_on": deps}))
    (d / "_swarm_manifest.json").write_text(json.dumps({"milestones": []}))
    if ledger_entries is not None:
        (d / "done-ledger.json").write_text(json.dumps({"chain": "done-ledger", "entries": ledger_entries}))


def test_observe_status_flags_a_broken_done_ledger_chain(tmp_path):
    sw = tmp_path / "swarm"
    tampered = {"seq": 1, "ts": "t", "task_id": "P0-T01", "validator": "cws-conform",
                "verdict": "pass", "evidence_sha": "x", "prev": "deadbeef"}   # prev != genesis
    _mini_swarm(sw, [("P0-T01", "cws-conform", [])], ledger_entries=[tampered])
    store = tmp_path / "out"
    rc = _run("cws-observe", "status", "cws_observe_status", {"SWARM_DIR": str(sw)}, store)
    rep = json.load(open(store / "observe.json"))
    assert rep["done_ledger_chain"] == "broken" and rc != 0


def test_observe_status_blocks_a_task_whose_dep_is_not_redeemed(tmp_path):
    sw = tmp_path / "swarm"
    _mini_swarm(sw, [("P0-T01", "cws-conform", []), ("P0-T02", "cws-modelcheck", ["P0-T01"])], ledger_entries=[])
    store = tmp_path / "out"
    rc = _run("cws-observe", "status", "cws_observe_status", {"SWARM_DIR": str(sw)}, store)
    rep = json.load(open(store / "observe.json"))
    assert rc == 0
    assert rep["by_task"]["P0-T01"] == "ready"            # validator built, no deps
    assert rep["by_task"]["P0-T02"] == "blocked:deps"     # its dep is not redeemed


def test_observe_redeem_refuses_failing_evidence(tmp_path):
    sw = tmp_path / "swarm"; _mini_swarm(sw, [("P0-T17", "cws-conform", [])])
    ev = tmp_path / "ev"; ev.mkdir()
    (ev / "run-ledger.json").write_text(json.dumps(
        {"script": "run.sh", "runs": [{"ts": "t", "step": "1", "status": "error", "exit": 1}]}))
    store, dl = tmp_path / "out", tmp_path / "done.json"
    rc = _run("cws-observe", "redeem", "cws_observe_redeem",
              {"SWARM_DIR": str(sw), "TASK_ID": "P0-T17", "RUN_LEDGER": str(ev / "run-ledger.json"),
               "DONE_LEDGER": str(dl)}, store)
    rep = json.load(open(store / "redeem.json"))
    assert rc != 0 and rep["verdict"] == "refused"
    assert not dl.exists(), "a refused redemption must not write a done-ledger entry"


def test_observe_redeem_refuses_evidence_from_the_wrong_validator(tmp_path):
    sw = tmp_path / "swarm"; _mini_swarm(sw, [("P0-T17", "cws-conform", [])])
    ev = tmp_path / "ev"; ev.mkdir()
    (ev / "run-ledger.json").write_text(json.dumps(
        {"script": "run.sh", "runs": [{"ts": "t", "step": "1", "status": "ok", "exit": 0, "stdout_sha": "a"}]}))
    (ev / "task-ledger.json").write_text(json.dumps({"skill": "cws-modelcheck", "perk": "check"}))
    store, dl = tmp_path / "out", tmp_path / "done.json"
    rc = _run("cws-observe", "redeem", "cws_observe_redeem",
              {"SWARM_DIR": str(sw), "TASK_ID": "P0-T17", "RUN_LEDGER": str(ev / "run-ledger.json"),
               "DONE_LEDGER": str(dl)}, store)
    rep = json.load(open(store / "redeem.json"))
    assert rc != 0 and rep["verdict"] == "refused" and "cws-modelcheck" in rep["reason"]


def test_observe_redeem_appends_a_genesis_chained_entry_and_is_idempotent(tmp_path):
    sw = tmp_path / "swarm"; _mini_swarm(sw, [("P0-T17", "cws-conform", [])])
    ev = tmp_path / "ev"; ev.mkdir()
    (ev / "run-ledger.json").write_text(json.dumps(
        {"script": "run.sh", "runs": [{"ts": "t", "step": "1", "status": "ok", "exit": 0, "stdout_sha": "a"}]}))
    (ev / "task-ledger.json").write_text(json.dumps({"skill": "cws-conform", "perk": "repin"}))
    store, dl = tmp_path / "out", tmp_path / "done.json"
    v = {"SWARM_DIR": str(sw), "TASK_ID": "P0-T17", "RUN_LEDGER": str(ev / "run-ledger.json"), "DONE_LEDGER": str(dl)}
    assert _run("cws-observe", "redeem", "cws_observe_redeem", v, store) == 0
    led = json.load(open(dl))
    assert len(led["entries"]) == 1 and led["entries"][0]["prev"] == "0" * 64
    assert _run("cws-observe", "redeem", "cws_observe_redeem", v, store) == 0   # re-run
    assert len(json.load(open(dl))["entries"]) == 1, "redeem must be idempotent per task"
