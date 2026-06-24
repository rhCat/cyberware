#!/usr/bin/env python3
"""infra/store/reconcile.py — P5-T01: the continuous reconciler. The chained JSONL is the artifact of record;
the StoreBackend is a derived index. The reconciler re-derives the chain INDEPENDENTLY (read the chain file,
re-verify it, recompute every link digest via chainverify) and set-diffs it against the index, alarming on any
divergence the index could only show through loss, tamper, or lag-that-isn't-lag.

Divergence taxonomy (the index is mirrored chain-first, so it may trail but must never lead the chain):
  * index_behind  — a chain seq ABOVE the index head is not yet indexed. BENIGN: the backend is catching up
    after a crash (chain-first means a tail can be un-mirrored). `repair` re-applies it; never an alarm.
  * gap_below_head — a chain seq AT/BELOW the index head is missing from the index. ALARM: a deleted index row.
  * index_ahead   — the index has a seq the chain does not. ALARM: the index can never lead the chain.
  * digest_mismatch — a row's link_digest disagrees with the chain's recompute. ALARM: a tampered index row.
  * chain_broken  — verify_chain rejects the chain itself (tamper / transplant / seq gap). ALARM: never trust
    the index when the artifact of record is broken. The transplant guard re-asserts the OUT-OF-BAND expected
    origin (backend.get_origin) so a self-consistent forged genesis cannot reconcile clean.

A cycle's `ok` is False on ANY alarm class (index_behind alone is not an alarm). Injected divergence is caught
within ONE cycle because each cycle recomputes the chain digests from the file, sharing no state with the
index's write path.
"""
from __future__ import annotations
import time

from infra.cwp import chainverify
from infra.store import chainstore


def reconcile_run(backend, run_id, root, repair: bool = False) -> dict:
    """Reconcile ONE run's index against its chain (the artifact of record). Returns a structured verdict:
    {run_id, ok, chain_ok, divergences: [{class, seq, ...}], indexed, chain_len, repaired}."""
    cs = chainstore.ChainStore(root)
    entries, schema, trunc = cs.read_run(run_id)
    out = {"run_id": run_id, "ok": False, "chain_ok": False, "divergences": [],
           "indexed": 0, "chain_len": 0, "repaired": 0, "torn_tail": bool(trunc and trunc.get("was_torn"))}
    if not entries:
        out["divergences"].append({"class": "no_chain", "seq": None})
        return out

    # (1) the artifact of record must itself verify — and bind the OUT-OF-BAND expected origin (transplant guard)
    expect_plan = backend.get_origin(run_id)
    chain_ok, problems = chainverify.verify_chain(entries, schema, expect_run_id=run_id,
                                                  expect_plan_sha=expect_plan)
    out["chain_ok"] = chain_ok
    if not chain_ok:
        out["divergences"].append({"class": "chain_broken", "seq": None, "detail": problems[:2]})
        return out                                                # never trust the index over a broken chain

    # (2) recompute every record's link digest STRAIGHT FROM THE CHAIN (the independent oracle)
    chain_digest = {}                                             # seq -> link_digest, non-genesis records only
    for e in entries:
        ld = chainverify.link_digest(chainverify.link_of(e), schema)
        if e.get("type") != "genesis":
            chain_digest[e["seq"]] = ld
    out["chain_len"] = len(chain_digest)

    # (3) set-diff vs the index
    idx_rows = {r["seq"]: r for r in backend.rows(run_id)}
    out["indexed"] = len(idx_rows)
    index_head = max(idx_rows) if idx_rows else -1

    # the transplant guard is only meaningful with an OUT-OF-BAND expected origin. If the backend indexed rows
    # for this run it MUST have recorded the origin (govd sets it at create); a missing origin alongside indexed
    # rows means the origin row was lost/deleted — ALARM (else a forged genesis could reconcile clean).
    if expect_plan is None and idx_rows:
        out["divergences"].append({"class": "origin_missing", "seq": None})

    for seq, ld in sorted(chain_digest.items()):
        if seq in idx_rows:
            if idx_rows[seq]["link_digest"] != ld:
                out["divergences"].append({"class": "digest_mismatch", "seq": seq})
        elif seq <= index_head:
            out["divergences"].append({"class": "gap_below_head", "seq": seq})           # deleted index row
        else:
            out["divergences"].append({"class": "index_behind", "seq": seq})             # benign lag
            if repair:
                e = next(x for x in entries if x.get("seq") == seq)
                col = chainstore.record_columns(e)
                backend.index_record(col["run_id"], col["seq"], col["prev"], col["link_digest"],
                                     col["kind"], col["ts"], col["plan_sha"], col["fields"])
                out["repaired"] += 1
    for seq in idx_rows:
        if seq not in chain_digest:
            out["divergences"].append({"class": "index_ahead", "seq": seq})              # phantom index row

    alarm_classes = {"gap_below_head", "index_ahead", "digest_mismatch", "chain_broken", "origin_missing"}
    out["ok"] = not any(d["class"] in alarm_classes for d in out["divergences"])
    return out


# NOTE on a deliberate residual: deleting the index's TAIL row (the current max seq) is classified as benign
# index_behind (indistinguishable from not-yet-mirrored lag without a persisted high-water mark) and is
# self-healed by repair on the next cycle — the chain (artifact of record) is never lost. Deleting/altering any
# NON-tail row is caught (gap_below_head / digest_mismatch), as is a phantom row (index_ahead). The chain
# itself is fully tamper-checked by verify_chain every cycle, so the artifact of record is always protected.


def reconcile_all(backend, root, repair: bool = False) -> dict:
    """One reconcile CYCLE over every run the chain or the index knows. Returns {ok, cycle_runs, alarms:[...]}.
    `ok` is False iff ANY run alarms."""
    cs = chainstore.ChainStore(root)
    run_ids = sorted(set(cs.run_ids()) | set(backend.run_ids()))
    alarms = []
    for rid in run_ids:
        r = reconcile_run(backend, rid, root, repair=repair)
        if not r["ok"]:
            alarms.append(r)
    return {"ok": not alarms, "cycle_runs": len(run_ids), "alarms": alarms}


def continuous_reconcile(backend, root, interval: float = 5.0, cycles=None, stop=None,
                         repair: bool = False, sink=None) -> dict:
    """Loop reconcile_all every `interval` seconds. Stops after `cycles` cycles (if given) or when `stop()` is
    truthy. Each cycle's alarms are passed to `sink(cycle_index, result)` if provided. Returns a summary
    {cycles_run, divergence_seen, first_alarm_cycle}. This is the daemon govd starts; it only READS the chain
    + index and reports — it never mutates Store decision state."""
    cycles_run = 0
    first_alarm = None
    while True:
        try:
            res = reconcile_all(backend, root, repair=repair)
        except Exception as e:                               # a transient read error must NOT kill the daemon
            res = {"ok": False, "cycle_runs": 0,
                   "alarms": [{"run_id": "*", "divergences": [{"class": "reconcile_error",
                                                               "detail": str(e)[:200]}]}]}
        if sink:
            sink(cycles_run, res)
        if not res["ok"] and first_alarm is None:
            first_alarm = cycles_run
        cycles_run += 1
        if cycles is not None and cycles_run >= cycles:
            break
        if stop is not None and stop():
            break
        if cycles is None or cycles_run < cycles:
            time.sleep(interval)
    return {"cycles_run": cycles_run, "divergence_seen": first_alarm is not None,
            "first_alarm_cycle": first_alarm}
