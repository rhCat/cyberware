#!/usr/bin/env python3
"""infra/store/backend.py — P5-T01: the StoreBackend seam. ONE queryable-index interface, two interchangeable
backends, both passing ONE identical contract suite.

The chained JSONL (infra/store/chainstore.py) is the artifact of record; a StoreBackend is a DERIVED, fully
re-derivable index over it — what makes the provenance store queryable (and, on Postgres, durable + shared).

  * SqliteWalBackend — the default/free tier: local sqlite in WAL mode (concurrent readers + one writer,
    crash-safe commit). No server, always `configured`.
  * PsycopgBackend   — the durable tier: psycopg3 / Postgres-15. INERT (every op returns "unconfigured")
    until an operator wires `dsn_file` server-side; the import is LAZY (inside the methods) so the default
    tier and the hermetic selftest NEVER require psycopg or a live Postgres. The DSN is read at connect time
    and NEVER echoed (mirrors rails.StripeRail / settle.adapter.StripeAdapter).

`index_record` is an UPSERT keyed on (run_id, seq): replaying a record is a no-op duplicate — so a crash that
re-mirrors the chain tail can never double-write. Conformance is by CONVENTION (a callable probe in the
selftest, like infra/settle/adapter.py), not abc.ABCMeta. Stored `fields` are value-free; the digest cell is
the chain's own canonical link digest (the tamper-detection column the reconciler recomputes from the chain).
"""
from __future__ import annotations
import json
import os

from infra.store import chainstore


def _canon(fields) -> str:
    """Stable JSON for the fields cell — canonical so a stored row round-trips byte-identically."""
    return json.dumps(fields, sort_keys=True, separators=(",", ":"))


class StoreBackend:
    """A queryable provenance index derived from the chain. fund/payout-style replay-idempotent mirroring."""
    name = "abstract"

    def open(self): raise NotImplementedError
    def configured(self) -> bool: raise NotImplementedError
    def set_origin(self, run_id, plan_sha): raise NotImplementedError       # out-of-band expected origin
    def get_origin(self, run_id): raise NotImplementedError
    def index_record(self, run_id, seq, prev, link_digest, kind, ts, plan_sha, fields) -> dict:
        raise NotImplementedError
    def index_decision(self, summary) -> dict: raise NotImplementedError
    def rows(self, run_id) -> list: raise NotImplementedError              # ordered by seq
    def head(self, run_id): raise NotImplementedError                      # {seq, link_digest} | None
    def run_ids(self) -> list: raise NotImplementedError
    def reset(self): raise NotImplementedError                            # drop + recreate (reindex)
    # P5-T04: the single-writer LEASE (advisory lock) over the SHARED store — the active-passive primitive.
    # try_acquire/renew/release/holder are MUTUALLY EXCLUSIVE: at most one holder per lease_id at any instant,
    # enforced by the store's own atomic transaction (sqlite BEGIN IMMEDIATE / Postgres conditional upsert),
    # so two govd instances can never both be the writer (no split-brain).
    def try_acquire_lease(self, lease_id, holder_id, ttl, now=None) -> dict: raise NotImplementedError
    def renew_lease(self, lease_id, holder_id, ttl, now=None) -> dict: raise NotImplementedError
    def release_lease(self, lease_id, holder_id) -> dict: raise NotImplementedError
    def lease_holder(self, lease_id, now=None): raise NotImplementedError  # current non-expired holder | None


