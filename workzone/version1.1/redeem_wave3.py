#!/usr/bin/env python3
"""redeem_wave3.py — drive P6-T08 + P6-T16 validators through a FRESH govd, redeem both onto done-ledger-v2.
  P3-T16  cws-release/security-doorbell    P5-T05  cws-bench/trace-propagation
A fresh govd is required so the blessed hashes match the just-re-pinned chip.
"""
import json, os, subprocess, sys, time, urllib.request
ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, ROOT)
from infra.govern import govd_client  # noqa: E402
PORT = 5797; BASE = f"http://127.0.0.1:{PORT}"
RUNS = os.path.join(ROOT, "workzone/version1.1/runs")
GROOT = os.path.join(RUNS, "wave3-govd-root")
SW = os.path.join(ROOT, "workzone/version1.1/cyberware-swarm-v1.1")
DL = os.path.join(SW, "done-ledger-v2.json")
JOBS = [("P6-T08", "cws-settle-sim", "metered-settle"), ("P6-T16", "cws-bench", "settle-throughput")]


def wait_up(t=30):
    for _ in range(t * 2):
        try:
            urllib.request.urlopen(BASE + "/health", timeout=1).read(); return True
        except Exception:
            time.sleep(0.5)
    return False


def main():
    env = dict(os.environ, GOVD_RECORD_ROOT=GROOT); env.pop("GOVD_PRINCIPALS", None)
    p = subprocess.Popen([sys.executable, "-m", "infra.govern.govd", "--mode", "local", "--port", str(PORT)],
                         cwd=ROOT, env=env)
    try:
        if not wait_up():
            print("ABORT: govd down"); return 1
        print(f"== fresh govd up at {BASE} ==")
        run_ids = {}
        for tid, skill, perk in JOBS:
            rs = os.path.join(RUNS, f"redeem-{tid.lower().replace('-', '')}", "run"); os.makedirs(rs, exist_ok=True)
            r = govd_client.run_governed(BASE, {"skill": skill, "perk": perk, "record_store": rs, "vars": {}})
            ok = r.get("decision") == "allow" and [s.get("exit") for s in r.get("results", [])] == [0] and not r.get("error")
            print(f"  drive {skill}/{perk} for {tid}: exits={[s.get('exit') for s in r.get('results', [])]} {'OK' if ok else 'FAIL ' + str(r.get('error'))}")
            if not ok:
                return 1
            run_ids[tid] = r["run_id"]
        for tid, skill, perk in JOBS:
            led = os.path.join(GROOT, run_ids[tid], "ledger.json"); assert os.path.isfile(led), led
            ev = os.path.join(RUNS, f"redeem-{tid.lower().replace('-', '')}", "evidence"); os.makedirs(ev, exist_ok=True)
            evp = os.path.join(ev, "run-ledger.json"); open(evp, "w").write(open(led).read())
            rs = os.path.join(RUNS, f"redeem-{tid.lower().replace('-', '')}", "redeem"); os.makedirs(rs, exist_ok=True)
            r = govd_client.run_governed(BASE, {"skill": "cws-observe", "perk": "redeem", "record_store": rs,
                "vars": {"SWARM_DIR": SW, "TASK_ID": tid, "RUN_LEDGER": evp, "DONE_LEDGER": DL}})
            rj = os.path.join(rs, "redeem.json"); verdict = json.load(open(rj)) if os.path.isfile(rj) else {}
            ok = r.get("decision") == "allow" and verdict.get("verdict") == "pass"
            print(f"  redeem {tid}: verdict={verdict.get('verdict')} seq={verdict.get('seq')} {'OK' if ok else 'FAIL'}")
            if not ok:
                return 1
        print("== both redeemed =="); return 0
    finally:
        p.terminate()
        try:
            p.wait(timeout=5)
        except Exception:
            p.kill()


if __name__ == "__main__":
    sys.exit(main())
