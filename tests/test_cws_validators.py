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


def _v2_chain():
    from infra.cwp import ledger as L
    chain = [L.genesis("run-A", "plan-1")]
    L.append(chain, {"task_id": "T1", "verdict": "pass", "evidence_sha": "a"})
    L.append(chain, {"task_id": "T2", "verdict": "pass", "evidence_sha": "b"})
    return chain


def test_ledgercheck_recomputes_a_v2_chain_and_names_tamper():
    """SV-2 (P1-T01): the cryptographic prev-chain is RE-verified, not trusted — a mutated record breaks
    the recompute and the first record that fails to chain is named."""
    import copy
    lv = _load("cws-ledgercheck", "verify", "cws_ledgerverify")
    chain = _v2_chain()
    assert lv.verify(chain)[1] == []                             # sound chain — list form
    assert lv.verify({"schema": 2, "entries": chain})[1] == []  # sound chain — {entries} object form
    tampered = copy.deepcopy(chain)
    tampered[1]["evidence_sha"] = "MUTATED"                      # flip a field -> downstream prev no longer matches
    bad = lv.verify(tampered)[1]
    assert bad and "T2" in bad[0]


def test_ledgercheck_nontransplant_needs_an_out_of_band_origin():
    """The honest boundary: the SAME records re-linked under a different genesis are internally consistent,
    so non-transplant can only be certified against an expected origin sourced OUT-OF-BAND."""
    from infra.cwp import ledger as L
    lv = _load("cws-ledgercheck", "verify", "cws_ledgerverify")
    forged = [L.genesis("run-EVIL", "plan-EVIL")]               # attacker re-stamps the work under a new origin
    L.append(forged, {"task_id": "T1", "verdict": "pass"})
    L.append(forged, {"task_id": "T2", "verdict": "pass"})
    assert lv.verify(forged)[1] == []                           # internally consistent -> passes without an anchor
    bad = lv.verify(forged, expect_run_id="run-REAL", expect_plan_sha="plan-REAL")[1]
    assert bad and "transplant" in bad[0]                       # pinned origin rejects the transplant


def test_ledgercheck_rejects_headless_empty_and_double_genesis():
    """A provenance chain must have exactly one leading genesis. A genesis-less ('decapitated') chain, an
    empty chain, or a second genesis mid-chain must all read broken — not 'ok'."""
    from infra.cwp import ledger as L
    lv = _load("cws-ledgercheck", "verify", "cws_ledgerverify")
    assert lv.verify([])[1]                                     # empty -> broken
    headless = [{"type": "step", "task_id": "evil", "seq": 0, "prev": L.ZERO}]
    L.append(headless, {"task_id": "evil2"})
    assert lv.verify(headless)[1] and "genesis" in lv.verify(headless)[1][0]
    dbl = _v2_chain()
    dbl.append(L.genesis("run-X", "plan-X"))                    # a second genesis appended (its prev is ZERO)
    assert lv.verify(dbl)[1]


def test_ledgercheck_flags_a_deleted_middle_record_via_seq_gap():
    """Deleting a genuine record and re-linking its successor leaves a non-contiguous seq (0,1,3); the
    cryptographic check must catch the gap, not only the structural sibling."""
    from infra.cwp import ledger as L
    import copy
    lv = _load("cws-ledgercheck", "verify", "cws_ledgerverify")
    chain = [L.genesis("r", "p")]
    L.append(chain, {"task_id": "t1"})
    L.append(chain, {"task_id": "t2"})
    L.append(chain, {"task_id": "t3"})
    cut = copy.deepcopy(chain)
    del cut[2]                                                   # drop t2
    cut[2]["prev"] = L.link_digest(L.link_of(cut[1]), 2)        # repoint former t3 onto t1 (seqs now 0,1,3)
    bad = lv.verify(cut)[1]
    assert bad and "contiguous" in bad[0]


def test_ledgercheck_refuses_schema_downgrade_and_survives_bad_seq():
    """A chain can't pick its own (retired) digest: a schema-1 chain is refused without an explicit opt-in.
    A non-integer seq reads broken, never an uncaught crash."""
    from infra.cwp import ledger as L
    lv = _load("cws-ledgercheck", "verify", "cws_ledgerverify")
    legacy = {"schema": 1, "entries": [L.genesis("r", "p", schema=1)]}
    L.append(legacy["entries"], {"task_id": "x"}, schema=1)
    assert lv.verify(legacy)[1] and "legacy" in lv.verify(legacy)[1][0]          # refused by default
    assert lv.verify(legacy, allow_legacy=True)[1] == []                         # audited with opt-in
    bad_seq = _v2_chain()
    bad_seq[1]["seq"] = "two"                                                     # type confusion must not crash
    out = lv.verify(bad_seq)[1]
    assert out and ("seq" in out[0] or "prev" in out[0])


