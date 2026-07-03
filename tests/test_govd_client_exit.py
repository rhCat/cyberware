"""The client exit-code contract: a governance-BLOCKED run must never report success to a caller keying on the
process exit code. A per-step {"refused": ...} (ACL denial, snippet drift, oversight-channel close, a limb that
refused the step) is a block even though the run still returns decision="allow" — that step never ran."""
from __future__ import annotations

from infra.govern.govd_client import blocked_run


def test_up_front_error_is_blocked():
    assert blocked_run({"run_id": "r", "decision": "allow", "error": "registry mismatch"}) is True


def test_step_refusal_is_blocked_even_with_decision_allow():
    # the exact defect: a step govd/exod REFUSED (never ran) inside an allow-decision run
    out = {"run_id": "r", "decision": "allow", "mode": "delegated",
           "results": [{"step": "1", "status": "ok", "exit": 0},
                       {"step": "2", "refused": "acl_skill_denied"}]}
    assert blocked_run(out) is True


def test_cooperative_step_refusal_is_blocked():
    out = {"run_id": "r", "decision": "allow", "script": "run.sh",
           "results": [{"step": "1", "refused": "server closed the oversight channel"}]}
    assert blocked_run(out) is True


def test_delegated_exod_refusal_status_is_blocked():
    # the P1 the adversarial review caught: a DELEGATED step exod refused off-node arrives as
    # {"status": "refused"} with NO `refused` key (grant workspace/argv mismatch, off-node ACL/params denial,
    # capmanifest mount check, closure drift, unreachable/unverifiable limb, vault/sandbox unavailable). The
    # original fix keyed only on the `refused` key and missed this shape → exit 0 for a real governance block.
    out = {"run_id": "r", "decision": "allow", "mode": "delegated",
           "results": [{"step": "1", "status": "ok", "exit": 0, "authority": "exod"},
                       {"step": "2", "status": "refused", "exit": None, "authority": "exod"}]}
    assert blocked_run(out) is True


def test_refused_key_presence_not_truthiness():
    # defense-in-depth (P3): a refusal recorded with a falsy reason must still count as blocked — key on the
    # PRESENCE of `refused`, not the truthiness of the reason a peer supplied.
    out = {"run_id": "r", "decision": "allow", "results": [{"step": "1", "refused": None}]}
    assert blocked_run(out) is True


def test_clean_run_is_not_blocked():
    out = {"run_id": "r", "decision": "allow", "results": [{"step": "1", "exit": 0},
                                                           {"step": "2", "status": "ok", "exit": 0}]}
    assert blocked_run(out) is False


def test_faithful_task_failure_is_not_a_governance_block():
    # a step that RAN and exited non-zero is a task failure (in results/ledger), not a governance block: the
    # exit-code contract is about GOVERNANCE outcome, not the task's own exit.
    out = {"run_id": "r", "decision": "allow",
           "results": [{"step": "1", "status": "error", "exit": 3}]}
    assert blocked_run(out) is False


def test_no_results_key_is_safe():
    assert blocked_run({"run_id": "r", "decision": "allow"}) is False
