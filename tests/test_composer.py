"""Unit: composer.structural / emit_tla — the deadlock check (the safeguard must actually catch one)."""
import composer

GOOD = {
    "entry_state": "a",
    "states": {"a": {}, "b": {}, "done": {}},
    "terminal_states": {"done": {}},
    "transitions": [{"from": "a", "to": "b"}, {"from": "b", "to": "done"}],
}


def test_sound_blueprint_has_no_structural_issues():
    assert composer.structural(GOOD) == []


def test_catches_non_terminal_sink():
    bp = {**GOOD, "states": {"a": {}, "b": {}, "stuck": {}, "done": {}},
          "transitions": [{"from": "a", "to": "b"}, {"from": "b", "to": "done"},
                          {"from": "a", "to": "stuck"}]}
    issues = composer.structural(bp)
    assert any("deadlock" in i and "stuck" in i for i in issues)


def test_catches_unreachable_state():
    bp = {**GOOD, "states": {"a": {}, "b": {}, "orphan": {}, "done": {}}}
    issues = composer.structural(bp)
    assert any("unreachable" in i and "orphan" in i for i in issues)


def test_catches_no_terminal_reachable():
    bp = {"entry_state": "a", "states": {"a": {}, "b": {}}, "terminal_states": {"z": {}},
          "transitions": [{"from": "a", "to": "b"}, {"from": "b", "to": "a"}]}
    issues = composer.structural(bp)
    assert any("no terminal" in i.lower() for i in issues)


def test_emit_tla_has_spec_and_terminal_self_loop():
    tla = composer.emit_tla(GOOD, "task")
    assert "MODULE task" in tla and "Spec ==" in tla and "Init ==" in tla
    assert '(pc = "done" /\\ pc\' = "done")' in tla   # terminal self-loop, so TLC won't flag it


def test_real_skill_blueprints_are_all_sound():
    import glob
    import json
    for p in glob.glob(str(composer.ROOT) + "/skills/*/blueprint.json"):
        assert composer.structural(json.load(open(p))) == [], f"{p} has structural issues"
