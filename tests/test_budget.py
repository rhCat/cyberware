"""Per-actor CREDIT budget — the gauge + the pricing-stage shutoff. Tests mirror test_credits / test_fleetd:
the PURE gate decision (budget_ok), the actor-keyed ledger, the ATOMIC store debit (incl. a concurrency
race), the negotiable credit pricing, the float-ban, and the govern-gate integration (exhaust -> shutoff,
a rejected claim consumes nothing, an un-budgeted actor under enforcement -> reject)."""
from __future__ import annotations
import os
import tempfile
import threading

import pytest

from infra.settle import budget, credit_price, reward_ledger
from infra.settle.money import Money
from infra.store.backend import SqliteWalBackend

C = lambda s: Money(s, "CREDITS")


# ── the pure gate decision (no I/O — like principals.acl_allows) ──
def test_budget_ok_table():
    assert budget.budget_ok("a", C("1.0000"), C("5.0000"), configured=True) == (True, None)
    assert budget.budget_ok("a", C("5.0000"), C("5.0000"), configured=True) == (True, None)   # exact fit allowed
    ok, p = budget.budget_ok("a", C("6.0000"), C("5.0000"), configured=True)                  # over -> shutoff
    assert ok is False and p["id"] == "insufficient_credits"
    ok, p = budget.budget_ok("a", C("1.0000"), None, configured=True)                         # unreadable -> closed
    assert ok is False and p["id"] == "budget_unavailable"
    ok, p = budget.budget_ok("a", C("1.0000"), None, configured=False)                        # no budget -> closed
    assert ok is False and p["id"] == "budget_unmetered"


# ── the actor-keyed credit ledger (in-memory posting form + selftest) ──
def test_budget_ledger_seed_debit_topup():
    led = reward_ledger.open_ledger()
    budget.seed(led, "alice", C("5.0000"))
    assert budget.balance(led, "alice") == C("5.0000")
    assert budget.seed(led, "alice", C("5.0000"))["status"] == "duplicate"          # seed idempotent
    assert budget.debit(led, "alice", C("2.0000"), "P1")["status"] == "debited"
    assert budget.debit(led, "alice", C("2.0000"), "P1")["status"] == "duplicate"   # debit idempotent on idem
    assert budget.balance(led, "alice") == C("3.0000")
    assert budget.debit(led, "alice", C("9.0000"), "P2")["status"] == "insufficient_credits"  # over -> refused
    assert budget.balance(led, "alice") == C("3.0000")                              # untouched on refusal
    budget.topup(led, "alice", C("3.0000"), source="grant", ref="g1")
    assert budget.balance(led, "alice") == C("6.0000")
    assert reward_ledger.global_zero(led)                                           # double-entry stays zero-sum


def test_budget_selftest_passes():
    r = budget.budget_selftest()
    assert all(r.values()), r


def test_configured_allowance_resolves_credits_or_budget():
    # govd's budget_configured gate counts EITHER `credits` or `budget`; the seeder MUST resolve both or a
    # `budget:`-keyed actor is metered-but-unseeded (locked out at 0). (review-followup regression.)
    assert budget.configured_allowance({"credits": "5.0000"}) == "5.0000"
    assert budget.configured_allowance({"budget": "7.0000"}) == "7.0000"        # the seed gap the review caught
    assert budget.configured_allowance({"credits": "5.0000", "budget": "9"}) == "5.0000"   # credits wins
    assert budget.configured_allowance({"rate": 10.0}) is None                  # no allowance -> unmetered
    assert budget.configured_allowance(None) is None and budget.configured_allowance("x") is None


def test_topup_requires_a_unique_ref():
    # an empty ref is a money-safety hazard (silently collapse OR double-credit) -> REFUSED; distinct refs both
    # land; a repeated ref is an idempotent no-op. (review-followup regression.)
    led = reward_ledger.open_ledger()
    budget.seed(led, "alice", C("1.0000"), ref="s1")
    r = budget.topup(led, "alice", C("3.0000"), ref="")                         # empty ref -> refused, no posting
    assert r["status"] == "error" and r["error"] == "ref_required"
    assert budget.balance(led, "alice") == C("1.0000")                          # balance untouched
    assert budget.topup(led, "alice", C("3.0000"), ref="g1")["status"] == "credited"
    assert budget.topup(led, "alice", C("3.0000"), ref="g1")["status"] == "duplicate"   # same ref -> no-op
    assert budget.topup(led, "alice", C("2.0000"), ref="g2")["status"] == "credited"    # distinct ref lands
    assert budget.balance(led, "alice") == C("6.0000")                          # 1 + 3 (g1) + 2 (g2)
    assert reward_ledger.global_zero(led)


# ── the durable, ATOMIC store debit ──
def _backend():
    return SqliteWalBackend(os.path.join(tempfile.mkdtemp(), "idx.sqlite")).open()


