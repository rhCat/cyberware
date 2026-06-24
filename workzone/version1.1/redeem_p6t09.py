#!/usr/bin/env python3
"""redeem_p6t09.py — drive alchemy/concord through a FRESH govd, then redeem P6-T09 onto done-ledger-v2.

P6-T09 (the llm/* schema-validation payment gate — `infra/settle/intelligence.py` + the `llm/llm-extract`
intelligence skill) is validated_by=alchemy (no pinned perk). The deliverable's MONEY logic is proven in the
gates (tests/test_intelligence.py + the llm-extract/payment-gate skilltest); the REDEMPTION proof is a clean
governed alchemy run — alchemy/concord re-extracts every porter's CFG (including the new llm porter) and
confirms it concords with its committed declared blueprint, chip-wide. A fresh govd is required so the blessed
hashes match the just-re-pinned chip.
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

PORT = 5791
BASE = f"http://127.0.0.1:{PORT}"
RUNS = os.path.join(ROOT, "workzone/version1.1/runs")
GROOT = os.path.join(RUNS, "p6t09-govd-root")
SW = os.path.join(ROOT, "workzone/version1.1/cyberware-swarm-v1.1")
DL = os.path.join(SW, "done-ledger-v2.json")
TASK, SKILL, PERK = "P6-T09", "alchemy", "concord"


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
    env.pop("GOVD_PRINCIPALS", None)
    proc = subprocess.Popen([sys.executable, "-m", "infra.govern.govd", "--mode", "local",
                             "--port", str(PORT)], cwd=ROOT, env=env)
    try:
        if not wait_up():
            print("ABORT: fresh govd did not come up"); return 1
        print(f"== fresh govd up at {BASE} (record_root={GROOT}) ==")

        rstore = os.path.join(RUNS, "redeem-p6t09", "run")
        os.makedirs(rstore, exist_ok=True)
        led = {"skill": SKILL, "perk": PERK, "record_store": rstore, "vars": {}}
        print(f"\n== drive {SKILL}/{PERK} (for {TASK}) ==")
        r = govd_client.run_governed(BASE, led)
        exits = [s.get("exit") for s in r.get("results", [])]
        ok = r.get("decision") == "allow" and exits == [0] and not r.get("error")
        print(f"  decision={r.get('decision')} exits={exits} run={r.get('run_id')} "
              f"{'OK' if ok else 'FAIL ' + str(r.get('error'))}")
        if not ok:
            print("ABORT: validator did not pass under govd."); return 1

        ledger = os.path.join(GROOT, r["run_id"], "ledger.json")
        assert os.path.isfile(ledger), f"missing govd ledger {ledger}"
        ev_dir = os.path.join(RUNS, "redeem-p6t09", "evidence")
        os.makedirs(ev_dir, exist_ok=True)
        ev = os.path.join(ev_dir, "run-ledger.json")
        with open(ledger) as f, open(ev, "w") as g:
            g.write(f.read())
        rstore2 = os.path.join(RUNS, "redeem-p6t09", "redeem")
        os.makedirs(rstore2, exist_ok=True)
        led2 = {"skill": "cws-observe", "perk": "redeem", "record_store": rstore2,
                "vars": {"SWARM_DIR": SW, "TASK_ID": TASK, "RUN_LEDGER": ev, "DONE_LEDGER": DL}}
        print(f"\n== redeem {TASK} (binds {SKILL}) ==")
        r2 = govd_client.run_governed(BASE, led2)
        exits2 = [s.get("exit") for s in r2.get("results", [])]
        rj = os.path.join(rstore2, "redeem.json")
        verdict = json.load(open(rj)) if os.path.isfile(rj) else {}
        ok2 = r2.get("decision") == "allow" and exits2 == [0] and verdict.get("verdict") == "pass"
        print(f"  decision={r2.get('decision')} exits={exits2} verdict={verdict.get('verdict')} "
              f"seq={verdict.get('seq')} {'OK' if ok2 else 'FAIL ' + str(r2.get('error') or verdict.get('reason'))}")
        return 0 if ok2 else 1
    finally:
        proc.terminate()
        try:
            proc.wait(timeout=5)
        except Exception:
            proc.kill()


if __name__ == "__main__":
    sys.exit(main())