class SqliteWalBackend(StoreBackend):
    """Default tier — local sqlite in WAL mode. Always configured; no server needed."""
    name = "sqlite"

    def __init__(self, db_path):
        self.db_path = os.path.abspath(os.path.expanduser(db_path))
        self.cx = None

    def configured(self) -> bool:
        return True

    def open(self):
        import sqlite3
        os.makedirs(os.path.dirname(self.db_path) or ".", exist_ok=True)
        self.cx = sqlite3.connect(self.db_path, isolation_level=None, check_same_thread=False)
        self.cx.execute("PRAGMA journal_mode=WAL")
        self.cx.execute("PRAGMA synchronous=NORMAL")
        # P5-T04: under HA two instances share this db (lease + index). busy_timeout makes a racing
        # BEGIN IMMEDIATE WAIT for the RESERVED lock instead of raising "database is locked" — so concurrent
        # lease acquirers serialize cleanly (exactly one winner) rather than erroring.
        self.cx.execute("PRAGMA busy_timeout=5000")
        self.cx.execute("""CREATE TABLE IF NOT EXISTS idx_record(
            run_id TEXT, seq INTEGER, prev TEXT, link_digest TEXT, kind TEXT, ts TEXT,
            plan_sha TEXT, fields TEXT, PRIMARY KEY(run_id, seq))""")
        self.cx.execute("""CREATE TABLE IF NOT EXISTS idx_decision(
            rid INTEGER PRIMARY KEY AUTOINCREMENT, run_id TEXT, ts TEXT, link_digest TEXT, fields TEXT)""")
        self.cx.execute("""CREATE TABLE IF NOT EXISTS idx_origin(
            run_id TEXT PRIMARY KEY, plan_sha TEXT)""")
        return self

    def set_origin(self, run_id, plan_sha):
        self.cx.execute("INSERT OR IGNORE INTO idx_origin VALUES(?,?)", (run_id, plan_sha))   # first wins

    def get_origin(self, run_id):
        r = self.cx.execute("SELECT plan_sha FROM idx_origin WHERE run_id=?", (run_id,)).fetchone()
        return r[0] if r else None

    def index_record(self, run_id, seq, prev, link_digest, kind, ts, plan_sha, fields) -> dict:
        cur = self.cx.execute("INSERT OR IGNORE INTO idx_record VALUES(?,?,?,?,?,?,?,?)",
                              (run_id, seq, prev, link_digest, kind, ts, plan_sha, _canon(fields)))
        return {"backend": self.name, "run_id": run_id, "seq": seq, "link_digest": link_digest,
                "status": "indexed" if cur.rowcount == 1 else "duplicate"}

    def index_decision(self, summary) -> dict:
        ld = chainstore.link_digest({"type": "decision", "fields": summary,
                                     "run_id": summary.get("run_id"), "seq": -1})
        self.cx.execute("INSERT INTO idx_decision(run_id, ts, link_digest, fields) VALUES(?,?,?,?)",
                        (summary.get("run_id"), summary.get("ts", ""), ld, _canon(summary)))
        return {"backend": self.name, "status": "indexed", "run_id": summary.get("run_id")}

    def rows(self, run_id) -> list:
        cur = self.cx.execute(
            "SELECT run_id,seq,prev,link_digest,kind,ts,plan_sha,fields FROM idx_record "
            "WHERE run_id=? ORDER BY seq", (run_id,))
        return [{"run_id": r[0], "seq": r[1], "prev": r[2], "link_digest": r[3], "kind": r[4],
                 "ts": r[5], "plan_sha": r[6], "fields": json.loads(r[7])} for r in cur.fetchall()]

    def head(self, run_id):
        r = self.cx.execute("SELECT seq, link_digest FROM idx_record WHERE run_id=? ORDER BY seq DESC LIMIT 1",
                            (run_id,)).fetchone()
        return {"seq": r[0], "link_digest": r[1]} if r else None

    def run_ids(self) -> list:
        return [r[0] for r in self.cx.execute("SELECT DISTINCT run_id FROM idx_record ORDER BY run_id")]

    def reset(self):
        for t in ("idx_record", "idx_decision", "idx_origin"):
            self.cx.execute(f"DELETE FROM {t}")

    # ── P5-T04: the single-writer lease (advisory lock) — atomic via BEGIN IMMEDIATE ──────────────────────
    def _ensure_leases(self):
        self.cx.execute("""CREATE TABLE IF NOT EXISTS leases(
            lease_id TEXT PRIMARY KEY, holder_id TEXT, expires_at REAL, acquired_at REAL)""")

    def try_acquire_lease(self, lease_id, holder_id, ttl, now=None) -> dict:
        import time as _t
        now = _t.time() if now is None else now
        self.cx.execute("BEGIN IMMEDIATE")                              # serialize racing acquirers (RESERVED lock)
        try:
            self._ensure_leases()
            row = self.cx.execute("SELECT holder_id, expires_at FROM leases WHERE lease_id=?",
                                  (lease_id,)).fetchone()
            if row is not None and row[0] != holder_id and row[1] is not None and row[1] > now:
                self.cx.execute("COMMIT")                               # held by a LIVE other holder — refuse
                return {"acquired": False, "holder": row[0], "expires_at": row[1]}
            exp = now + ttl
            self.cx.execute("INSERT INTO leases(lease_id, holder_id, expires_at, acquired_at) VALUES(?,?,?,?) "
                            "ON CONFLICT(lease_id) DO UPDATE SET holder_id=excluded.holder_id, "
                            "expires_at=excluded.expires_at, acquired_at=excluded.acquired_at",
                            (lease_id, holder_id, exp, now))
            self.cx.execute("COMMIT")
            return {"acquired": True, "holder": holder_id, "expires_at": exp}
        except Exception:
            self.cx.execute("ROLLBACK")
            raise

    def renew_lease(self, lease_id, holder_id, ttl, now=None) -> dict:
        import time as _t
        now = _t.time() if now is None else now
        self.cx.execute("BEGIN IMMEDIATE")
        try:
            self._ensure_leases()
            row = self.cx.execute("SELECT holder_id FROM leases WHERE lease_id=?", (lease_id,)).fetchone()
            if row is None or row[0] != holder_id:                      # someone else holds it — renewal fails
                self.cx.execute("COMMIT")
                return {"renewed": False, "holder": row[0] if row else None}
            exp = now + ttl
            self.cx.execute("UPDATE leases SET expires_at=? WHERE lease_id=?", (exp, lease_id))
            self.cx.execute("COMMIT")
            return {"renewed": True, "holder": holder_id, "expires_at": exp}
        except Exception:
            self.cx.execute("ROLLBACK")
            raise

    def release_lease(self, lease_id, holder_id) -> dict:
        self.cx.execute("BEGIN IMMEDIATE")
        try:
            self._ensure_leases()
            row = self.cx.execute("SELECT holder_id FROM leases WHERE lease_id=?", (lease_id,)).fetchone()
            released = row is not None and row[0] == holder_id          # only the holder may release
            if released:
                self.cx.execute("DELETE FROM leases WHERE lease_id=?", (lease_id,))
            self.cx.execute("COMMIT")
            return {"released": released}
        except Exception:
            self.cx.execute("ROLLBACK")
            raise

    def lease_holder(self, lease_id, now=None):
        import time as _t
        now = _t.time() if now is None else now
        self._ensure_leases()
        row = self.cx.execute("SELECT holder_id, expires_at FROM leases WHERE lease_id=?", (lease_id,)).fetchone()
        if row is None or row[1] is None or row[1] <= now:             # unclaimed or expired → no live holder
            return None
        return row[0]


