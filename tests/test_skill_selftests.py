"""In-skill self-tests — every perk's OWN `test/case.json`, run through the governed channel.

The proof lives WITH the skill: `skills/<skill>/perks/<perk>/test/case.json` (+ a `fixture/` dir),
pinned in the skill's `index.json`. This module is only the discovery harness — it finds every case and
runs it via `infra.tool.skilltest` (compile → executor → assert). It replaces the hand-written central
`test_skill_execution.py`: a skill now carries its own mechanically-run proof, not a verbal description.
"""
import os

import pytest

from infra.tool import skilltest

CASES = skilltest.all_cases()
IDS = [f"{s}/{p}" for s, p in CASES]


def test_every_skill_ships_a_self_test():
    """The invariant: every skill in the registry proves itself — at least one perk with a test/case.json."""
    skills = sorted(d for d in os.listdir(skilltest.SKILLS)
                    if os.path.isfile(os.path.join(skilltest.SKILLS, d, "perks.json")))
    tested = {s for s, _ in CASES}
    missing = sorted(set(skills) - tested)
    assert not missing, f"skills with no in-skill self-test: {missing}"


@pytest.mark.parametrize("sk,pk", CASES, ids=IDS)
def test_perk_self_test(sk, pk):
    status, detail = skilltest.run(sk, pk)
    if status == "skip":
        pytest.skip(detail)
    assert status == "pass", f"{sk}/{pk} self-test failed: {detail}"
