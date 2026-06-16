#!/usr/bin/env python3
"""infra/exec/legacy.py — the legacy in-process execution path, behind a loud [UNGOVERNED-BOUNDARY] banner
(P2-T11).

Before SV-3, a step ran in-process: software-governed (the executor's tamper-check + oversight scan) but
NOT kernel-enforced. exod (P2-T02) replaces it with a real kernel boundary. This path survives only for a
host without bwrap, or a deliberate ungoverned run — and it must NEVER be mistaken for the governed one.
So every invocation EMITS the banner, and the result is tagged `governed=False` with `boundary` =
`ungoverned-in-process`. A governed exod step-result, by contrast, is SIGNED (the ledger trusts it via
`exodverify.verify_step_result`) — so the honest governed/ungoverned distinction is always visible in the
logs and in the record, never silent.
"""
from __future__ import annotations
import subprocess
import sys

BANNER = "[UNGOVERNED-BOUNDARY] in-process execution — NOT kernel-enforced (no exod sandbox)"


def run_in_process(argv, *, reason: str = "", timeout: int = 600, log=None) -> dict:
    """Run `argv` directly in-process — no sandbox. Emits the [UNGOVERNED-BOUNDARY] banner EVERY run and
    returns a result tagged `governed=False`, so it cannot be confused with a governed exod step-result."""
    line = BANNER + (f" · {reason}" if reason else "")
    print(line, file=log if log is not None else sys.stderr, flush=True)
    p = subprocess.run(argv, capture_output=True, text=True, timeout=timeout)
    return {"governed": False, "boundary": "ungoverned-in-process", "banner": BANNER, "reason": reason,
            "argv": list(argv), "exit": p.returncode, "stdout": p.stdout, "stderr": p.stderr}


def is_governed(result) -> bool:
    """True only for a governed (kernel-enforced, exod-signed) result. A legacy in-process result carries
    `governed=False`; an exod step-result is a signed DSSE envelope (a `payloadType` of the step-result
    type). Anything else is treated as ungoverned — the safe default."""
    if not isinstance(result, dict):
        return False
    if result.get("governed") is False or result.get("boundary") == "ungoverned-in-process":
        return False
    return result.get("payloadType") == "application/vnd.cyberware.step-result+json"
