"""P5-T04 — active-passive govd over a single-writer advisory-lock lease.

The HA promise: exactly ONE active writer at a time over the shared store; a partitioned ex-active is fenced
out (split-brain impossible); a failover loses no work (zero duplicate grants, zero lost step_results); an
interrupted run is never orphaned. Proven hermetically — two in-process instances over ONE shared sqlite,
no live Postgres, a deterministic clock (injected `now`) so there are no sleeps."""
from __future__ import annotations

import os
import tempfile

from infra.govern import lease as L
from infra.store import backend as B
from infra.store import mirror as M


def _be():
    return B.SqliteWalBackend(os.path.join(tempfile.mkdtemp(prefix="ha-"), "index.sqlite")).open()


def test_lease_is_mutually_exclusive_no_split_brain():
    be = _be()
    a, b = L.LeaseManager(be, holder_id="A", ttl=10.0), L.LeaseManager(be, holder_id="B", ttl=10.0)
    t = 1000.0
    assert a.try_acquire(now=t) is True                       # A wins
    assert b.try_acquire(now=t + 1) is False                  # B cannot — A holds it (mutual exclusion)
    assert a.held(now=t + 1) is True and b.held(now=t + 1) is False
    assert be.lease_holder(L.ACTIVE_LEASE, now=t + 1) == "A"   # exactly one holder
    assert a.renew(now=t + 4) is True                         # A renews
    assert b.try_acquire(now=t + 5) is False                  # still A's


def test_concurrent_acquire_has_exactly_one_winner():
    """Mutual exclusion under REAL contention: N independent instances — each its OWN backend connection to the
    SAME shared db file (the real two-govd topology, NOT one shared connection) — fire try_acquire at once.
    BEGIN IMMEDIATE + busy_timeout serialize the racers so EXACTLY ONE wins; no split-brain."""
    import threading

    db = os.path.join(tempfile.mkdtemp(prefix="ha-race-"), "index.sqlite")
    B.SqliteWalBackend(db).open()                             # create the db + leases table once
    n = 12
    backends = [B.SqliteWalBackend(db).open() for _ in range(n)]   # SEPARATE connections == separate instances
    mgrs = [L.LeaseManager(be, holder_id=f"h{i}", ttl=100.0) for i, be in enumerate(backends)]
    barrier = threading.Barrier(n)
    lock = threading.Lock()
    results = []

    def racer(m):
        barrier.wait()                                        # line every thread up to fire simultaneously
        try:
            got = m.try_acquire(now=1000.0)
        except Exception as e:                                # a real bug would surface as an error, not silently
            got = ("err", type(e).__name__)
        with lock:
            results.append((m.holder_id, got))

    threads = [threading.Thread(target=racer, args=(m,)) for m in mgrs]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    winners = [h for h, got in results if got is True]
    assert len(winners) == 1, results                         # exactly one acquirer won the race — no split-brain
    assert backends[0].lease_holder(L.ACTIVE_LEASE, now=1000.0) == winners[0]


def test_lease_expiry_handoff_and_renew_denied_after_takeover():
    be = _be()
    a, b = L.LeaseManager(be, holder_id="A", ttl=10.0), L.LeaseManager(be, holder_id="B", ttl=10.0)
    t = 1000.0
    assert a.try_acquire(now=t)
    assert be.lease_holder(L.ACTIVE_LEASE, now=t + 100) is None   # A's lease expired (no renew)
    assert b.try_acquire(now=t + 100) is True                    # B takes over
    assert a.renew(now=t + 101) is False                         # A was fenced — its renewal is denied
    assert b.held(now=t + 101) is True
    assert b.release() is True and be.lease_holder(L.ACTIVE_LEASE, now=t + 102) is None


def test_only_the_holder_may_release():
    be = _be()
    a, b = L.LeaseManager(be, holder_id="A", ttl=10.0), L.LeaseManager(be, holder_id="B", ttl=10.0)
    assert a.try_acquire(now=1000.0)
    assert b.release() is False                               # B is not the holder — release is a no-op
    assert a.held(now=1000.0) is True
    assert a.release() is True


def test_mirror_single_writer_gate_blocks_a_non_holder_and_records_the_attempt():
    """The split_brain enforcement: a writer WITHOUT the lease may not touch the shared artifact of record. Its
    write is dropped and the attempt is recorded — so a partitioned ex-active cannot append behind the back of
    the new active."""
    root = tempfile.mkdtemp(prefix="ha-gate-")
    cfg = {}
    be = B.SqliteWalBackend(os.path.join(root, "index.sqlite")).open()
    holder = L.LeaseManager(be, holder_id="active", ttl=10.0)
    assert holder.try_acquire(now=5000.0)

    active = M.StoreMirror(root, cfg)
    standby = M.StoreMirror(root, cfg)
    active.set_lease_guard(lambda: holder.held(now=5000.0))
    standby.set_lease_guard(lambda: False)                    # the standby holds no lease — every write is gated

    active.record_run("r1", {"plan_sha": "p", "skill": "x", "perk": "y", "decision": "allow"})
    active.record_event("r1", "p", {"type": "step_result", "step": "1", "status": "ok", "exit": 0, "ts": "t"})
    standby.record_event("r1", "p", {"type": "step_result", "step": "1", "status": "ok", "exit": 0, "ts": "tX"})
    standby.record_event("r1", "p", {"type": "granted", "step": "1", "ts": "tX"})
    active.flush(); standby.flush()

    from infra.store import chainstore as CS
    rows, _, _ = CS.ChainStore(root).read_run("r1")
    body = [r for r in rows if r.get("type") != "genesis"]
    assert len(body) == 2                                     # only the active's 2 records; the standby's were blocked
    assert standby.blocked == 2 and active.blocked == 0
    assert os.path.isfile(os.path.join(root, "split-brain-attempts.jsonl"))  # the attempts were recorded


def test_ha_selftest_all_pass():
    r = L.ha_selftest()
    assert r["ok"], r
    assert r["split_brain"] and r["failover_drill"] and r["no_orphaned_run"] and r["lease_lifecycle"]
    assert r["blocked_split_writes"] == 2


def test_maybe_enable_ha_is_off_by_default():
    """No `ha` config ⇒ no lease, no gate — the single-node path is unchanged (no regression)."""
    class _FakeStore:
        class mirror:
            @staticmethod
            def enabled():
                return True
    assert L.maybe_enable_ha({}, _FakeStore()) is None
    assert L.maybe_enable_ha({"ha": {"enabled": False}}, _FakeStore()) is None


def test_acquire_blocking_times_out_on_a_held_lease():
    """A standby that cannot get the lease within the timeout returns False (it stays a standby) — a virtual
    clock drives the poll, so the test does not actually sleep."""
    be = _be()
    incumbent = L.LeaseManager(be, holder_id="incumbent", ttl=100.0)
    assert incumbent.try_acquire(now=0.0)
    clock = {"t": 0.0}

    def now_fn():
        return clock["t"]

    def sleep(dt):
        clock["t"] += dt

    standby = L.LeaseManager(be, holder_id="standby", ttl=100.0)
    assert standby.acquire_blocking(timeout=5.0, poll=1.0, now_fn=now_fn, sleep=sleep) is False
    # once the incumbent's lease expires, the standby acquires on the next poll
    incumbent_expiry_clock = {"t": 200.0}
    assert standby.acquire_blocking(timeout=5.0, poll=1.0,
                                    now_fn=lambda: incumbent_expiry_clock["t"], sleep=sleep) is True