def test_backend_balance_post_debit_idempotent():
    be = _backend()
    assert be.budget_balance("a").amount == C("0").amount
    be.budget_post("a", C("5.0000"), "seed:a", "seed:a")
    assert be.budget_post("a", C("5.0000"), "seed:a", "seed:a")["status"] == "duplicate"   # post idempotent
    assert be.budget_balance("a") == C("5.0000")
    assert be.budget_debit_atomic("a", C("2.0000"), "usage:r1")["ok"] is True
    assert be.budget_debit_atomic("a", C("2.0000"), "usage:r1").get("duplicate") is True   # debit idempotent
    assert be.budget_debit_atomic("a", C("99.0000"), "usage:r2")["ok"] is False            # over -> refused
    assert be.budget_balance("a") == C("3.0000")


def test_backend_debit_is_atomic_under_concurrency():
    # balance fits exactly ONE 2-credit debit; 16 threads race distinct idems -> exactly one wins, never negative
    be = _backend()
    be.budget_post("a", C("2.0000"), "seed:a", "seed:a")
    wins = []
    lock = threading.Lock()

    def race(i):
        r = be.budget_debit_atomic("a", C("2.0000"), f"usage:r{i}")
        if r["ok"] and not r.get("duplicate"):
            with lock:
                wins.append(i)
    ts = [threading.Thread(target=race, args=(i,)) for i in range(16)]
    [t.start() for t in ts]
    [t.join() for t in ts]
    assert len(wins) == 1                                  # exactly one debit succeeded
    assert be.budget_balance("a") == C("0.0000")           # never over-spent


def test_backend_idem_is_actor_scoped_no_cross_actor_freebie():
    # the same idem under TWO actors must BOTH charge — a cross-actor idem collision must not be a "duplicate"
    # no-op (which would have skipped the balance check and granted a free run).
    be = _backend()
    be.budget_post("a", C("5.0000"), "seed:a", "seed:a")
    be.budget_post("b", C("5.0000"), "seed:b", "seed:b")
    assert be.budget_debit_atomic("a", C("2.0000"), "usage:X")["ok"] is True
    rb = be.budget_debit_atomic("b", C("2.0000"), "usage:X")            # SAME idem, different actor
    assert rb["ok"] is True and not rb.get("duplicate")                # b is genuinely charged, not a no-op
    assert be.budget_balance("a") == C("3.0000") and be.budget_balance("b") == C("3.0000")
    # a TRUE retry (same actor + idem) is still idempotent
    assert be.budget_debit_atomic("a", C("2.0000"), "usage:X").get("duplicate") is True
    assert be.budget_balance("a") == C("3.0000")


# ── negotiable credit pricing ──
def test_credit_price_resolution():
    assert credit_price.credit_price("general:fs", "archive").currency == "CREDITS"
    assert credit_price.credit_price("general:fs", "archive") == C("2.0000")        # operator leaf/perk override
    assert credit_price.credit_price("http", "post") == C("2.0000")                 # operator skill/perk override
    assert credit_price.credit_price("general:fs", "find_large") == C("1.0000")     # _default
    assert credit_price.credit_price("zzz:nope", "x") == C("1.0000")                # unknown -> _default
    # an explicit pricing dict: namespace key + skill-leaf override + _default fallback
    pricing = {"credit_prices": {"_default": "1.0000", "cws": "5.0000", "fs/find_large": "3.0000"}}
    assert credit_price.credit_price("cws:cws-deploy", "serve", pricing) == C("5.0000")    # namespace default
    assert credit_price.credit_price("general:fs", "find_large", pricing) == C("3.0000")   # leaf/perk override
    assert credit_price.credit_price("general:markdown", "render", pricing) == C("1.0000") # _default


# ── the float-ban (these live under infra/settle/) ──
def test_no_float_in_budget_modules():
    from infra.settle.money import float_ban_scan
    assert float_ban_scan([budget.__file__, credit_price.__file__]) == []


# ── govern-gate integration: exhaust -> shutoff; rejected claim consumes nothing; unmetered actor closed ──
@pytest.fixture
def chip_env():
    os.environ.setdefault("CYBERWARE_SKILLCHIP", os.path.abspath("skillChip"))
    if not os.path.isfile(os.path.join("skillChip", "index.json")):
        pytest.skip("chip manifest absent")


