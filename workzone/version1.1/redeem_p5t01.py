#!/usr/bin/env python3
"""redeem_p5t01.py — drive cws-bench/store-reconcile through a FRESH govd, then redeem P5-T01 onto done-ledger-v2.

P5-T01 (Store behind a StoreBackend interface: sqlite-WAL + psycopg/Postgres-15, with the chained JSONL as the
artifact of record + a continuous reconciler) is validated_by=cws-bench. The governed cws-bench/store-reconcile
run proves the acceptance: both adapters pass ONE identical contract suite (the LIVE Postgres leg runs when
GOVD_STORE_DSN is set — see below), zero divergence across the soak, and an injected divergence alarmed within
ONE cycle. A fresh govd is required so the blessed hashes match the just-re-pinned chip.

To prove the LIVE Postgres adapter through the GOVERNED channel (not just pytest), this driver wires the DSN
the way an operator would: a server-side file at ~/.cyberware/store-dsn (the key_file pattern). The porter
reads it; the secret NEVER crosses the governed env as a var or into the ledger. Set GOVD_STORE_DSN to point
at a reachable Postgres (the local docker `cyberware-pg15` is the default); if none is reachable the live leg
honestly SKIPs and `both_adapters_pass` is recorded false (the live adapter is still proven in
tests/test_store.py)."""
import json
import os
import subprocess
import sys
import time
import urllib.request

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, ROOT)
from infra.govern import govd_client  # noqa: E402

PORT = 5792
BASE = f"http://127.0.0.1:{PORT}"
RUNS = os.path.join(ROOT, "workzone/version1.1/runs")
GROOT = os.path.join(RUNS, "p5t01-govd-root")
SW = os.path.join(ROOT, "workzone/version1.1/cyberware-swarm-v1.1")
DL = os.path.join(SW, "done-ledger-v2.json")
TASK, SKILL, PERK = "P5-T01", "cws-bench", "store-reconcile"
DSN = os.environ.get("GOVD_STORE_DSN", "postgresql://postgres:cyberware@127.0.0.1:55432/govdstore")


def wait_up(timeout=30):
    for _ in range(timeout * 2):
        try:
            urllib.request.urlopen(BASE + "/health", timeout=1).read()
            return True
        except Exception:
            time.sleep(0.5)
    return False


def _wire_operator_dsn():
    """Simulate the operator wiring the Postgres DSN server-side at the well-known key_file path, IF a live
    Postgres is reachable. Returns the path written (to clean up after), or None. The governed env never
    carries the secret — the porter reads this file."""
    try:
        import psycopg
        psycopg.connect(DSN, connect_timeout=3).close()
    except Exception:
        return None                                          # no live Postgres -> live leg honestly skips
    wk = os.path.expanduser("~/.cyberware/store-dsn")
    os.makedirs(os.path.dirname(wk), exist_ok=True)
    fd = os.open(wk, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    with os.fdopen(fd, "w") as f:
        f.write(DSN)
    return wk


def main():
    wk = _wire_operator_dsn()                                # operator-style server-side DSN file (or None)
    print(f"== operator DSN wired: {wk or '(no live Postgres — live leg will skip)'} ==")
    # govd's OWN Store stays sqlite (env != cfg); the porter finds the operator DSN file and runs the live leg.
    env = dict(os.environ, GOVD_RECORD_ROOT=GROOT, N_OPS="2000", SOAK_CYCLES="20")
    env.pop("GOVD_PRINCIPALS", None)
    proc = subprocess.Popen([sys.executable, "-m", "infra.govern.govd", "--mode", "local",
                             "--port", str(PORT)], cwd=ROOT, env=env)
    try:
        if not wait_up():
            print("ABORT: fresh govd did not come up"); return 1
        print(f"== fresh govd up at {BASE} (record_root={GROOT}, store dsn set) ==")

        rstore = os.path.join(RUNS, "redeem-p5t01", "run")
        os.makedirs(rstore, exist_ok=True)
        led = {"skill": SKILL, "perk": PERK, "record_store": rstore, "vars": {}}
        print(f"\n== drive {SKILL}/{PERK} (for {TASK}) ==")
        r = govd_client.run_governed(BASE, led)
        exits = [s.get("exit") for s in r.get("results", [])]
        ok = r.get("decision") == "allow" and exits == [0] and not r.get("error")
        rj = os.path.join(rstore, "reconcile.json")
        recon = json.load(open(rj)) if os.path.isfile(rj) else {}
        print(f"  decision={r.get('decision')} exits={exits} run={r.get('run_id')} "
              f"psycopg_live={recon.get('psycopg_live')} within={recon.get('within')} "
              f"{'OK' if ok else 'FAIL ' + str(r.get('error'))}")
        if not ok:
            print("ABORT: validator did not pass under govd."); return 1

        ledger = os.path.join(GROOT, r["run_id"], "ledger.json")
        assert os.path.isfile(ledger), f"missing govd ledger {ledger}"
        ev_dir = os.path.join(RUNS, "redeem-p5t01", "evidence")
        os.makedirs(ev_dir, exist_ok=True)
        ev = os.path.join(ev_dir, "run-ledger.json")
        with open(ledger) as f, open(ev, "w") as g:
            g.write(f.read())
        rstore2 = os.path.join(RUNS, "redeem-p5t01", "redeem")
        os.makedirs(rstore2, exist_ok=True)
        led2 = {"skill": "cws-observe", "perk": "redeem", "record_store": rstore2,
                "vars": {"SWARM_DIR": SW, "TASK_ID": TASK, "RUN_LEDGER": ev, "DONE_LEDGER": DL}}
        print(f"\n== redeem {TASK} (binds {SKILL}) ==")
        r2 = govd_client.run_governed(BASE, led2)
        exits2 = [s.get("exit") for s in r2.get("results", [])]
        rj2 = os.path.join(rstore2, "redeem.json")
        verdict = json.load(open(rj2)) if os.path.isfile(rj2) else {}
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
        if wk and os.path.isfile(wk):                         # don't leave the DSN secret on disk after the run
            try:
                os.remove(wk)
            except OSError:
                pass


if __name__ == "__main__":
    sys.exit(main())
