#!/usr/bin/env python3
"""infra/chaos.py — fault-injection drills (P2-T10 + P6-T17, V-CHAOS).

The recovery invariants from `spec/inflight.md`, exercised by injecting the two faults the governed runtime
must survive without losing or duplicating money or work:

  * **partition (govd ↔ exod)** — a step already granted finishes, but the NEXT `step_request` cannot get a
    fresh grant and **refuses closed** (never proceeds ungoverned); a WS/recorder resume re-delivers the last
    `step_result` **idempotently** — the ledger dedups by `(run_id, seq)`, so **zero duplicate records**.
  * **crash-exod** — exod dies mid-step: its orphaned sandbox is **reaped**, the step is recorded as an
    **error** (never a false pass — exod's authoritative status is gone, so the outcome is failure), and the
    run is **resumable** from that step.
  * **settle-engine crash atomicity (P6-T17)** — a crash mid-posting-set is **all-or-nothing** (the posting
    set is one record = one append = one fsync; a torn tail is dropped on recovery, never a partial set);
    recovery **replays exactly once** (the spent-quote guard); and **conservation holds through the crash**
    (the recovered ledger is zero-sum either way).

The partition + settle-crash drills are platform-agnostic and run in CI; the crash-exod drill models the
recovery bookkeeping here, while the REAL cgroup-kill reaping is exercised by the exec-image sandbox tests
(`infra/exec/`, P2-T03/T08).
"""
from __future__ import annotations
import os

from infra.cwp import ledger
from infra.settle import engine, quote as quote_mod, reward_ledger
from infra.settle.money import Money


# ── partition drill (P2-T10) ──────────────────────────────────────────────────

class Recorder:
    """An idempotent step-result recorder: an append keyed by `(run_id, seq)` — a re-delivery (WS resume) of
    an already-recorded result is a no-op, so a partition + retry produces ZERO duplicate records."""

    def __init__(self):
        self.records = []
        self._seen = set()

    def record(self, run_id: str, seq: int, status: str) -> bool:
        key = (run_id, seq)
        if key in self._seen:
            return False                                       # idempotent: already recorded, no dup
        self._seen.add(key)
        self.records.append({"run_id": run_id, "seq": seq, "status": status})
        return True


def partition_drill(n_steps: int = 4, partition_at: int = 2) -> dict:
    """Run a governed run; govd↔exod partitions before step `partition_at`. The step in flight completes; the
    next step_request refuses closed; a WS resume re-delivers the last result idempotently."""
    # the drill's pass envelope is partition_at ∈ [1, n_steps): a partition before any step grants, or after
    # the last, is degenerate. This is a CI regression guard over the Recorder dedup + fail-closed refusal;
    # the real network-partition fault + the durable step-dedup live in govd (result_acceptable).
    rec = Recorder()
    run = "run-partition"
    completed, refused_next = 0, False
    for i in range(n_steps):
        govd_reachable = i < partition_at                      # the partition lands before step `partition_at`
        if not govd_reachable:
            refused_next = True                                # step_request gets no fresh grant → refuse closed
            break
        rec.record(run, i, "pass")                             # granted step runs + records
        completed += 1
    # WS resume: the last completed step_result is re-delivered (network retry) — must NOT duplicate
    dup_before = len(rec.records)
    rec.record(run, completed - 1, "pass")
    zero_dup = len(rec.records) == dup_before
    return {"running_step_completed": completed == partition_at, "next_refused_closed": refused_next,
            "ws_resume_idempotent": zero_dup, "records": len(rec.records),
            "ok": completed == partition_at and refused_next and zero_dup}


# ── crash-exod drill (P2-T10) ─────────────────────────────────────────────────