def test_gate_exhausts_to_shutoff_and_rejects_consume_nothing(chip_env):
    from infra.govern import govd
    be = _backend()
    be.budget_post("alice", C("3.0000"), "seed:alice", "seed:alice")
    cfg = {"mode": "remote", "budget_enforce": True}
    ledger = {"skill": "fs", "perk": "find_large", "var_keys": ["SEARCH_DIR"]}   # price 1.0

    def claim(run):
        bal = be.budget_balance("alice")
        v = govd.govern(ledger, cfg, scope={"skills": ["fs"]}, principal="alice",
                        budget_enforce=True, budget_balance=bal, budget_configured=True)
        if v["decision"] == "allow" and v.get("cost"):
            if not be.budget_debit_atomic("alice", C(v["cost"]), "usage:" + run)["ok"]:
                return "reject"
        return v["decision"]

    decs = [claim(f"r{i}") for i in range(4)]
    assert decs == ["allow", "allow", "allow", "reject"]            # 3 fit, the 4th is the shutoff
    assert be.budget_balance("alice") == C("0.0000")

    # a missing-input claim rejects BEFORE the budget gate -> cost None, nothing consumed
    be.budget_post("bob", C("2.0000"), "seed:bob", "seed:bob")
    v = govd.govern({"skill": "fs", "perk": "find_large", "var_keys": []}, cfg,
                    scope={"skills": ["fs"]}, principal="bob",
                    budget_enforce=True, budget_balance=be.budget_balance("bob"), budget_configured=True)
    assert v["decision"] == "reject" and v.get("cost") is None
    assert "missing_input" in [p.get("id") for p in v["problems"]]
    assert be.budget_balance("bob") == C("2.0000")                 # untouched


def test_gate_unmetered_actor_rejected_under_enforcement(chip_env):
    from infra.govern import govd
    v = govd.govern({"skill": "fs", "perk": "find_large", "var_keys": ["SEARCH_DIR"]},
                    {"mode": "remote", "budget_enforce": True}, scope={"skills": ["fs"]},
                    principal="nobudget", budget_enforce=True, budget_balance=None, budget_configured=False)
    assert v["decision"] == "reject" and "budget_unmetered" in [p.get("id") for p in v["problems"]]


# ── live HTTP: exhaust -> 403 shutoff, then a monitor-gated /budget/topup restores allow (no restart) ──
def test_live_shutoff_then_topup_restores_allow(chip_env, tmp_path):
    import json
    import threading
    import time
    import urllib.error
    import urllib.request
    from infra.govern import govd
    from infra.govern import principals as P
    from infra.store.backend import make_backend
    from infra.settle.price import load_pricing

    root = str(tmp_path / "ledger")
    cfg = govd.load_config()
    cfg.update({"mode": "local", "local": {"host": "127.0.0.1", "ports": [0]}, "record_root": root,
                "budget_enforce": True, "monitor_token": "admin", "pricing": load_pricing(),
                "principals": {"alice": {"token_sha": P.token_sha("ALICE"), "rate": 100.0, "burst": 100.0,
                                         "credits": "2.0000", "acl": {"skills": ["fs"]}}}})
    be = make_backend(root, cfg)
    be.budget_post("alice", C("2.0000"), "seed:alice", "seed:alice")          # 2 credits, price 1.0 -> 2 allows
    httpd, _ = govd.bind_server("127.0.0.1", [0])
    httpd.daemon_threads = True
    httpd.cfg, httpd.store, httpd.store_backend, httpd.rate_buckets = cfg, govd.Store(root), be, {}
    threading.Thread(target=httpd.serve_forever, kwargs={"poll_interval": 0.02}, daemon=True).start()
    base = f"http://127.0.0.1:{httpd.server_address[1]}"
    for _ in range(100):
        try:
            urllib.request.urlopen(base + "/health", timeout=1)
            break
        except OSError:
            time.sleep(0.02)

    def _req(path, body, headers):
        req = urllib.request.Request(base + path, data=json.dumps(body).encode(),
                                     headers={**headers, "Content-Type": "application/json"})
        try:
            r = urllib.request.urlopen(req, timeout=3)
            return r.status, json.loads(r.read() or b"{}")
        except urllib.error.HTTPError as e:
            return e.code, json.loads(e.read() or b"{}")

    def govern():
        return _req("/govern", {"skill": "fs", "perk": "find_large", "var_keys": ["SEARCH_DIR"]},
                    {"Authorization": "Bearer ALICE"})

    try:
        assert govern()[0] == 200                                  # allow (balance 2 -> 1)
        assert govern()[0] == 200                                  # allow (1 -> 0)
        code, b = govern()                                         # SHUTOFF
        assert code == 403 and "insufficient_credits" in [p.get("id") for p in b.get("problems", [])]
        assert be.budget_balance("alice") == C("0.0000")
        # live top-up (monitor-gated) — no restart
        tc, tb = _req("/budget/topup", {"actor": "alice", "credits": "5.0000"}, {"X-Govd-Monitor": "admin"})
        assert tc == 200 and tb["status"] == "posted" and tb["balance"] == "5.0000"
        assert govern()[0] == 200                                  # the same actor now allows again
        # a bad monitor token is refused
        assert _req("/budget/topup", {"actor": "alice", "credits": "1"}, {"X-Govd-Monitor": "wrong"})[0] == 403
        # input validation: a JSON float (would slip past str()), a negative, and a missing amount are refused
        assert _req("/budget/topup", {"actor": "alice", "credits": 1.5}, {"X-Govd-Monitor": "admin"})[0] == 400
        assert _req("/budget/topup", {"actor": "alice", "credits": "-5.0000"}, {"X-Govd-Monitor": "admin"})[0] == 400
    finally:
        httpd.shutdown()
        httpd.server_close()
