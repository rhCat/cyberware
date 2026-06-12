"""Per-perk + per-skill CONTRACT tests (no execution — runs everywhere, fast).

Every perk in the registry must compile to a clean, well-formed script; every skill must be internally
consistent (perks.json ↔ dirs ↔ manifesto ↔ SKILL.md) and carry the real oversight invariant.
"""
import json
import os

from infra.govern import compiler
from infra.govern import oversight
import pytest
from conftest import ROOT, all_perks

PERKS = all_perks()
PERK_IDS = [f"{s}/{p}" for s, p in PERKS]
SKILLS = sorted({s for s, _ in PERKS})


def _example_vars(sk, pk):
    meta = json.load(open(f"{ROOT}/skills/{sk}/perks/{pk}/metadata.json"))
    ex = dict(meta.get("minimal_example", {}).get("vars", {}))
    contract = json.load(open(f"{ROOT}/skills/{sk}/perks/{pk}/src/contracts.json"))
    for k, spec in contract.get("inputs", {}).items():
        if spec.get("required") and k not in ex:
            ex[k] = "/tmp/placeholder"
    return ex


def test_registry_is_nonempty():
    assert len(PERKS) >= 27


@pytest.mark.parametrize("sk,pk", PERKS, ids=PERK_IDS)
def test_perk_compiles_to_a_clean_script(sk, pk):
    L = {"skill": sk, "perk": pk, "record_store": "/tmp/rs", "vars": _example_vars(sk, pk)}
    text, seq = compiler.build_script(L)
    man = json.load(open(f"{ROOT}/skills/{sk}/perks/{pk}/manifesto.json"))
    assert seq == man["sequence"], f"{sk}/{pk}: compiled sequence != manifesto"
    for i in range(1, len(seq) + 1):
        assert f"step{i}()" in text
    assert "--all)" in text and "set -uo pipefail" in text
    violations, _ = oversight.scan(text)
    assert violations == [], f"{sk}/{pk} trips oversight: {[r['id'] for r in violations]}"


@pytest.mark.parametrize("sk,pk", PERKS, ids=PERK_IDS)
def test_perk_declares_an_output_check(sk, pk):
    c = json.load(open(f"{ROOT}/skills/{sk}/perks/{pk}/src/contracts.json"))
    assert c.get("checks", {}).get("output_exists"), f"{sk}/{pk}: no output_exists"


@pytest.mark.parametrize("sk", SKILLS)
def test_skill_structure_is_consistent(sk):
    d = f"{ROOT}/skills/{sk}"
    assert os.path.isfile(f"{d}/SKILL.md"), f"{sk}: missing SKILL.md"
    smd = open(f"{d}/SKILL.md").read()
    for p in json.load(open(f"{d}/perks.json"))["perks"]:
        pid = p["id"]
        assert os.path.isdir(f"{d}/perks/{pid}"), f"{sk}: perks.json lists {pid} but no dir"
        man = json.load(open(f"{d}/perks/{pid}/manifesto.json"))
        for tool in man["sequence"]:
            assert os.path.isfile(f"{d}/perks/{pid}/src/{tool}.sh"), f"{sk}/{pid}: no {tool}.sh"
        assert pid in smd, f"{sk}: SKILL.md never mentions perk {pid}"


@pytest.mark.parametrize("sk", SKILLS)
def test_skill_blueprint_oversight_invariant_is_real(sk):
    """Across the whole registry, the danger gate must be a checked property, not TRUE."""
    bp = json.load(open(f"{ROOT}/skills/{sk}/blueprint.json"))
    inv = next(i for i in bp["safety_invariants"] if i["name"] == "oversight_clears_script")
    assert inv["expression"] != "TRUE" and "oversight_cleared" in inv["expression"]
