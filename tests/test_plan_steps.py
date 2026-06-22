"""P1-T06 — the blessed plan is the sole source of step truth (infra/govern/executor.plan_steps).

The governed executor must derive WHICH steps to run from the perk's authenticity-hashed manifesto
sequence — the same structure govd blesses as plan["sequence"] — never by executing the script's own
`--list`. Crucially the manifesto is AUTHENTICATED against its blessed sha256 in the skill index.json (the
same root of trust as the per-step porter digests), so a post-bless manifesto swap cannot decouple the
step→tool map from snippet verification. These tests pin both sides of the derivation so its mutants (the
1-based range, the enumerate start, the None guard, the sequence default, the sha compare) are killed, and
prove the security properties directly: a lying sibling `--list` cannot change the step set (plan_steps
never reads the script), and a tampered/unblessed manifesto fails closed.
"""
from __future__ import annotations

import hashlib
import json
import os

from infra.govern.plan_steps import plan_steps


def _perk(tmp_path, sequence):
    """Lay out perks/<perk>/{manifesto.json, src/} + a skill index.json that BLESSES the manifesto's sha256
    (a real index.json hashes the manifesto). Return the src dir (what plan_steps receives)."""
    src = tmp_path / "perks" / "p" / "src"
    src.mkdir(parents=True)
    body = json.dumps({"sequence": sequence}).encode()
    (tmp_path / "perks" / "p" / "manifesto.json").write_bytes(body)
    (tmp_path / "index.json").write_text(
        json.dumps({"files": {"perks/p/manifesto.json": hashlib.sha256(body).hexdigest()}}))
    return str(src)


def test_steps_are_the_one_based_indices_of_the_manifesto_sequence(tmp_path):
    snip = _perk(tmp_path, ["tool_a", "tool_b", "tool_c"])
    declared, step_tool = plan_steps(snip)
    assert declared == ["1", "2", "3"]                       # 1-based, exactly len(sequence) ids
    assert step_tool == {"1": "tool_a", "2": "tool_b", "3": "tool_c"}


def test_single_step_sequence(tmp_path):
    snip = _perk(tmp_path, ["only"])
    assert plan_steps(snip) == (["1"], {"1": "only"})        # not ["0"], not ["1","2"]


def test_non_compiler_script_declares_no_steps():
    assert plan_steps(None) == ([], {})                      # no blessed plan -> nothing declared -> refused


def test_missing_or_unreadable_manifest_declares_no_steps(tmp_path):
    src = tmp_path / "perks" / "p" / "src"
    src.mkdir(parents=True)                                  # src exists but NO manifesto.json
    assert plan_steps(str(src)) == ([], {})


def test_empty_sequence_declares_no_steps(tmp_path):
    assert plan_steps(_perk(tmp_path, [])) == ([], {})


def test_tampered_manifesto_fails_closed(tmp_path):
    """SECURITY (the blocker this fix closes): a manifesto whose body no longer matches its blessed
    index.json sha — a post-bless swap to rename a tool so snippet-verify looks for the wrong porter — is
    refused. plan_steps authenticates the manifesto, so the swap yields the empty plan, not a decoupled map."""
    snip = _perk(tmp_path, ["real"])
    mpath = os.path.join(os.path.dirname(snip), "manifesto.json")
    open(mpath, "w").write(json.dumps({"sequence": ["renamed_so_snippet_check_misses"]}))   # sha now != blessed
    assert plan_steps(snip) == ([], {})


def test_unblessed_manifesto_fails_closed(tmp_path):
    """A manifesto with NO entry in the skill index.json (never blessed) is not trusted."""
    src = tmp_path / "perks" / "p" / "src"
    src.mkdir(parents=True)
    (tmp_path / "perks" / "p" / "manifesto.json").write_text(json.dumps({"sequence": ["x"]}))
    (tmp_path / "index.json").write_text(json.dumps({"files": {}}))    # blesses nothing
    assert plan_steps(str(src)) == ([], {})


def test_manifesto_without_sequence_key_declares_no_steps(tmp_path):
    """A blessed manifesto that exists but lacks a 'sequence' key declares nothing — no fabricated step."""
    src = tmp_path / "perks" / "p" / "src"
    src.mkdir(parents=True)
    body = json.dumps({"requires": ["x"]}).encode()
    (tmp_path / "perks" / "p" / "manifesto.json").write_bytes(body)
    (tmp_path / "index.json").write_text(
        json.dumps({"files": {"perks/p/manifesto.json": hashlib.sha256(body).hexdigest()}}))
    assert plan_steps(str(src)) == ([], {})


def test_a_lying_script_list_cannot_change_the_step_set(tmp_path):
    """The security property: plan_steps reads the manifesto, never the script — so a tampered `--list`
    (here a sibling run.sh that prints a bogus extra step / a different tool) is structurally ignored."""
    snip = _perk(tmp_path, ["real_tool"])
    run_sh = tmp_path / "perks" / "p" / "src" / "run.sh"
    run_sh.write_text('#!/usr/bin/env bash\ncase "$1" in --list) printf "1\\tEVIL_TOOL\\n2\\tINJECTED\\n";; esac\n')
    declared, step_tool = plan_steps(snip)
    assert declared == ["1"] and step_tool == {"1": "real_tool"}   # the lying --list had zero effect
    assert "EVIL_TOOL" not in step_tool.values() and "2" not in declared


def test_executor_main_uses_plan_steps_not_subprocess_list():
    """Guard against regression: executor.main must derive steps via plan_steps and must NOT shell out to
    `--list`. (A coarse source check — the unit tests above prove the behaviour; this pins the wiring.)"""
    src = open(os.path.join(os.path.dirname(__file__), "..", "infra", "govern", "executor.py")).read()
    assert "plan_steps(snip)" in src
    assert "from infra.govern.plan_steps import plan_steps" in src
    assert '"--list"' not in src                              # no --list execution survives anywhere
    # the agent-side runner derives steps from the blessed plan too, never the porter's --list
    gc = open(os.path.join(os.path.dirname(__file__), "..", "infra", "govern", "govd_client.py")).read()
    assert '"--list"' not in gc
