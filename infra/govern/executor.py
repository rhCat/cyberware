#!/usr/bin/env python3
"""executor.py — the ONLY channel that runs a compiled script. The governance / enforcement layer.

The agent never runs the compiled bash directly — it calls executor.py, which:
  * snapshots the script to `.<script>.bk` on first run, and REFUSES if the script later drifts
    (an agent editing a compiled step to slip past a contract is caught — tamper-check);
  * enforces OVERSIGHT_RULE *inside the channel* — the script is scanned before any step runs and
    REFUSED on unwaived violations; approvable rules are waived only by an explicit `--approve <id>`,
    and every waiver is recorded to the run-ledger (running `oversight.py` first is pre-flight
    visibility, but the executor re-checks regardless — the gate cannot be skipped);
  * REFUSES a step whose upstream steps have not been recorded as run (require_upstream);
  * registers every run — ts, step, exit, duration, output hash, output tail — to a persistent
    `run-ledger.json` under the record_store (the provenance chain);
  * enforces the timeout and other EXECUTOR_RULE.json limits.

If a step's output later disagrees with the hash recorded here, the drift is visible in the ledger —
governance you cannot bypass without leaving a hole in the chain.

  executor.py --script run.sh --step 1
  executor.py --script run.sh --all [--approve <rule_id>]
"""
from __future__ import annotations
import argparse, hashlib, json, os, re, subprocess, sys, time

from infra.govern.oversight import scan

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def sha(b): return hashlib.sha256(b if isinstance(b, bytes) else b.encode()).hexdigest()[:16]
def now(): return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
def rules(): return json.load(open(os.path.join(ROOT, "infra", "govern", "EXECUTOR_RULE.json")))


def record_store_of(script):
    for line in open(script):
        m = re.search(r"RECORD_STORE=('([^']*)'|\"([^\"]*)\"|(\S+))", line)
        if m:
            return next(g for g in m.groups()[1:] if g is not None)
    print("  [warn] no RECORD_STORE found in script — recording beside the script", file=sys.stderr)
    return os.path.dirname(os.path.abspath(script))


def main():
    ap = argparse.ArgumentParser(description="the governed channel — the only way to run a compiled script")
    ap.add_argument("--script", required=True)
    ap.add_argument("--step")
    ap.add_argument("--all", action="store_true")
    ap.add_argument("--approve", action="append", default=[],
                    help="waive an approvable OVERSIGHT_RULE id — an explicit, ledger-recorded decision")
    a = ap.parse_args()
    R = rules()
    script = os.path.abspath(a.script)
    body = open(script, "rb").read()
    bk = os.path.join(os.path.dirname(script), "." + os.path.basename(script) + R.get("backup_suffix", ".bk"))
    store = record_store_of(script)
    os.makedirs(store, exist_ok=True)
    lpath = os.path.join(store, R.get("record_ledger_name", "run-ledger.json"))
    ledger = json.load(open(lpath)) if os.path.isfile(lpath) else {"script": os.path.basename(script), "runs": []}
    print(f"executor · {os.path.basename(script)} → {store}")

    # 1. tamper-check against the .bk snapshot
    if R.get("tamper_check", True):
        if not os.path.isfile(bk):
            open(bk, "wb").write(body)
            print(f"  [snapshot] {os.path.basename(bk)} taken (sha {sha(body)})")
        elif open(bk, "rb").read() != body:
            old = sha(open(bk, "rb").read())
            print(f"  [TAMPER] script changed since first governed run (was {old}, now {sha(body)}) — REFUSED")
            ledger["runs"].append({"ts": now(), "event": "tamper_refused", "sha": sha(body)})
            json.dump(ledger, open(lpath, "w"), indent=2)
            sys.exit(4)
        else:
            print(f"  [tamper] script matches snapshot (sha {sha(body)})")

    # 2. oversight INSIDE the channel — the same OVERSIGHT_RULE scan, enforced before anything runs
    if R.get("oversight_check", True):
        violations, waived = scan(body.decode(errors="replace"), a.approve)
        for r in waived:
            print(f"  [oversight] WAIVED {r['id']} — {r['reason']} (explicit --approve, recorded)")
        if waived:
            ledger["runs"].append({"ts": now(), "event": "oversight_waived",
                                   "rules": [r["id"] for r in waived], "sha": sha(body)})
            json.dump(ledger, open(lpath, "w"), indent=2)
        if violations:
            for r in violations:
                how = f"  (approvable: --approve {r['id']})" if r.get("approvable") else "  (non-approvable)"
                print(f"  [OVERSIGHT] {r['id']} — {r['reason']}{how}")
            print(f"  [OVERSIGHT] {len(violations)} unwaived violation(s) — REFUSED")
            ledger["runs"].append({"ts": now(), "event": "oversight_refused",
                                   "rules": [r["id"] for r in violations], "sha": sha(body)})
            json.dump(ledger, open(lpath, "w"), indent=2)
            sys.exit(7)
        print("  [oversight] clear" + (f" ({len(waived)} waived)" if waived else ""))

    # which steps — both paths validate against the script's own --list
    listing = subprocess.run(["bash", script, "--list"], capture_output=True, text=True).stdout
    declared = [ln.split("\t")[0].strip() for ln in listing.strip().splitlines() if ln.strip()]
    if a.all:
        steps = declared
    elif a.step:
        if a.step.strip() not in declared:
            print(f"  [STEP] '{a.step}' is not a declared step (have: {', '.join(declared) or 'none'}) — REFUSED")
            sys.exit(2)
        steps = [a.step.strip()]
    else:
        print("specify --step <N> or --all"); sys.exit(2)

    ran = {r["step"] for r in ledger["runs"] if r.get("status") == "ok" and "step" in r}
    for st in steps:
        # 3. upstream gate
        if R.get("require_upstream", True):
            if not st.isdigit() or int(st) < 1:
                print(f"  [STEP] '{st}' is not a valid step number — REFUSED")
                sys.exit(2)
            missing = [str(i) for i in range(1, int(st)) if str(i) not in ran]
            if missing:
                print(f"  [UPSTREAM] step {st} blocked — upstream not run: {', '.join(missing)} — REFUSED")
                sys.exit(5)
        # 4. governed run + provenance record
        print(f"  [run] step {st}")
        t0 = time.time()
        try:
            p = subprocess.run(["bash", script, "--step", str(st)], capture_output=True, text=True,
                               timeout=R.get("max_runtime_seconds", 600))
        except subprocess.TimeoutExpired:
            print(f"  [TIMEOUT] step {st} exceeded {R.get('max_runtime_seconds')}s — REFUSED")
            ledger["runs"].append({"ts": now(), "step": str(st), "status": "timeout"})
            json.dump(ledger, open(lpath, "w"), indent=2)
            sys.exit(6)
        dt = round(time.time() - t0, 2)
        tail = (p.stdout.strip().splitlines() or [""])[-1]
        rec = {"ts": now(), "step": str(st), "status": "ok" if p.returncode == 0 else "error",
               "exit": p.returncode, "seconds": dt, "stdout_sha": sha(p.stdout), "stdout_tail": tail}
        ledger["runs"].append(rec)
        ran.add(str(st))
        json.dump(ledger, open(lpath, "w"), indent=2)
        print(f"      exit={p.returncode} {dt}s · recorded → {lpath}")
        if tail:
            print(f"      output: {tail}")
        if p.returncode != 0:
            print(f"      stderr: {p.stderr.strip()[:300]}")
            sys.exit(p.returncode)
    print("executor: done (governed)")


if __name__ == "__main__":
    main()