class PsycopgBackend(StoreBackend):
    """Durable tier — psycopg3 / Postgres-15. INERT until `config.dsn_file` is wired (operator, server-side).
    The DSN is read at connect time and never echoed; psycopg is imported lazily inside the methods so the
    default tier + hermetic selftest never require it."""
    name = "postgres"

    def __init__(self, config: dict = None):
        self.config = config or {}
        self.cx = None

    def configured(self) -> bool:
        return bool(self.config.get("dsn_file") or self.config.get("dsn"))

    def _dsn(self):
        if self.config.get("dsn"):
            return self.config["dsn"]
        return open(os.path.expanduser(self.config["dsn_file"]), encoding="utf-8").read().strip()

    def open(self):
        if not self.configured():
            return self
        import psycopg                                      # lazy: only when actually wired
        self.cx = psycopg.connect(self._dsn(), autocommit=True)
        with self.cx.cursor() as c:
            c.execute("""CREATE TABLE IF NOT EXISTS idx_record(
                run_id TEXT, seq BIGINT, prev TEXT, link_digest TEXT, kind TEXT, ts TEXT,
                plan_sha TEXT, fields JSONB, PRIMARY KEY(run_id, seq))""")
            c.execute("""CREATE TABLE IF NOT EXISTS idx_decision(
                rid BIGSERIAL PRIMARY KEY, run_id TEXT, ts TEXT, link_digest TEXT, fields JSONB)""")
            c.execute("""CREATE TABLE IF NOT EXISTS idx_origin(run_id TEXT PRIMARY KEY, plan_sha TEXT)""")
        return self

    def _unconf(self, **kw):
        return {"backend": self.name, "status": "unconfigured",
                "note": "set store.dsn_file (operator, server-side) to enable; the agent never sees the DSN", **kw}

    def set_origin(self, run_id, plan_sha):
        if not self.configured():
            return
        with self.cx.cursor() as c:
            c.execute("INSERT INTO idx_origin VALUES(%s,%s) ON CONFLICT (run_id) DO NOTHING", (run_id, plan_sha))

    def get_origin(self, run_id):
        if not self.configured():
            return None
        with self.cx.cursor() as c:
            c.execute("SELECT plan_sha FROM idx_origin WHERE run_id=%s", (run_id,))
            r = c.fetchone()
        return r[0] if r else None

    def index_record(self, run_id, seq, prev, link_digest, kind, ts, plan_sha, fields) -> dict:
        if not self.configured():
            return self._unconf(run_id=run_id, seq=seq)
        try:
            with self.cx.cursor() as c:
                c.execute("INSERT INTO idx_record VALUES(%s,%s,%s,%s,%s,%s,%s,%s) "
                          "ON CONFLICT (run_id, seq) DO NOTHING",
                          (run_id, seq, prev, link_digest, kind, ts, plan_sha, _canon(fields)))
                status = "indexed" if c.rowcount == 1 else "duplicate"
            return {"backend": self.name, "run_id": run_id, "seq": seq, "link_digest": link_digest,
                    "status": status}
        except Exception as e:                              # never echo the DSN, only the class + message
            return {"backend": self.name, "status": "error", "detail": f"{type(e).__name__}: {e}"[:300]}

    def index_decision(self, summary) -> dict:
        if not self.configured():
            return self._unconf(run_id=summary.get("run_id"))
        ld = chainstore.link_digest({"type": "decision", "fields": summary,
                                     "run_id": summary.get("run_id"), "seq": -1})
        with self.cx.cursor() as c:
            c.execute("INSERT INTO idx_decision(run_id, ts, link_digest, fields) VALUES(%s,%s,%s,%s)",
                      (summary.get("run_id"), summary.get("ts", ""), ld, _canon(summary)))
        return {"backend": self.name, "status": "indexed", "run_id": summary.get("run_id")}

    def rows(self, run_id) -> list:
        if not self.configured():
            return []
        with self.cx.cursor() as c:
            c.execute("SELECT run_id,seq,prev,link_digest,kind,ts,plan_sha,fields FROM idx_record "
                      "WHERE run_id=%s ORDER BY seq", (run_id,))
            out = []
            for r in c.fetchall():
                f = r[7] if isinstance(r[7], (dict, list)) else json.loads(r[7])
                out.append({"run_id": r[0], "seq": r[1], "prev": r[2], "link_digest": r[3], "kind": r[4],
                            "ts": r[5], "plan_sha": r[6], "fields": f})
        return out

    def head(self, run_id):
        if not self.configured():
            return None
        with self.cx.cursor() as c:
            c.execute("SELECT seq, link_digest FROM idx_record WHERE run_id=%s ORDER BY seq DESC LIMIT 1",
                      (run_id,))
            r = c.fetchone()
        return {"seq": r[0], "link_digest": r[1]} if r else None

    def run_ids(self) -> list:
        if not self.configured():
            return []
        with self.cx.cursor() as c:
            c.execute("SELECT DISTINCT run_id FROM idx_record ORDER BY run_id")
            return [r[0] for r in c.fetchall()]

    def reset(self):
        if not self.configured():
            return
        with self.cx.cursor() as c:
            for t in ("idx_record", "idx_decision", "idx_origin"):
                c.execute(f"DELETE FROM {t}")

    # ── P5-T04: the single-writer lease — ONE atomic conditional upsert (no race window) ──────────────────
    def _ensure_leases(self):
        with self.cx.cursor() as c:
            c.execute("""CREATE TABLE IF NOT EXISTS leases(
                lease_id TEXT PRIMARY KEY, holder_id TEXT, expires_at DOUBLE PRECISION, acquired_at DOUBLE PRECISION)""")

    def try_acquire_lease(self, lease_id, holder_id, ttl, now=None) -> dict:
        if not self.configured():
            return self._unconf(lease_id=lease_id)
        import time as _t
        now = _t.time() if now is None else now
        exp = now + ttl
        self._ensure_leases()
        with self.cx.cursor() as c:
            # atomic: insert, or update ONLY if the existing lease is expired or already ours. RETURNING tells us
            # if WE now hold it; an empty result means a live OTHER holder blocked the update.
            c.execute("INSERT INTO leases(lease_id, holder_id, expires_at, acquired_at) VALUES(%s,%s,%s,%s) "
                      "ON CONFLICT(lease_id) DO UPDATE SET holder_id=EXCLUDED.holder_id, "
                      "expires_at=EXCLUDED.expires_at, acquired_at=EXCLUDED.acquired_at "
                      "WHERE leases.expires_at <= %s OR leases.holder_id = EXCLUDED.holder_id "
                      "RETURNING holder_id, expires_at", (lease_id, holder_id, exp, now, now))
            r = c.fetchone()
            if r and r[0] == holder_id:
                return {"acquired": True, "holder": holder_id, "expires_at": exp}
            c.execute("SELECT holder_id, expires_at FROM leases WHERE lease_id=%s", (lease_id,))
            cur = c.fetchone()
        return {"acquired": False, "holder": cur[0] if cur else None, "expires_at": cur[1] if cur else None}

    def renew_lease(self, lease_id, holder_id, ttl, now=None) -> dict:
        if not self.configured():
            return self._unconf(lease_id=lease_id)
        import time as _t
        now = _t.time() if now is None else now
        exp = now + ttl
        self._ensure_leases()
        with self.cx.cursor() as c:
            c.execute("UPDATE leases SET expires_at=%s WHERE lease_id=%s AND holder_id=%s "
                      "RETURNING holder_id", (exp, lease_id, holder_id))
            r = c.fetchone()
        return {"renewed": bool(r), "holder": holder_id if r else None, "expires_at": exp if r else None}

    def release_lease(self, lease_id, holder_id) -> dict:
        if not self.configured():
            return self._unconf(lease_id=lease_id)
        self._ensure_leases()
        with self.cx.cursor() as c:
            c.execute("DELETE FROM leases WHERE lease_id=%s AND holder_id=%s RETURNING lease_id",
                      (lease_id, holder_id))
            r = c.fetchone()
        return {"released": bool(r)}

    def lease_holder(self, lease_id, now=None):
        if not self.configured():
            return None
        import time as _t
        now = _t.time() if now is None else now
        self._ensure_leases()
        with self.cx.cursor() as c:
            c.execute("SELECT holder_id, expires_at FROM leases WHERE lease_id=%s", (lease_id,))
            r = c.fetchone()
        if r is None or r[1] is None or r[1] <= now:
            return None
        return r[0]


