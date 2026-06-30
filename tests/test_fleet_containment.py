"""Unit tests for the cws-fleet `deploy` containment core — the anti-rogue security logic, exercised
independently of docker. The core lives in the skillChip submodule; we load it by path so the security
decision is reviewable as a pure function (mirrors how principals.acl_allows is unit-tested apart from govd).

Subset is by CONTENT (skill_sha), not leaf name — the adversarial review showed a leaf-only check let a
mounted child carry a TROJANED same-leaf skill (different sha) past the gate. These tests pin the fix.
"""
from __future__ import annotations
import importlib.util
import json
import os

import pytest

_HERE = os.path.dirname(__file__)
_CORE = os.path.join(_HERE, "..", "skillChip", "cws", "cws-fleet", "perks", "deploy", "src", "fleet_deploy.py")
_DOWN = os.path.join(_HERE, "..", "skillChip", "cws", "cws-fleet", "perks", "down", "src", "fleet_down.py")

pytestmark = pytest.mark.skipif(not os.path.isfile(_CORE),
                                reason="skillChip submodule not checked out")


def _load(path, name):
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


fd = _load(_CORE, "fleet_deploy_core") if os.path.isfile(_CORE) else None
fdown = _load(_DOWN, "fleet_down_core") if os.path.isfile(_DOWN) else None


def _sk(*pairs):
    """Build a skills list [{leaf, sha}, ...] from (leaf, sha) pairs."""
    return [{"leaf": leaf, "sha": sha} for leaf, sha in pairs]


PARENT = _sk(("fs", "SHA_fs"), ("http", "SHA_http"), ("git_ops", "SHA_git"))   # the parent chip's catalog


# ── fleet_rank: named / numeric ('and so on') / unknown ──
def test_fleet_rank():
    assert fd.fleet_rank("mothership") == 1
    assert fd.fleet_rank("EDGE") == 2                    # case-insensitive
    assert fd.fleet_rank("subagent") == 3
    assert fd.fleet_rank("7") == 7 and fd.fleet_rank(7) == 7       # deeper ints verbatim
    assert fd.fleet_rank(None) is None
    assert fd.fleet_rank("garbage") is None
    assert fd.fleet_rank(0) is None and fd.fleet_rank(-2) is None
    assert fd.fleet_rank(True) is None                  # a bool is not a tier (int-subclass guard)


# ── check_containment: the fail-closed decision, full reason table (CONTENT-identity subset) ──
@pytest.mark.parametrize("parent_ft,child_ft,acl,child,ok,reason", [
    ("mothership", "subagent", {"fs"}, _sk(("fs", "SHA_fs")), True, None),
    ("edge", "subagent", {"fs", "http"}, _sk(("fs", "SHA_fs"), ("http", "SHA_http")), True, None),
    ("mothership", 9, {"fs"}, _sk(("fs", "SHA_fs")), True, None),                            # deeper int child
    ("mothership", "mothership", {"fs"}, _sk(("fs", "SHA_fs")), False, "fleet_tier_not_strictly_lower"),  # sideways
    ("edge", "mothership", {"fs"}, _sk(("fs", "SHA_fs")), False, "fleet_tier_not_strictly_lower"),        # upward
    ("subagent", "edge", {"fs"}, _sk(("fs", "SHA_fs")), False, "fleet_tier_not_strictly_lower"),          # upward
    ("garbage", "subagent", {"fs"}, _sk(("fs", "SHA_fs")), False, "fleet_tier_unknown"),
    ("mothership", None, {"fs"}, _sk(("fs", "SHA_fs")), False, "fleet_tier_unknown"),
    ("mothership", "subagent", {"fs", "s3"}, _sk(("fs", "SHA_fs")), False, "acl_not_subset"),             # acl beyond parent
    ("mothership", "subagent", {"fs"}, _sk(("fs", "SHA_fs"), ("s3", "SHA_s3")), False, "chip_not_subset"),  # child smuggles s3
    ("mothership", "subagent", {"http"}, _sk(("fs", "SHA_fs")), False, "acl_exceeds_chip"),               # acl not on child
    # THE BLOCKER: a TROJANED same-leaf skill (leaf 'fs' but a DIFFERENT skill_sha) must be rejected
    ("mothership", "subagent", {"fs"}, _sk(("fs", "TROJAN_sha")), False, "chip_not_subset"),
    # an empty child chip is degenerate -> rejected (a body must carry >=1 verbatim parent skill)
    ("mothership", "subagent", set(), [], False, "chip_not_subset"),
])
def test_check_containment(parent_ft, child_ft, acl, child, ok, reason):
    assert fd.check_containment(parent_ft, child_ft, acl, PARENT, child) == (ok, reason)


def test_trojaned_skill_with_no_sha_is_rejected():
    # a child skill missing a skill_sha entirely can never match a parent by content -> fail-closed
    assert fd.check_containment("mothership", "subagent", {"fs"}, PARENT,
                                [{"leaf": "fs", "sha": None}]) == (False, "chip_not_subset")


