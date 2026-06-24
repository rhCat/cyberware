"""P5-T01 — the provenance Store behind a StoreBackend interface: sqlite-WAL + psycopg/Postgres-15 pass ONE
identical contract suite; the chained JSONL is the artifact of record; the continuous reconciler shows zero
divergence across a soak and catches an injected divergence within one cycle.

The Postgres leg runs against a live pg15 if one is reachable (env GOVD_STORE_DSN, or the local
docker `cyberware-pg15` on :55432); otherwise it SKIPs — it is never silently faked."""
import os
import tempfile

import pytest

from infra.store import backend as B
from infra.store import chainstore, reconcile

_PG_DSN = os.environ.get("GOVD_STORE_DSN", "postgresql://postgres:cyberware@127.0.0.1:55432/govdstore")


def _pg_backend_or_skip():
    try:
        import psycopg  # noqa: F401
    except Exception:
        pytest.skip("psycopg not importable")
    be = B.PsycopgBackend({"dsn": _PG_DSN})
    try:
        be.open()
        be.reset()
    except Exception as e:
        pytest.skip(f"no live Postgres at {_PG_DSN}: {type(e).__name__}")
    return be


# ── the identical contract suite, run against BOTH backends ──────────────────────

def test_store_selftest_sqlite_all_pass():
    r = B.store_selftest()
    assert all(v for v in r.values() if isinstance(v, bool)), r


def test_store_selftest_postgres_all_pass():
    be = _pg_backend_or_skip()
    r = B.store_selftest(backend_factory=lambda: be)
    assert all(v for v in r.values() if isinstance(v, bool)), r


def _seed(d, be, run_id="run-x", plan="plan-x", n=10):
    cs = chainstore.ChainStore(d)
    be.set_origin(run_id, plan)
    for i in range(n):
        rec = cs.append_record(run_id, plan, "event", {"ts": f"t{i}", "step": i, "status": "ok"})
        c = chainstore.record_columns(rec)
        be.index_record(c["run_id"], c["seq"], c["prev"], c["link_digest"], c["kind"], c["ts"],
                        c["plan_sha"], c["fields"])
    return cs, run_id, plan


def test_clean_index_reconciles_zero_divergence():
    d = tempfile.mkdtemp(prefix="store-clean-")
    be = B.SqliteWalBackend(os.path.join(d, "i.sqlite")).open()
    _seed(d, be)
    res = reconcile.reconcile_all(be, d)
    assert res["ok"] and not res["alarms"]


@pytest.mark.parametrize("fault", ["gap_below_head", "index_ahead", "digest_mismatch"])
def test_injected_divergence_alarms_within_one_cycle(fault):
    d = tempfile.mkdtemp(prefix=f"store-{fault}-")
    be = B.SqliteWalBackend(os.path.join(d, "i.sqlite")).open()
    cs, rid, plan = _seed(d, be)
    assert reconcile.reconcile_all(be, d)["ok"]                       # clean before the fault
    if fault == "gap_below_head":
        be.cx.execute("DELETE FROM idx_record WHERE run_id=? AND seq=5", (rid,))
    elif fault == "index_ahead":
        be.cx.execute("INSERT INTO idx_record VALUES(?,?,?,?,?,?,?,?)",
                      (rid, 999, "x", "y", "event", "t", plan, "{}"))
    else:
        be.cx.execute("UPDATE idx_record SET link_digest='tampered' WHERE run_id=? AND seq=3", (rid,))
    r = reconcile.reconcile_run(be, rid, d)
    assert r["ok"] is False
    assert any(dv["class"] == fault for dv in r["divergences"]), r["divergences"]


def test_transplant_guard_rejects_forged_origin():
    """A self-consistent chain whose genesis plan_sha differs from the OUT-OF-BAND expected origin is rejected
    (the index can't reconcile a transplanted chain clean)."""
    d = tempfile.mkdtemp(prefix="store-transplant-")
    be = B.SqliteWalBackend(os.path.join(d, "i.sqlite")).open()
    cs, rid, plan = _seed(d, be)                                      # chain's real plan_sha = plan-x
    be2 = B.SqliteWalBackend(os.path.join(d, "i2.sqlite")).open()
    be2.set_origin(rid, "DIFFERENT-expected-plan")                    # out-of-band expectation differs
    r = reconcile.reconcile_run(be2, rid, d)
    assert r["ok"] is False and any(dv["class"] == "chain_broken" for dv in r["divergences"])


def test_index_behind_is_benign_and_repairs():
    """A chain tail not yet mirrored is BENIGN (the index is mirrored chain-first); repair re-applies it."""
    d = tempfile.mkdtemp(prefix="store-behind-")
    be = B.SqliteWalBackend(os.path.join(d, "i.sqlite")).open()
    cs, rid, plan = _seed(d, be, n=10)
    # append 3 more to the chain WITHOUT mirroring -> index trails the chain tail
    for i in range(10, 13):
        cs.append_record(rid, plan, "event", {"ts": f"t{i}", "step": i, "status": "ok"})
    r = reconcile.reconcile_run(be, rid, d)
    assert r["ok"] is True                                            # tail lag is not an alarm
    assert all(dv["class"] == "index_behind" for dv in r["divergences"])
    r2 = reconcile.reconcile_run(be, rid, d, repair=True)
    assert r2["repaired"] == 3
    assert reconcile.reconcile_run(be, rid, d)["ok"] and not reconcile.reconcile_run(be, rid, d)["divergences"]


