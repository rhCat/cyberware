"""In-skill self-tests — every perk's OWN `test/case.json`, run through the governed channel.

The proof lives WITH the skill: `skills/<skill>/perks/<perk>/test/case.json` (+ a `fixture/` dir),
pinned in the skill's `index.json`. This module is only the discovery harness — it finds every case and
runs it via `infra.tool.skilltest` (compile → executor → assert). It replaces the hand-written central
`test_skill_execution.py`: a skill now carries its own mechanically-run proof, not a verbal description.
"""
import pytest

from infra.tool import skill_index, skilltest

CASES = skilltest.all_cases()
IDS = [f"{s}/{p}" for s, p in CASES]


def test_every_skill_ships_a_self_test():
    """The invariant: every skill in the registry proves itself — at least one perk with a test/case.json.
    Walks the namespaced load set (all_skills), not a flat dir scan: under the source-grouped chip the top
    level holds namespace dirs (cws/, general/), so an os.listdir for perks.json would vacuously pass."""
    skills = set(skill_index.all_skills(skilltest.SKILLS))
    tested = {s for s, _ in CASES}
    missing = sorted(skills - tested)
    assert not missing, f"skills with no in-skill self-test: {missing}"


@pytest.mark.parametrize("sk,pk", CASES, ids=IDS)
def test_perk_self_test(sk, pk):
    status, detail = skilltest.run(sk, pk)
    if status == "skip":
        pytest.skip(detail)
    assert status == "pass", f"{sk}/{pk} self-test failed: {detail}"
