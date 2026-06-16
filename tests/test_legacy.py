"""The legacy in-process path behind the [UNGOVERNED-BOUNDARY] banner (P2-T11): the banner fires every run
and the result is unmistakably tagged ungoverned, so logs distinguish it from a governed exod step-result."""
from __future__ import annotations

import io

from infra.exec import legacy


def test_banner_fires_on_every_run():
    buf = io.StringIO()
    for _ in range(3):
        legacy.run_in_process(["true"], reason="probe", log=buf)
    assert buf.getvalue().count(legacy.BANNER) == 3            # banner_every_run


def test_result_is_tagged_ungoverned():
    buf = io.StringIO()
    r = legacy.run_in_process(["bash", "-lc", "echo hi"], log=buf)
    assert r["governed"] is False and r["boundary"] == "ungoverned-in-process"
    assert r["exit"] == 0 and r["stdout"].strip() == "hi"
    assert legacy.BANNER in r["banner"]


def test_governed_distinction_is_honest():
    buf = io.StringIO()
    ungoverned = legacy.run_in_process(["true"], log=buf)
    assert legacy.is_governed(ungoverned) is False             # the ungoverned path is never "governed"
    governed = {"payloadType": "application/vnd.cyberware.step-result+json", "payload": "...",
                "signatures": [{"keyid": "ed25519:0123456789abcdef", "sig": "z"}]}
    assert legacy.is_governed(governed) is True                # a signed exod step-result is governed
    assert legacy.is_governed({"status": "ok"}) is False       # an unmarked dict is ungoverned (safe default)
    assert legacy.is_governed("ok") is False
