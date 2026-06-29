"""Unit tests for the cws-fleet `deploy` containment core — the anti-rogue security logic, exercised
independently of docker. The core lives in the skillChip submodule; we load it by path so the security
decision is reviewable as a pure function (mirrors how principals.acl_allows is unit-tested apart from govd).
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

PARENT = {"fs", "http", "git_ops"}        # the parent chip's catalog (skill leaves)


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


# ── check_containment: the fail-closed decision, full reason table ──
@pytest.mark.parametrize("parent_ft,child_ft,acl,child_set,ok,reason", [
    ("mothership", "subagent", {"fs"}, {"fs"}, True, None),
    ("edge", "subagent", {"fs", "http"}, {"fs", "http"}, True, None),
    ("mothership", 9, {"fs"}, {"fs"}, True, None),                                          # deeper int child
    ("mothership", "mothership", {"fs"}, {"fs"}, False, "fleet_tier_not_strictly_lower"),   # sideways
    ("edge", "mothership", {"fs"}, {"fs"}, False, "fleet_tier_not_strictly_lower"),         # upward
    ("subagent", "edge", {"fs"}, {"fs"}, False, "fleet_tier_not_strictly_lower"),           # upward
    ("garbage", "subagent", {"fs"}, {"fs"}, False, "fleet_tier_unknown"),
    ("mothership", None, {"fs"}, {"fs"}, False, "fleet_tier_unknown"),
    ("mothership", "subagent", {"fs", "s3"}, {"fs"}, False, "acl_not_subset"),              # acl beyond parent
    ("mothership", "subagent", {"fs"}, {"fs", "s3"}, False, "chip_not_subset"),             # child smuggles a skill
    ("mothership", "subagent", {"http"}, {"fs"}, False, "acl_exceeds_chip"),                # acl not on the child chip
])
def test_check_containment(parent_ft, child_ft, acl, child_set, ok, reason):
    assert fd.check_containment(parent_ft, child_ft, acl, PARENT, child_set) == (ok, reason)


def test_empty_acl_is_a_vacuous_subset_and_allowed():
    # a body granted nothing is the minimal contained body — allowed when the tiers descend
    assert fd.check_containment("mothership", "subagent", set(), PARENT, {"fs"}) == (True, None)


def test_tier_gate_precedes_subset_gates():
    # the cheap tier gate is reported BEFORE any subset failure (no spawn ever reaches the subset check)
    assert fd.check_containment("subagent", "subagent", {"s3"}, PARENT, {"s3"}) == (False, "fleet_tier_not_strictly_lower")


# ── _chip_leaves: manifest read, fail-closed on absence ──
def test_chip_leaves_reads_namespaced_and_bare(tmp_path):
    (tmp_path / "index.json").write_text(json.dumps({"skills": [
        {"skill": "cws:cws-deploy"}, {"skill": "general:fs"}, {"skill": "markdown"}]}))
    assert fd._chip_leaves(str(tmp_path)) == {"cws-deploy", "fs", "markdown"}


def test_chip_leaves_no_manifest_is_empty_failclosed(tmp_path):
    assert fd._chip_leaves(str(tmp_path)) == set()      # no manifest -> empty -> no subset check can pass


# ── _register: atomic append/replace by name, drops None fields, creates parent dir ──
def test_register_appends_replaces_and_drops_none(tmp_path):
    f = tmp_path / "sub" / "fleet.json"                 # parent dir is created by _register
    fd._register(str(f), {"name": "scribe", "fleet_tier": "subagent", "url": "http://x", "tier": None})
    assert json.load(open(f))["nodes"] == [{"name": "scribe", "fleet_tier": "subagent", "url": "http://x"}]
    fd._register(str(f), {"name": "scribe", "fleet_tier": "edge", "url": "http://y"})       # replace by name
    nodes = json.load(open(f))["nodes"]
    assert len(nodes) == 1 and nodes[0]["fleet_tier"] == "edge"


# ── down: _deregister removes exactly the named row ──
def test_deregister_removes_named_row(tmp_path):
    f = tmp_path / "fleet.json"
    f.write_text(json.dumps({"nodes": [{"name": "a"}, {"name": "scribe"}, {"name": "b"}]}))
    assert fdown._deregister(str(f), "scribe") is True
    assert [n["name"] for n in json.load(open(f))["nodes"]] == ["a", "b"]


def test_deregister_absent_row_and_missing_file_are_noops(tmp_path):
    f = tmp_path / "fleet.json"
    f.write_text(json.dumps({"nodes": [{"name": "a"}]}))
    assert fdown._deregister(str(f), "ghost") is False
    assert [n["name"] for n in json.load(open(f))["nodes"]] == ["a"]
    assert fdown._deregister(str(tmp_path / "nope.json"), "x") is False


# ── cartridge subset: the real least-privilege compile (MODE=compose) is within the parent ──
def _chip_root():
    chip = os.path.normpath(os.path.join(_HERE, "..", "skillChip"))
    if not os.path.isfile(os.path.join(chip, "index.json")):
        pytest.skip("chip manifest absent")
    return os.path.normpath(os.path.join(_HERE, "..")), chip


def test_cartridge_subset_is_within_parent(tmp_path):
    import subprocess
    import sys
    root, chip = _chip_root()
    parent_leaves = fd._chip_leaves(chip)
    if "fs" not in parent_leaves:
        pytest.skip("parent chip has no 'fs' skill")
    out = str(tmp_path / "child")
    r = subprocess.run([sys.executable, "-m", "infra.tool.cartridge", "--compile", "fs", "--out", out],
                       cwd=root, capture_output=True, text=True,
                       env={**os.environ, "CYBERWARE_SKILLCHIP": chip})
    assert r.returncode == 0, r.stderr
    child_leaves = fd._chip_leaves(out)
    assert child_leaves and child_leaves <= parent_leaves            # least-privilege subset ⊆ parent


def test_cartridge_rejects_a_skill_outside_the_parent(tmp_path):
    import subprocess
    import sys
    root, chip = _chip_root()
    out = str(tmp_path / "child")
    r = subprocess.run([sys.executable, "-m", "infra.tool.cartridge", "--compile", "__nope__", "--out", out],
                       cwd=root, capture_output=True, text=True,
                       env={**os.environ, "CYBERWARE_SKILLCHIP": chip})
    assert r.returncode != 0            # not in the parent -> cartridge fails -> deploy would refuse (compose_failed)