def test_ledgercheck_verifies_a_govd_provenance_ledger():
    """The recursive SV-2 act (P1-T09): verify must recognise the {decision, events} run-ledger a governed
    run writes — a sound record passes (a recorded refusal is still evidence); a malformed one is named."""
    lv = _load("cws-ledgercheck", "verify", "cws_ledgerverify")
    good = {"decision": "allow", "events": [
        {"type": "granted", "step": "1"},
        {"type": "step_result", "step": "1", "status": "ok", "exit": 0}]}
    recs, bad, mode = lv.verify(good)
    assert mode == "govd" and bad == [] and recs == 2
    refused = {"decision": "allow", "events": [{"type": "tamper_refused", "step": "1"}]}
    assert lv.verify(refused)[1] == []                          # a recorded refusal is evidence, not corruption
    malformed = {"decision": "allow", "events": [{"type": "step_result", "step": "1"}]}  # no status
    assert lv.verify(malformed)[1]                              # named broken
    assert lv.verify({"decision": "allow", "events": "nope"})[1]  # events not a list


def test_ledger_v2_writer_roundtrips_through_jsonl():
    """P1-T01 write path: genesis(run_id, plan_sha) + append produce a chain that survives a JSONL
    write/read round-trip and verifies; the genesis binds the origin."""
    from infra.cwp import ledger as L
    import tempfile
    chain = [L.genesis("run-Z", "plan-Z")]
    L.append(chain, {"task_id": "A", "verdict": "pass"})
    L.append(chain, {"task_id": "B", "verdict": "pass"})
    with tempfile.NamedTemporaryFile("w", suffix=".jsonl", delete=False) as f:
        path = f.name
    L.write_chain(path, chain)
    entries, schema = L.read_chain(path)
    assert schema == 2 and len(entries) == 3
    assert L.verify_chain(entries, schema)[0] is True
    assert entries[0]["run_id"] == "run-Z" and entries[0]["plan_sha"] == "plan-Z"
    os.remove(path)


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


def test_doclint_rejects_a_non_normative_or_off_topic_spec(tmp_path):
    """doclint must DISCRIMINATE: a doc that decides nothing (no RFC-2119 keyword) or omits a required
    topic fails. A core that always reports ok would pass the happy self-test but fail here."""
    core = _core("cws-conform", "doclint", "cws_doclint")

    def lint(text, store, **extra):
        spec = tmp_path / f"{store}.md"
        spec.write_text(text)
        sdir = tmp_path / store
        env = {**os.environ, "SPEC": str(spec), "RECORD_STORE": str(sdir), **extra}
        rc = subprocess.run([sys.executable, core], env=env, capture_output=True, text=True, cwd=ROOT).returncode
        return rc, json.load(open(sdir / "doclint.json"))

    rc, rep = lint("# Title\n\nThis says nothing binding.\n", "weak", MIN_NORMATIVE="1")
    assert rc != 0 and rep["status"] == "fail" and rep["normative_count"] == 0

    rc, rep = lint("# Title\n\nA grant MUST carry a key-id.\n", "offtopic", REQUIRE="rotation")
    assert rc != 0 and "rotation" in str(rep["missing_required"])


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