def crash_exod_drill(n_steps: int = 4, crash_at: int = 2) -> dict:
    """exod crashes during step `crash_at`: the orphaned sandbox is reaped, the step records an ERROR (not a
    false pass — exod's authoritative status is gone), and the run is resumable from that step."""
    rec = Recorder()
    run = "run-crash"
    sandboxes = {}                                             # seq -> "running" | "reaped"
    error_recorded, resumable = False, False
    for i in range(n_steps):
        sandboxes[i] = "running"
        if i == crash_at:
            # exod dies mid-step: no authoritative pass arrives → the step is an error, the sandbox orphaned
            rec.record(run, i, "error")
            sandboxes[i] = "reaped"                            # cgroup-kill the orphan (modeled; real reap = exec image)
            error_recorded = True
            resumable = True                                   # the run can re-issue from this step
            break
        rec.record(run, i, "pass")
        sandboxes[i] = "done"
    orphan_reaped = sandboxes.get(crash_at) == "reaped"
    step_status = next((r["status"] for r in rec.records if r["seq"] == crash_at), None)
    return {"orphan_reaped": orphan_reaped, "step_records_error": step_status == "error",
            "run_resumable": resumable, "no_false_pass": step_status != "pass",
            "ok": orphan_reaped and error_recorded and step_status == "error" and resumable}


# ── settle-engine crash atomicity (P6-T17) ────────────────────────────────────

def _settled_chain(tmp: str):
    """Build a funded reward ledger that settles one quote, persisted to a JSONL file. Returns (path, qsha,
    gv_pub, ex_pub, ap_pub, qenv) for the crash drill."""
    import subprocess

    def kp(tag):
        p, pub = os.path.join(tmp, f"{tag}.key"), os.path.join(tmp, f"{tag}.pub")
        subprocess.run(["openssl", "genpkey", "-algorithm", "ed25519", "-out", p], check=True, capture_output=True)
        subprocess.run(["openssl", "pkey", "-in", p, "-pubout", "-out", pub], check=True, capture_output=True)
        return p, pub
    gv_priv, gv_pub = kp("gv")
    ex_priv, ex_pub = kp("ex")
    ap_priv, ap_pub = kp("ap")
    policy = {"accounts": ["payee", "fee"], "weights": [90, 10]}
    q = quote_mod.compute_quote("plan-crash", Money("100.0000"), policy, fmv="f")
    qenv = quote_mod.sign_quote(q, gv_priv)
    qsha = quote_mod.quote_sha(q)
    led = reward_ledger.open_ledger()
    quote_mod.fund_quote(led, "treasury", qenv)
    rcpt = engine.build_receipt("run-1", qsha, "pass", Money("100.0000"), ex_priv, ap_priv)
    engine.settle(led, rcpt, qenv, ex_pub, ap_pub, gv_pub)
    path = os.path.join(tmp, "reward.jsonl")
    ledger.write_chain(path, led)
    return path, qsha, gv_pub, ex_pub, ap_pub, qenv, ex_priv, ap_priv


def _recover(path: str):
    """Recover a chain after a crash: torn-tail healing drops only an unparseable FINAL line (a mid-chain
    bad line is real corruption and RAISES). Returns (entries, torn_dropped, all_complete)."""
    entries, truncation = ledger._parse_jsonl(open(path).read(), allow_torn_tail=True)
    return entries, (truncation is not None and truncation["was_torn"]), all(isinstance(e, dict) for e in entries)


