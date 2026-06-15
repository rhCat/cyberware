#!/usr/bin/env python3
"""redeem_exec.py — the GOVERNED kernel-redteam redemption loop, run INSIDE the exec image (the only place
the bwrap boundary exists). Assumes govd is already running at $GOVD_URL with GOVD_RECORD_ROOT set and the
chip registry pointing at /work/skillChip.

  1. drive every cws-redteam perk through govd (each runs its attack THROUGH exod+sandbox and exits 0 iff
     the boundary HELD) — producing a per-run govd provenance ledger (skill=cws-redteam, a clean pass);
  2. redeem the cws-redteam-validated P2 cone (P2-T01/T02/T03/T08) against those run-ledgers — each binds
     to validated_by=cws-redteam and appends a prev-hash-chained pass entry to done-ledger-v2.

Everything here is governed (run_governed); the done-ledger write persists to the bind-mounted /work.
"""
import json
import os
import sys

sys.path.insert(0, "/work")
from infra.govern import govd_client  # noqa: E402

BASE = os.environ.get("GOVD_URL", "http://127.0.0.1:5773")
GROOT = os.environ["GOVD_RECORD_ROOT"]
RUNS = "/work/workzone/version1.1/runs/redteam-exec"
SW = "/work/workzone/version1.1/cyberware-swarm-v1.1"
DL = f"{SW}/done-ledger-v2.json"

PERKS = ["rt-fs-escape", "rt-write-rofs", "rt-write-outside", "rt-net-egress", "rt-sysrq-reboot",
         "rt-proc-sys-write", "rt-mount", "rt-device-raw", "rt-forged-status", "rt-grant-replay",
         "rt-grant-expired", "rt-grant-wrong-run", "rt-grant-forged", "rt-no-capability"]

# each cone task redeemed against a thematically-relevant perk's run-ledger (redeem binds on the validator
# skill, so any cws-redteam ledger is valid evidence; the mapping just keeps the record meaningful).
TASK_EVIDENCE = {
    "P2-T01": "rt-grant-forged",     # signed grants
    "P2-T02": "rt-forged-status",    # exod's authoritative channel
    "P2-T03": "rt-fs-escape",        # the bwrap SandboxProfile
    "P2-T08": "rt-grant-replay",     # the corpus itself
}


def main():
    run_id = {}
    print("== driving the cws-redteam corpus through govd (in the exec image) ==")
    for perk in PERKS:
        led = {"skill": "cws-redteam", "perk": perk, "record_store": f"{RUNS}/{perk}", "vars": {}}
        r = govd_client.run_governed(BASE, led)
        exits = [s.get("exit") for s in r.get("results", [])]
        ok = r.get("decision") == "allow" and exits == [0]
        print(f"  {perk:20} decision={r.get('decision')} exits={exits} run={r.get('run_id')} {'OK' if ok else 'FAIL '+str(r.get('error'))}")
        if not ok:
            print("ABORT: a red-team perk did not hold under govd — refusing to redeem.")
            sys.exit(1)
        run_id[perk] = r["run_id"]

    print("\n== redeeming the cws-redteam P2 cone onto done-ledger-v2 ==")
    for tid, perk in TASK_EVIDENCE.items():
        evidence = f"{GROOT}/{run_id[perk]}/ledger.json"
        assert os.path.isfile(evidence), f"missing evidence {evidence}"
        led = {"skill": "cws-observe", "perk": "redeem", "record_store": f"{RUNS}/redeem-{tid}",
               "vars": {"SWARM_DIR": SW, "TASK_ID": tid, "RUN_LEDGER": evidence, "DONE_LEDGER": DL}}
        r = govd_client.run_governed(BASE, led)
        exits = [s.get("exit") for s in r.get("results", [])]
        rj = f"{RUNS}/redeem-{tid}/redeem.json"
        out = json.load(open(rj)) if os.path.isfile(rj) else {}
        print(f"  {tid} via {perk:18} exits={exits} verdict={out.get('verdict')} {out.get('reason','')}")

    print("\n== done-ledger-v2 pass entries ==")
    entries = json.load(open(DL)).get("entries", [])
    for e in entries:
        if e.get("verdict") == "pass" and e.get("task_id", "").startswith("P2"):
            print(f"  {e.get('seq')}: {e.get('task_id')} <- {e.get('validator')}")


if __name__ == "__main__":
    main()