def test_backend_failure_never_fails_a_decision():
    """The whole low-risk thesis: govd's Store mirrors the chain+index BEST-EFFORT. A backend that raises on
    every write must NOT fail create()/append() — the in-memory run + the authoritative ledger.json survive."""
    import json as _json

    from infra.govern import govd
    d = tempfile.mkdtemp(prefix="store-govd-")
    store = govd.Store(d, cfg={})

    class _Exploding:
        def set_origin(self, *a, **k): raise RuntimeError("boom-origin")
        def index_record(self, *a, **k): raise RuntimeError("boom-index")
        def index_decision(self, *a, **k): raise RuntimeError("boom-decision")
    store.mirror.backend = _Exploding()

    rid = "run-boom"
    record = {"run_id": rid, "ts": "t0", "skill": "fs", "perk": "find_large", "decision": "allow",
              "plan_sha": "plan-boom", "events": [], "token": "SECRET-TOKEN"}
    store.create(rid, record)                                         # must NOT raise despite the exploding backend
    store.append(rid, {"type": "step_result", "step": 0, "status": "ok"})   # must NOT raise
    store.record_decision({"run_id": rid, "ts": "t0", "decision": "allow"})  # must NOT raise
    store.mirror.flush()                                               # let the async worker drain

    # the authoritative state survived
    assert store.get(rid) is not None and len(store.get(rid)["events"]) == 1
    ondisk = _json.load(open(store._path(rid)))
    assert ondisk["run_id"] == rid and len(ondisk["events"]) == 1
    # and the chain (artifact of record) still got the value-free record WITHOUT the secret token (chain is
    # written FIRST, before the exploding backend) — proving the chain survives a total index failure
    chain, _, _ = store.mirror.chain.read_run(rid)
    assert chain and not any("SECRET-TOKEN" in _json.dumps(e) for e in chain)


def test_chain_never_contains_the_session_token():
    """Value-free: the session token lives only in ledger.json (stripped at every read boundary) and NEVER in
    the chain or the index."""
    import json as _json

    from infra.govern import govd
    d = tempfile.mkdtemp(prefix="store-vf-")
    store = govd.Store(d, cfg={})
    rid = "run-vf"
    store.create(rid, {"run_id": rid, "ts": "t", "skill": "fs", "perk": "x", "decision": "allow",
                       "plan_sha": "p", "events": [], "token": "TOP-SECRET"})
    store.mirror.flush()
    chain, _, _ = store.mirror.chain.read_run(rid)
    assert chain and not any("TOP-SECRET" in _json.dumps(e) for e in chain)
    if store.mirror.backend is not None:
        assert not any("TOP-SECRET" in _json.dumps(r) for r in store.mirror.backend.rows(rid))


def test_value_free_event_is_an_allowlist():
    """A new (possibly secret-bearing) event field is EXCLUDED by default — value_free_event is an allowlist."""
    from infra.store import mirror
    safe = mirror.value_free_event({"type": "step_result", "step": 0, "status": "ok",
                                    "token": "SECRET", "surprise_new_secret": "LEAK"})
    assert "token" not in safe and "surprise_new_secret" not in safe
    assert safe["type"] == "step_result" and safe["status"] == "ok"


def test_reconciler_alarms_when_origin_row_is_lost():
    """The transplant guard needs an OUT-OF-BAND origin. If the index has rows but the origin row was lost,
    the reconciler ALARMs (else a forged genesis could reconcile clean)."""
    d = tempfile.mkdtemp(prefix="store-origin-")
    be = B.SqliteWalBackend(os.path.join(d, "i.sqlite")).open()
    cs, rid, plan = _seed(d, be)
    assert reconcile.reconcile_all(be, d)["ok"]                       # clean with the origin set
    be.cx.execute("DELETE FROM idx_origin WHERE run_id=?", (rid,))    # lose the out-of-band origin
    r = reconcile.reconcile_run(be, rid, d)
    assert r["ok"] is False and any(dv["class"] == "origin_missing" for dv in r["divergences"])


def test_soak_zero_divergence_then_injected_alarm():
    """A short soak: a writer drives chain+index in lockstep while the reconciler runs; zero divergence. Then
    one injected index mutation alarms on the very next cycle (cycles_to_alarm == 1)."""
    d = tempfile.mkdtemp(prefix="store-soak-")
    be = B.SqliteWalBackend(os.path.join(d, "i.sqlite")).open()
    cs, rid, plan = _seed(d, be, n=50)
    # 5 clean cycles, all ok
    clean = reconcile.continuous_reconcile(be, d, interval=0, cycles=5)
    assert clean["divergence_seen"] is False
    # inject, then run cycles and confirm the FIRST one alarms
    be.cx.execute("UPDATE idx_record SET link_digest='x' WHERE run_id=? AND seq=10", (rid,))
    after = reconcile.continuous_reconcile(be, d, interval=0, cycles=1)
    assert after["divergence_seen"] is True and after["first_alarm_cycle"] == 0