def test_observe_redeem_accepts_govd_provenance_ledger():
    """redeem must accept govd's own provenance ledger (events[] + decision) as evidence — so a redemption
    is backed by the dashboard-visible, value-free record, not just a local executor run-ledger."""
    rd = _load("cws-observe", "redeem", "cws_observe_redeem")
    ok = {"decision": "allow", "skill": "cws-conform",
          "events": [{"type": "granted", "step": "1"}, {"type": "step_result", "step": "1", "status": "ok"}]}
    assert rd.run_ledger_passed(ok)[0] is True
    assert rd.run_ledger_passed({**ok, "decision": "reject"})[0] is False
    err = {"decision": "allow", "skill": "cws-conform", "events": [{"type": "step_result", "step": "1", "status": "error"}]}
    assert rd.run_ledger_passed(err)[0] is False
    refused = {"decision": "allow", "skill": "cws-conform",
               "events": [{"type": "oversight_refused"}, {"type": "step_result", "step": "1", "status": "ok"}]}
    assert rd.run_ledger_passed(refused)[0] is False


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
    # decision-4: redemptions land on a canonical (major-2) chain that opens with a genesis record
    from infra.cwp import ledger
    assert led["schema"] == 2
    g, red = led["entries"]
    assert g["type"] == "genesis" and g["prev"] == "0" * 64
    assert red["task_id"] == "P0-T17" and red["verdict"] == "pass"
    assert red["prev"] == ledger.link_digest(ledger.link_of(g), 2)   # canonical-chained to the genesis
    assert _run("cws-observe", "redeem", "cws_observe_redeem", v, store) == 0   # re-run
    assert len(json.load(open(dl))["entries"]) == 2, "redeem must be idempotent per task"


def test_observe_status_reads_a_valid_v2_chain_across_majors(tmp_path):
    """status verifies frozen v1 (major 1) AND the canonical v2 chain (major 2) with a correct genesis
    cross-reference, counting redemptions from both (decision-4: verifiers support majors N and N-1)."""
    from infra.cwp import ledger
    sw = tmp_path / "swarm"
    v1e = {"seq": 1, "ts": "t", "task_id": "P0-T01", "validator": "cws-conform",
           "verdict": "pass", "evidence_sha": "x", "prev": "0" * 64}
    _mini_swarm(sw, [("P0-T01", "cws-conform", []), ("P0-T02", "cws-conform", [])], ledger_entries=[v1e])
    genesis = {"type": "genesis", "schema": 2, "supersedes": "done-ledger", "supersedes_schema": 1,
               "supersedes_head": ledger.head_of([v1e], 1), "supersedes_count": 1, "prev": "0" * 64}
    red = {"seq": 2, "ts": "t", "task_id": "P0-T02", "validator": "cws-conform", "verdict": "pass",
           "evidence_sha": "y", "prev": ledger.link_digest(ledger.link_of(genesis), 2)}
    (sw / "done-ledger-v2.json").write_text(json.dumps({"chain": "done-ledger-v2", "schema": 2, "entries": [genesis, red]}))
    store = tmp_path / "out"
    rc = _run("cws-observe", "status", "cws_observe_status", {"SWARM_DIR": str(sw)}, store)
    rep = json.load(open(store / "observe.json"))
    assert rc == 0 and rep["done_ledger_chain"] == "ok"
    assert rep["by_task"]["P0-T01"] == "redeemed" and rep["by_task"]["P0-T02"] == "redeemed"


def test_observe_status_breaks_when_v2_genesis_cross_ref_mismatches_v1(tmp_path):
    """decision-4 tamper-binding: the v2 genesis must cross-reference frozen v1's EXACT head; a wrong
    supersedes_head (v1 altered after v2 forked) MUST read as a broken chain."""
    from infra.cwp import ledger
    sw = tmp_path / "swarm"
    v1e = {"seq": 1, "ts": "t", "task_id": "P0-T01", "validator": "cws-conform",
           "verdict": "pass", "evidence_sha": "x", "prev": "0" * 64}
    _mini_swarm(sw, [("P0-T01", "cws-conform", []), ("P0-T02", "cws-conform", [])], ledger_entries=[v1e])
    genesis = {"type": "genesis", "schema": 2, "supersedes_head": "deadbeef", "prev": "0" * 64}   # wrong head
    red = {"seq": 2, "ts": "t", "task_id": "P0-T02", "validator": "cws-conform", "verdict": "pass",
           "evidence_sha": "y", "prev": ledger.link_digest(ledger.link_of(genesis), 2)}
    (sw / "done-ledger-v2.json").write_text(json.dumps({"chain": "done-ledger-v2", "schema": 2, "entries": [genesis, red]}))
    store = tmp_path / "out"
    rc = _run("cws-observe", "status", "cws_observe_status", {"SWARM_DIR": str(sw)}, store)
    rep = json.load(open(store / "observe.json"))
    assert rep["done_ledger_chain"] == "broken" and rc != 0


# ── cws-pm (composite operator: progress-report rendering robustness) ───────────────────────────────
import re  # noqa: E402


