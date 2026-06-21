#!/usr/bin/env python3
"""executor.py — the ONLY channel that runs a compiled script. The governance / enforcement layer.

The agent never runs the compiled bash directly — it calls executor.py, which:
  * snapshots the script to `.<script>.bk` on first run, and REFUSES if the script later drifts
    (an agent editing a compiled step to slip past a contract is caught — tamper-check);
  * enforces OVERSIGHT_RULE *inside the channel* — the script is scanned before any step runs and
    REFUSED on unwaived violations; approvable rules are waived only by an explicit `--approve <id>`,
    and every waiver is recorded to the run-ledger (running `oversight.py` first is pre-flight
    visibility, but the executor re-checks regardless — the gate cannot be skipped);
  * RE-VERIFIES each step's snippet (the perk porter) against its blessed authenticity digest at the
    instant of execution — a perk source mutated AFTER blessing but BEFORE the step runs refuses exactly
    that step (snippet_refused, expected-vs-found recorded), closing the time-of-check-to-time-of-use gap;
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
from infra.govern.snippetverify import snippet_decision  # per-step TOCTOU decision (R3 mutation target)

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def sha(b): return hashlib.sha256(b if isinstance(b, bytes) else b.encode()).hexdigest()[:16]
def now(): return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
def rules(): return json.load(open(os.path.join(ROOT, "infra", "govern", "EXECUTOR_RULE.json")))


def _blessed_snippets(script):
    """For a compiled perk script, return ({snippet_filename: blessed_sha256}, snip_dir) — the perk's
    authenticity digests from its skill's index.json (the same source the plan's snippet_shas are blessed
    from). Returns ({}, None) for any non-compiler script, so the per-step check is a strict no-op there."""
    snip = None
    for line in open(script):
        m = re.search(r"^SNIP=('([^']*)'|\"([^\"]*)\"|(\S+))", line)
        if m:
            snip = next(g for g in m.groups()[1:] if g is not None)
            break
    if not snip:
        return {}, None
    try:                                                     # index.json sits 3 dirs above <skill>/perks/<perk>/src
        idx = json.load(open(os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(snip))), "index.json")))
        prefix = f"perks/{os.path.basename(os.path.dirname(snip))}/src/"
        return {rel[len(prefix):]: h for rel, h in idx.get("files", {}).items() if rel.startswith(prefix)}, snip
    except Exception:
        return {}, snip


def record_store_of(script):
    for line in open(script):
        m = re.search(r"RECORD_STORE=('([^']*)'|\"([^\"]*)\"|(\S+))", line)
        if m:
            return next(g for g in m.groups()[1:] if g is not None)
    print("  [warn] no RECORD_STORE found in script — recording beside the script", file=sys.stderr)
    return os.path.dirname(os.path.abspath(script))


def noroot_gate(euid, ledger, lpath):
    """No-root execution gate: faithful execution requires a NON-ROOT identity — the user's own uid or a
    scoped agent assumed-role — never ambient root. Root in a container leaves root-owned artifacts on
    bind-mounts and widens the escape surface, silently un-governing the boundary. Refuses with exit 9 when
    `euid` is 0, recording the refusal as evidence. `euid` is passed IN (production calls
    `noroot_gate(os.geteuid(), ...)`) so the gate is unit-testable without actually being root — and is NOT
    bypassable from the environment (production always uses the real geteuid)."""
    if euid == 0:
        print("  [NOROOT] execution as root (uid 0) — REFUSED; run under a non-root USER, or a RUN_AS "
              "user / assumed-role identity (never root)")
        ledger["runs"].append({"ts": now(), "event": "root_refused", "euid": euid})
        json.dump(ledger, open(lpath, "w"), indent=2)
        raise SystemExit(9)


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

    # 2b. no-root gate — faithful execution under a non-root identity, never ambient root (before any bash)
    noroot_gate(os.geteuid(), ledger, lpath)

    # which steps — both paths validate against the script's own --list
    listing = subprocess.run(["bash", script, "--list"], capture_output=True, text=True).stdout
    rows = [ln.split("\t") for ln in listing.strip().splitlines() if ln.strip()]
    declared = [r[0].strip() for r in rows]
    step_tool = {r[0].strip(): r[1].strip() for r in rows if len(r) > 1}   # step -> tool, for snippet verify
    blessed, snip = _blessed_snippets(script)                              # {} / None for non-compiler scripts
    snip_verify = bool(snip and blessed and step_tool)
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
        # 3b. per-step snippet verification — re-hash THIS step's porter at time-of-USE, closing the gap
        #     between the agent's up-front registry verify and the run (a post-bless mutation of the perk
        #     source refuses EXACTLY this step, with expected-vs-found digests recorded as evidence)
        refuse, fname, want, found = snippet_decision(snip_verify, st, step_tool, blessed, snip)
        if refuse:
            print(f"  [SNIPPET] step {st} ({step_tool[st]}) snippet drift — REFUSED "
                  f"(expected {want[:16]}…, found {(found or 'MISSING')[:16]}…)")
            ledger["runs"].append({"ts": now(), "event": "snippet_refused", "step": str(st),
                                   "tool": step_tool[st], "file": fname, "expected": want, "found": found})
            json.dump(ledger, open(lpath, "w"), indent=2)
            sys.exit(8)
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
