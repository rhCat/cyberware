"""Unit: scaffold.blueprint + stubs — a freshly scaffolded skill must compose and carry the REAL invariant."""
import composer
import scaffold


def test_blueprint_is_the_standard_lifecycle():
    bp = scaffold.blueprint("demo", "Demo", "does a thing.")
    assert bp["entry_state"] == "ready"
    assert set(bp["states"]) == {"ready", "prepared", "verified", "executed"}
    assert bp["terminal_states"] == {"executed": {}}
    assert set(bp["gates"]) == {"g_prepared", "g_verified", "g_governed"}
    assert len(bp["transitions"]) == 3


def test_scaffolded_blueprint_composes_out_of_the_box():
    bp = scaffold.blueprint("demo", "Demo", "does a thing.")
    assert composer.structural(bp) == []


def test_oversight_invariant_is_real_not_TRUE():
    """Pins the P1 fix: the danger gate is asserted as a checked property, not a literal TRUE."""
    bp = scaffold.blueprint("demo", "Demo", "x.")
    inv = next(i for i in bp["safety_invariants"] if i["name"] == "oversight_clears_script")
    assert inv["expression"] != "TRUE"
    assert "oversight_cleared" in inv["expression"]


def test_stubs_are_nonempty_executable_shapes():
    assert scaffold.snippet_stub("t").startswith("#!/usr/bin/env bash")
    assert "json" in scaffold.py_stub("t").lower()
    assert "python3" in scaffold.porter_stub("t")