def _tables_wellformed(md):
    """Every markdown table data row must carry the same unescaped-pipe cell count as its header.
    Returns the malformed rows — the property the §3/§4/§5 cell-escaping must guarantee."""
    def cells(ln):
        return len(re.split(r"(?<!\\)\|", ln)) - 2          # cells between the outer pipes
    bad, hdr = [], None
    for i, ln in enumerate(md.splitlines()):
        s = ln.strip()
        if s.startswith("|") and s.endswith("|"):
            if set(s.replace("|", "").strip()) <= set("-: "):   # the |---|---| separator row
                continue
            if hdr is None:
                hdr = cells(s)
            elif cells(s) != hdr:
                bad.append((i, ln))
        else:
            hdr = None                                          # a blank/prose line ends the table
    return bad


def _pm_report(report, dag, redeemed, dry):
    return _load("cws-pm", "run", "cws_pm")._render_report(report, "", dag, redeemed, dry)


def _pm_counts(**kw):
    c = {"already_redeemed": 0, "redeemed": 0, "ran": 0, "blocked_deps": 0,
         "blocked_validator": 0, "failed": 0, "dry": 0}
    c.update(kw)
    return c


def test_pm_report_escapes_table_breaking_text_in_a_title():
    """A title with a pipe/backtick/newline (P4-T02 ships one: `on_fail: to|retry|compensate`) must not
    split its §3 row into extra cells — the live content-loss bug the report audit caught."""
    dag = {"P0-T01": {"task_id": "P0-T01", "depends_on": [],
                      "title": "Failure (on_fail: to|retry|compensate) `tick`\nand a newline"}}
    report = {"status": "ok", "dry_run": True, "total": 1, "redeemed_total": 0,
              "counts": _pm_counts(dry=1),
              "steps": [{"task_id": "P0-T01", "skill": "cws-conform", "perk": "x", "status": "dry"}]}
    assert _tables_wellformed(_pm_report(report, dag, set(), True)) == []


def test_pm_report_program_count_intersects_the_dag():
    """Off-DAG / stale done-ledger pass entries must NOT inflate the Program roll-up — parity with
    cws-observe/status's `redeemed &= set(tasks)` (otherwise the bar renders a nonsensical >100%)."""
    dag = {"P0-T01": {"task_id": "P0-T01", "depends_on": []},
           "P0-T02": {"task_id": "P0-T02", "depends_on": []}}
    report = {"status": "ok", "dry_run": True, "total": 0, "redeemed_total": 1,
              "counts": _pm_counts(), "steps": []}
    md = _pm_report(report, dag, {"P0-T01", "STALE-1", "STALE-2", "DEMO-9"}, True)   # 3 of 4 off-DAG
    assert "**Program:** 1 of 2 DAG tasks redeemed" in md
    assert "250%" not in md and "300%" not in md


def test_pm_report_live_failed_detail_stays_single_line():
    """An untrusted govd error carrying a newline/backtick must not break the §5 table or bullet."""
    report = {"status": "fail", "dry_run": False, "total": 1, "redeemed_total": 0,
              "counts": _pm_counts(failed=1),
              "steps": [{"task_id": "P0-T01", "skill": "cws-conform", "perk": "x", "status": "failed",
                         "run_id": "abc", "detail": "decision=reject\nreason `boom`"}]}
    md = _pm_report(report, {}, set(), False)
    assert _tables_wellformed(md) == []
    bullet = [ln for ln in md.splitlines() if ln.startswith("- ") and "failed**" in ln]
    assert bullet and "`boom`" not in bullet[0]             # the stray backtick was neutralized


def test_pm_report_discloses_steps_never_reached_on_early_halt():
    """STOP_ON_FAIL leaves steps < total; the report must surface the gap, not silently drop them."""
    report = {"status": "fail", "dry_run": False, "total": 5, "redeemed_total": 0,
              "counts": _pm_counts(ran=1, failed=1),
              "steps": [{"task_id": "P0-T01", "skill": "cws-conform", "perk": "x", "status": "ran", "run_id": "a"},
                        {"task_id": "P0-T02", "skill": "cws-conform", "perk": "x", "status": "failed",
                         "run_id": "b", "detail": "boom"}]}
    md = _pm_report(report, {}, set(), False)
    assert "3 of 5 steps were never reached" in md
