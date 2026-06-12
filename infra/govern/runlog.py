#!/usr/bin/env python3
"""runlog.py — where a run's generated artifacts live.

Everything a single run produces — the compiled `run.sh`, its `run.{drawio,svg}` diagrams, the `.bk`
tamper snapshot, `run-ledger.json` (the executor's provenance log), the tool outputs, and a
`task-ledger.json` that points at them — is grouped under ONE run directory.

By default that directory is `~/cyberware_run_logs/<skill>__<perk>__<hash>` (set `$CYBERWARE_RUN_LOGS`
to move the root, or give an explicit `record_store` in the task-ledger to override per run). The agent
should never scatter run artifacts in /tmp — they belong, grouped, under the run-logs root.
"""
from __future__ import annotations
import argparse
import hashlib
import json
import os

DEFAULT_ROOT = os.environ.get("CYBERWARE_RUN_LOGS") or os.path.expanduser("~/cyberware_run_logs")


def is_default(value) -> bool:
    """True when record_store is unset or a `<...>` / `${...}` placeholder — meaning 'use the default'."""
    return not isinstance(value, str) or not value.strip() or value.strip().startswith(("<", "${"))


def run_dir(ledger: dict) -> str:
    """The absolute run directory for this task-ledger — an explicit record_store, or the grouped default."""
    rs = ledger.get("record_store", "")
    if not is_default(rs):
        return os.path.abspath(os.path.expanduser(rs.strip()))
    sig = hashlib.sha1(json.dumps(ledger.get("vars", {}), sort_keys=True).encode()).hexdigest()[:8]
    return os.path.join(DEFAULT_ROOT, f"{ledger['skill']}__{ledger['perk']}__{sig}")


if __name__ == "__main__":
    _ap = argparse.ArgumentParser(description="print the run dir for a task-ledger")
    _ap.add_argument("--ledger", required=True)
    print(run_dir(json.load(open(_ap.parse_args().ledger))))
