"""P6-T14 — the SettlementAdapter seam: one idempotent fund/payout interface with two interchangeable backends
(InternalCreditsAdapter over the zero-sum reward-ledger + StripeAdapter inert-until-keyed). The hermetic
adapter_selftest exercises interface conformance, zero-sum postings, ledger↔sandbox reconciliation to 0.0001
across 1k payouts, a 10k duplicate-delivery storm with 0 idempotency violations, and Stripe inert-until-keyed."""
from infra.settle import adapter
from infra.settle.money import Money


def test_adapter_selftest_all_pass():
    r = adapter.adapter_selftest()
    assert all(v for v in r.values() if isinstance(v, bool)), r


def test_internal_fund_payout_idempotent_and_zero_sum():
    from infra.settle import reward_ledger
    led = reward_ledger.open_ledger()
    a = adapter.InternalCreditsAdapter(led, source="psp")
    assert a.fund("k1", "escrow", Money("5.00"))["status"] == "funded"
    assert a.fund("k1", "escrow", Money("5.00"))["status"] == "duplicate"   # replay = no-op
    assert a.payout("k2", "payee", Money("2.00"))["status"] == "paid"
    assert a.payout("k2", "payee", Money("2.00"))["status"] == "duplicate"
    assert reward_ledger.global_zero(led)


def test_stripe_inert_until_keyed():
    s = adapter.StripeAdapter({})
    assert s.fund("x", "escrow", Money("9.00"))["status"] == "unconfigured"
    assert s.payout("y", "acct_1", Money("9.00"))["status"] == "unconfigured"


def test_stripe_network_failure_fails_graceful(tmp_path, monkeypatch):
    """A keyed Stripe leg that hits a timeout/DNS/conn-refused must return a graceful error dict, NEVER crash
    (URLError, the superclass of HTTPError) — and must never echo the key in the error."""
    import urllib.error
    import urllib.request
    keyf = tmp_path / "stripe.key"
    keyf.write_text("sk_test_SECRETVALUE")
    s = adapter.StripeAdapter({"key_file": str(keyf)})

    def boom(*a, **k):
        raise urllib.error.URLError("connection refused")
    monkeypatch.setattr(urllib.request, "urlopen", boom)

    r = s.fund("idem-net", "escrow", Money("9.00"))
    assert r["status"] == "error" and "SECRET" not in repr(r)