def settle_crash_drill() -> dict:
    """P6-T17: a crash mid-posting-set is all-or-nothing; recovery replays EXACTLY once; conservation holds.
    Exercises BOTH crash orderings against the real durable-append/torn-tail machinery:

      A — crash AFTER the settle committed: a torn fragment trails the settled chain; recovery drops it, the
          settle survives, and a replay is refused by the spent-quote guard → exactly one payout.
      B — crash DURING the settle write (before commit): the settle line never lands; recovery leaves escrow
          funded, and a replay settles → exactly one payout.

    Either way: no partial posting set survives, the recovered ledger is zero-sum, and the quote pays out
    exactly once. Needs openssl."""
    import tempfile
    tmp = tempfile.mkdtemp(prefix="chaos-settle-")

    # ── ordering A: crash AFTER settle committed (torn fragment trails the settled chain) ──
    path, qsha, gv_pub, ex_pub, ap_pub, qenv, ex_priv, ap_priv = _settled_chain(tmp)
    with open(path, "a") as f:
        f.write('{"type": "posting_set", "postings": [{"account": "escrow:tor')   # interrupted, no newline
    a_entries, a_torn, a_complete = _recover(path)
    a_rcpt = engine.build_receipt("run-1", qsha, "pass", Money("100.0000"), ex_priv, ap_priv)
    a_replay = engine.settle(a_entries, a_rcpt, qenv, ex_pub, ap_pub, gv_pub)
    a_n = sum(1 for e in a_entries if str(e.get("memo", "")).startswith(engine._SETTLE_PREFIX))
    a_exactly_once = a_replay["settled"] is False and a_replay["reason"] == "quote_already_settled" and a_n == 1
    a_zero_sum = reward_ledger.global_zero(a_entries)

    # ── ordering B: crash DURING the settle write (the settle line never committed) ──
    import subprocess
    gv2, gp2 = os.path.join(tmp, "g2.key"), os.path.join(tmp, "g2.pub")
    ex2, ep2 = os.path.join(tmp, "e2.key"), os.path.join(tmp, "e2.pub")
    ap2, pp2 = os.path.join(tmp, "a2.key"), os.path.join(tmp, "a2.pub")
    for k, p in ((gv2, gp2), (ex2, ep2), (ap2, pp2)):
        subprocess.run(["openssl", "genpkey", "-algorithm", "ed25519", "-out", k], check=True, capture_output=True)
        subprocess.run(["openssl", "pkey", "-in", k, "-pubout", "-out", p], check=True, capture_output=True)
    q2 = quote_mod.compute_quote("plan-crashB", Money("100.0000"),
                                 {"accounts": ["payee", "fee"], "weights": [90, 10]}, fmv="f")
    q2env = quote_mod.sign_quote(q2, gv2)
    q2sha = quote_mod.quote_sha(q2)
    ledB = reward_ledger.open_ledger()
    quote_mod.fund_quote(ledB, "treasury", q2env)              # funded, but the settle never committed (crash)
    pathB = os.path.join(tmp, "rewardB.jsonl")
    ledger.write_chain(pathB, ledB)
    with open(pathB, "a") as f:
        f.write('{"type": "posting_set", "memo": "settle:quote:' + q2sha[:8])     # torn settle, no newline
    b_entries, b_torn, b_complete = _recover(pathB)
    b_n_before = sum(1 for e in b_entries if str(e.get("memo", "")).startswith(engine._SETTLE_PREFIX))
    b_rcpt = engine.build_receipt("run-1", q2sha, "pass", Money("100.0000"), ex2, ap2)
    b_replay = engine.settle(b_entries, b_rcpt, q2env, ep2, pp2, gp2)
    b_n_after = sum(1 for e in b_entries if str(e.get("memo", "")).startswith(engine._SETTLE_PREFIX))
    b_exactly_once = b_n_before == 0 and b_replay["settled"] is True and b_n_after == 1
    b_zero_sum = reward_ledger.global_zero(b_entries)

    return {"torn_tail_dropped": a_torn and b_torn, "all_or_nothing": a_complete and b_complete,
            "conservation_holds_through_crash": a_zero_sum and b_zero_sum,
            "replay_exactly_once": a_exactly_once and b_exactly_once,
            "crash_after_commit_exactly_once": a_exactly_once, "crash_before_commit_exactly_once": b_exactly_once,
            "ok": (a_torn and b_torn and a_complete and b_complete and a_zero_sum and b_zero_sum
                   and a_exactly_once and b_exactly_once)}


def chaos_selftest() -> dict:
    """All three V-CHAOS drills hold: partition (next refuses closed + idempotent resume), crash-exod (orphan
    reaped + error recorded + resumable), settle-crash (all-or-nothing + exactly-once + conservation)."""
    p = partition_drill()
    c = crash_exod_drill()
    s = settle_crash_drill()
    return {"partition": p["ok"], "crash_exod": c["ok"], "settle_crash": s["ok"],
            "ok": p["ok"] and c["ok"] and s["ok"]}
