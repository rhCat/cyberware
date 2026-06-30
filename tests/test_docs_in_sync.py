"""The published docs must not drift from the live chip roster.

This turns the doc-drift recurrence class — skills shipped but never cataloged, and pinned
counts left stale — into a CI gate. (Several skills sat uncataloged for sessions before this
existed; adding cws-deploy is what surfaced it.) A skill add/remove now MUST update the docs
or codeqc goes red.
"""
import json
import os

from infra import registry
from infra.tool import skill_index as si

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def _read(rel):
    with open(os.path.join(ROOT, rel), encoding="utf-8") as f:
        return f.read()


def _perk_count():
    total = 0
    for s in si.all_skills():
        with open(os.path.join(registry.skill_dir(s), "perks.json"), encoding="utf-8") as f:
            total += len(json.load(f)["perks"])
    return total


def test_skills_catalog_lists_every_chip_skill():
    """docs/skills.md must name every skill the chip actually serves. The human catalog names skills by their
    bare LEAF (a reader sees `fs`, and govd's canonicalize shim resolves a unique bare claim to its namespace);
    the `ns:` prefix is a routing detail, surfaced only where a leaf is shared across namespaces."""
    doc = _read("docs/skills.md")
    missing = [s for s in si.all_skills() if (registry.parse_skill_id(s)[1] or s) not in doc]
    assert not missing, f"docs/skills.md is missing chip skills: {missing}"


def test_doc_skill_count_matches_the_chip():
    """The pinned skill counts in docs/skills.md and README.md must equal the chip roster size."""
    n = len(si.all_skills())
    assert f"**{n} skills**" in _read("docs/skills.md"), f"docs/skills.md skill count != {n}"
    assert f"the catalog ({n} skills)" in _read("README.md"), f"README catalog count != {n}"


def test_readme_perk_count_is_honest():
    """README's 'every one of the N perks (across M skills)' claim must be the real tally."""
    perks, skills = _perk_count(), len(si.all_skills())
    assert f"{perks} perks (across {skills} skills)" in _read("README.md"), (
        f"README perk/skill claim != {perks} perks across {skills} skills"
    )