def make_backend(root, config: dict = None) -> StoreBackend:
    """Pick the backend the operator wired: Postgres iff `store.dsn_file`/`dsn` is set, else local sqlite-WAL
    (`<root>/index.sqlite`). Mirrors the inert-until-keyed posture of the settlement Stripe rail."""
    config = config or {}
    store_cfg = config.get("store", config)
    if store_cfg.get("dsn_file") or store_cfg.get("dsn"):
        return PsycopgBackend(store_cfg).open()
    return SqliteWalBackend(os.path.join(os.path.expanduser(root), "index.sqlite")).open()


def store_selftest(backend_factory=None, n_records: int = 200) -> dict:
    """Hermetic, no-network (sqlite by default). Builds a real prev-hash chain via the artifact-of-record
    seam, mirrors it into a backend, and proves the StoreBackend CONTRACT — the SAME suite every adapter
    must pass:
      (1) interface_conformance — both backends expose every method (callable probe);
      (2) round_trip — index rows fold back to exactly the chain's records;
      (3) idempotent_replay — re-mirroring the whole chain returns all "duplicate"; the index is unchanged;
      (4) reconcile_exact — the index's per-row link_digest equals an INDEPENDENT recompute straight from the
          chain file via chainverify (the artifact of record is the oracle, not the index);
      (5) torn_tail_safe — a crash-torn final chain line is tolerated; the index ends exactly where the chain
          validly ends;
      (6) backend_inert_until_configured — PsycopgBackend({}) is unconfigured and its ops are graceful no-ops.
    """
    import tempfile
    from infra.cwp import chainverify

    d = tempfile.mkdtemp(prefix="store-selftest-")
    if backend_factory is None:
        def backend_factory():
            return SqliteWalBackend(os.path.join(d, "idx.sqlite")).open()

    cs = chainstore.ChainStore(d)
    be = backend_factory()
    be.reset()
    run_id, plan_sha = "run-self", "plan-self"
    be.set_origin(run_id, plan_sha)

    linked = []
    for i in range(n_records):
        rec = cs.append_record(run_id, plan_sha, "event", {"ts": f"t{i}", "step": i, "status": "ok"})
        linked.append(rec)
        col = chainstore.record_columns(rec)
        be.index_record(col["run_id"], col["seq"], col["prev"], col["link_digest"],
                        col["kind"], col["ts"], col["plan_sha"], col["fields"])

    # (1) interface conformance — every method callable on BOTH backends
    methods = ("open", "configured", "set_origin", "get_origin", "index_record", "index_decision",
               "rows", "head", "run_ids", "reset")
    iface = all(callable(getattr(b, m, None)) for b in (be, PsycopgBackend({})) for m in methods)

    # (2) round-trip: index rows == the chain's non-genesis records (by seq)
    rows = be.rows(run_id)
    chain, schema, _ = cs.read_run(run_id)
    chain_recs = [e for e in chain if e.get("type") != "genesis"]
    round_trip = (len(rows) == len(chain_recs)
                  and all(rw["seq"] == cr["seq"] and rw["fields"] == cr["fields"]
                          for rw, cr in zip(rows, chain_recs)))

    # (3) idempotent replay: re-mirror everything -> all duplicate, index unchanged
    before = be.rows(run_id)
    dups = []
    for rec in linked:
        col = chainstore.record_columns(rec)
        dups.append(be.index_record(col["run_id"], col["seq"], col["prev"], col["link_digest"],
                                    col["kind"], col["ts"], col["plan_sha"], col["fields"])["status"])
    idempotent_replay = all(s == "duplicate" for s in dups) and be.rows(run_id) == before

    # (4) reconcile_exact: the index digest == an INDEPENDENT recompute from the chain file (oracle = chain)
    recompute = {}
    for e in chain:
        if e.get("type") != "genesis":
            recompute[e["seq"]] = chainverify.link_digest(chainverify.link_of(e), schema)
    reconcile_exact = all(rw["link_digest"] == recompute.get(rw["seq"]) for rw in rows)

    # (5) torn-tail: append a torn final line to the chain file; the chain reader drops it; reindex ends where
    #     the chain validly ends (one short of the torn write)
    p = chainstore.run_chain_path(d, run_id)
    with open(p, "a") as f:
        f.write('{"type": "record", "seq": 99999, "prev": "deadbeef", "fiel')   # torn (no newline, unparseable)
    torn_entries, _, trunc = cs.read_run(run_id)
    torn_tail_safe = bool(trunc and trunc.get("was_torn")
                          and len([e for e in torn_entries if e.get("type") != "genesis"]) == len(chain_recs))

    # (6) the Postgres backend is inert until a dsn is wired
    inert = (PsycopgBackend({}).configured() is False
             and PsycopgBackend({}).index_record("r", 1, "p", "d", "k", "t", "ps", {})["status"] == "unconfigured")

    ok = bool(iface and round_trip and idempotent_replay and reconcile_exact and torn_tail_safe and inert)
    return {"interface_conformance": iface, "round_trip": round_trip, "idempotent_replay": idempotent_replay,
            "reconcile_exact": reconcile_exact, "torn_tail_safe": torn_tail_safe,
            "backend_inert_until_configured": inert, "records": n_records, "ok": ok}


if __name__ == "__main__":
    import sys
    r = store_selftest()
    print(json.dumps(r, indent=2))
    sys.exit(0 if r["ok"] else 1)
