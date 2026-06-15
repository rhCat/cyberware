#!/usr/bin/env python3
"""redeem_p2t07.py — redeem P2-T07 (exod-attested meters) via cws-bench, run INSIDE the exec image.
Drives cws-bench/bwrap-overhead through govd (it measures the bwrap p95 from exod's signed meters and exits
0 iff within the <=100ms budget), then cws-observe/redeem P2-T07 against that governed run-ledger
(validated_by=cws-bench). Assumes govd is running with GOVD_RECORD_ROOT set; the done-ledger write persists.
"""
import json
import os
import sys

sys.path.insert(0, "/work")
from infra.govern import govd_client  # noqa: E402

BASE = os.environ.get("GOVD_URL", "http://127.0.0.1:5773")
GROOT = os.environ["GOVD_RECORD_ROOT"]
RUNS = "/work/workzone/version1.1/runs/bench-exec"
SW = "/work/workzone/version1.1/cyberware-swarm-v1.1"
DL = f"{SW}/done-ledger-v2.json"


def main():
    led = {"skill": "cws-bench", "perk": "bwrap-overhead", "record_store": f"{RUNS}/bwrap-overhead",
           "vars": {"N": "40"}}
    r = govd_client.run_governed(BASE, led)
    exits = [s.get("exit") for s in r.get("results", [])]
    print(f"cws-bench/bwrap-overhead: decision={r.get('decision')} exits={exits} run={r.get('run_id')}")
    bj = f"{RUNS}/bwrap-overhead/bench.json"
    if os.path.isfile(bj):
        b = json.load(open(bj))
        print(f"  measured: p50={b.get('p50')}ms p95={b.get('p95')}ms budget={b.get('budget_ms')}ms within={b.get('within')}")
    if not (r.get("decision") == "allow" and exits == [0]):
        print("ABORT: bench did not meet the budget — refusing to redeem."); sys.exit(1)

    evidence = f"{GROOT}/{r['run_id']}/ledger.json"
    assert os.path.isfile(evidence), f"missing evidence {evidence}"
    led2 = {"skill": "cws-observe", "perk": "redeem", "record_store": f"{RUNS}/redeem-P2-T07",
            "vars": {"SWARM_DIR": SW, "TASK_ID": "P2-T07", "RUN_LEDGER": evidence, "DONE_LEDGER": DL}}
    r2 = govd_client.run_governed(BASE, led2)
    out = json.load(open(f"{RUNS}/redeem-P2-T07/redeem.json")) if os.path.isfile(
        f"{RUNS}/redeem-P2-T07/redeem.json") else {}
    print(f"redeem P2-T07: exits={[s.get('exit') for s in r2.get('results',[])]} verdict={out.get('verdict')} {out.get('reason','')}")

    entries = json.load(open(DL)).get("entries", [])
    print("\nP2 pass entries:")
    for e in entries:
        if e.get("verdict") == "pass" and e.get("task_id", "").startswith("P2"):
            print(f"  {e.get('seq')}: {e.get('task_id')} <- {e.get('validator')}")


if __name__ == "__main__":
    main()