def test_empty_acl_is_a_vacuous_subset_and_allowed():
    # a body granted nothing is the minimal contained body — allowed when tiers descend + the chip is verbatim
    assert fd.check_containment("mothership", "subagent", set(), PARENT, _sk(("fs", "SHA_fs"))) == (True, None)


def test_tier_gate_precedes_subset_gates():
    assert fd.check_containment("subagent", "subagent", {"git_ops"}, PARENT,
                                _sk(("git_ops", "SHA_git"))) == (False, "fleet_tier_not_strictly_lower")


# ── _chip_skills: manifest read (id/leaf/sha), fail-closed on absence ──
def test_chip_skills_reads_id_leaf_sha(tmp_path):
    (tmp_path / "index.json").write_text(json.dumps({"skills": [
        {"skill": "cws:cws-deploy", "skill_sha": "a"}, {"skill": "general:fs", "skill_sha": "b"},
        {"skill": "markdown", "skill_sha": "c"}]}))
    got = {s["leaf"]: s["sha"] for s in fd._chip_skills(str(tmp_path))}
    assert got == {"cws-deploy": "a", "fs": "b", "markdown": "c"}


def test_chip_skills_no_manifest_is_empty_failclosed(tmp_path):
    assert fd._chip_skills(str(tmp_path)) == []          # no manifest -> [] -> no subset check can pass


# ── _register: atomic append/replace by name, drops None fields, creates parent dir ──
def test_register_appends_replaces_and_drops_none(tmp_path):
    f = tmp_path / "sub" / "fleet.json"                 # parent dir is created by _register
    fd._register(str(f), {"name": "node-a", "fleet_tier": "subagent", "url": "http://x", "tier": None})
    assert json.load(open(f))["nodes"] == [{"name": "node-a", "fleet_tier": "subagent", "url": "http://x"}]
    fd._register(str(f), {"name": "node-a", "fleet_tier": "edge", "url": "http://y"})       # replace by name
    nodes = json.load(open(f))["nodes"]
    assert len(nodes) == 1 and nodes[0]["fleet_tier"] == "edge"


# ── down: _deregister removes exactly the named row ──
def test_deregister_removes_named_row(tmp_path):
    f = tmp_path / "fleet.json"
    f.write_text(json.dumps({"nodes": [{"name": "a"}, {"name": "node-a"}, {"name": "b"}]}))
    assert fdown._deregister(str(f), "node-a") is True
    assert [n["name"] for n in json.load(open(f))["nodes"]] == ["a", "b"]


def test_deregister_absent_row_and_missing_file_are_noops(tmp_path):
    f = tmp_path / "fleet.json"
    f.write_text(json.dumps({"nodes": [{"name": "a"}]}))
    assert fdown._deregister(str(f), "ghost") is False
    assert [n["name"] for n in json.load(open(f))["nodes"]] == ["a"]
    assert fdown._deregister(str(tmp_path / "nope.json"), "x") is False


# ── cartridge subset: the real least-privilege compile (MODE=compose) is content-identical to the parent ──
def _chip_root():
    chip = os.path.normpath(os.path.join(_HERE, "..", "skillChip"))
    if not os.path.isfile(os.path.join(chip, "index.json")):
        pytest.skip("chip manifest absent")
    return os.path.normpath(os.path.join(_HERE, "..")), chip


def test_cartridge_subset_is_content_identical_to_parent(tmp_path):
    import subprocess
    import sys
    root, chip = _chip_root()
    parent = {s["leaf"]: s["sha"] for s in fd._chip_skills(chip)}
    if "fs" not in parent:
        pytest.skip("parent chip has no 'fs' skill")
    out = str(tmp_path / "child")
    r = subprocess.run([sys.executable, "-m", "infra.tool.cartridge", "--compile", "fs", "--out", out],
                       cwd=root, capture_output=True, text=True,
                       env={**os.environ, "CYBERWARE_SKILLCHIP": chip})
    assert r.returncode == 0, r.stderr
    child = fd._chip_skills(out)
    assert child and all(s["sha"] == parent.get(s["leaf"]) for s in child)   # verbatim copy: sha matches the parent
    # and the full containment gate accepts it
    assert fd.check_containment("mothership", "subagent", ["fs"], fd._chip_skills(chip), child) == (True, None)


def test_cartridge_rejects_a_skill_outside_the_parent(tmp_path):
    import subprocess
    import sys
    root, chip = _chip_root()
    out = str(tmp_path / "child")
    r = subprocess.run([sys.executable, "-m", "infra.tool.cartridge", "--compile", "__nope__", "--out", out],
                       cwd=root, capture_output=True, text=True,
                       env={**os.environ, "CYBERWARE_SKILLCHIP": chip})
    assert r.returncode != 0            # not in the parent -> cartridge fails -> deploy would refuse (compose_failed)
