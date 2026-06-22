#!/usr/bin/env python3
"""redeem_tail.py — drive the two locally-passable tail validators through a FRESH govd, then redeem the
tasks they evidence onto done-ledger-v2.

  P5-T03  validated_by=cws-bench    validated_perk=org-isolation  (multi-tenant org isolation selftest)
  P4-T07  validated_by=cws-mutate   validated_perk=mut-emitter    (mutation-test the workflow->TLA+ emitter)

Everything is governed: govd blesses the value-free plan, the agent runs the porters from its OWN registry,
govd records STATUS only. The redeem binds each task to its validator skill+perk (fail-closed) and appends a
prev-hash-chained pass to done-ledger-v2.json. A fresh govd is required so the blessed hashes match the
just-re-pinned chip (the long-running daemons predate mut-emitter/org-isolation).
"""
import json
import os
import subprocess
import sys
import time
import urllib.request

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, ROOT)
from infra.govern import govd_client  # noqa: E402

PORT = 5793
BASE = f"http://127.0.0.1:{PORT}"
RUNS = os.path.join(ROOT, "workzone/version1.1/runs")
GROOT = os.path.join(RUNS, "tail-govd-root")
SW = os.path.join(ROOT, "workzone/version1.1/cyberware-swarm-v1.1")
DL = os.path.join(SW, "done-ledger-v2.json")

# (task, validator skill, validator perk, vars for the drive)
JOBS = [
    ("P5-T03", "cws-bench", "org-isolation", {}),
    ("P4-T07", "cws-mutate", "mut-emitter", {"PROJECT_DIR": ROOT, "THRESHOLD": "0.90"}),
]


def wait_up(timeout=30):
    for _ in range(timeout * 2):
        try:
            urllib.request.urlopen(BASE + "/health", timeout=1).read()
            return True
        except Exception:
            time.sleep(0.5)
    return False


def main():
    env = dict(os.environ, GOVD_RECORD_ROOT=GROOT)
    env.pop("GOVD_PRINCIPALS", None)  # no auth registry -> pid="local"
    proc = subprocess.Popen([sys.executable, "-m", "infra.govern.govd", "--mode", "local",
                             "--port", str(PORT)], cwd=ROOT, env=env)
    try:
        if not wait_up():
            print("ABORT: fresh govd did not come up"); return 1
        print(f"== fresh govd up at {BASE} (record_root={GROOT}) ==")

        run_ids = {}
        for tid, skill, perk, vars_ in JOBS:
            rstore = os.path.join(RUNS, f"redeem-{tid.lower().replace('-', '')}", "run")
            os.makedirs(rstore, exist_ok=True)
            led = {"skill": skill, "perk": perk, "record_store": rstore, "vars": vars_}
            print(f"\n== drive {skill}/{perk} (for {tid}) ==")
            r = govd_client.run_governed(BASE, led)
            exits = [s.get("exit") for s in r.get("results", [])]
            ok = r.get("decision") == "allow" and exits == [0] and not r.get("error")
            print(f"  decision={r.get('decision')} exits={exits} run={r.get('run_id')} "
                  f"{'OK' if ok else 'FAIL ' + str(r.get('error'))}")
            if not ok:
                print("ABORT: validator did not pass under govd — refusing to redeem."); return 1
            run_ids[tid] = r["run_id"]

        for tid, skill, perk, _ in JOBS:
            ledger = os.path.join(GROOT, run_ids[tid], "ledger.json")
            assert os.path.isfile(ledger), f"missing govd ledger {ledger}"
            ev_dir = os.path.join(RUNS, f"redeem-{tid.lower().replace('-', '')}", "evidence")
            os.makedirs(ev_dir, exist_ok=True)
            ev = os.path.join(ev_dir, "run-ledger.json")
            with open(ledger) as f, open(ev, "w") as g:
                g.write(f.read())
            rstore = os.path.join(RUNS, f"redeem-{tid.lower().replace('-', '')}", "redeem")
            os.makedirs(rstore, exist_ok=True)
            led = {"skill": "cws-observe", "perk": "redeem", "record_store": rstore,
                   "vars": {"SWARM_DIR": SW, "TASK_ID": tid, "RUN_LEDGER": ev, "DONE_LEDGER": DL}}
            print(f"\n== redeem {tid} (binds {skill}/{perk}) ==")
            r = govd_client.run_governed(BASE, led)
            exits = [s.get("exit") for s in r.get("results", [])]
            ok = r.get("decision") == "allow" and exits == [0] and not r.get("error")
            rj = os.path.join(rstore, "redeem.json")
            verdict = json.load(open(rj)) if os.path.isfile(rj) else {}
            print(f"  decision={r.get('decision')} exits={exits} verdict={verdict.get('verdict')} "
                  f"seq={verdict.get('seq')} {'OK' if ok else 'FAIL ' + str(r.get('error'))}")
            if not ok or verdict.get("verdict") != "pass":
                print("ABORT: redeem did not pass."); return 1
        print("\n== both tasks redeemed onto done-ledger-v2 ==")
        return 0
    finally:
        proc.terminate()
        try:
            proc.wait(timeout=5)
        except Exception:
            proc.kill()


if __name__ == "__main__":
    sys.exit(main())
