#!/usr/bin/env python3
"""infra/settle/adapter.py — P6-T14: the SettlementAdapter seam (R2). ONE interface, two interchangeable
backends, every money-movement event idempotency-keyed.

A SettlementAdapter moves money across the settlement boundary with a uniform, idempotent API:
    fund(idem_key, account, amount)   money IN  — credit a balance / take a deposit
    payout(idem_key, dest, amount)    money OUT — disburse to a payee (a connected account)
    status(event_id)                  the recorded state of a prior event
Idempotency is INTRINSIC: replaying any event (same idem_key) is a no-op that returns the original outcome —
a duplicated webhook delivery, a retry, or a crash-and-resume never double-moves money.

  * InternalCreditsAdapter — the default/free tier, over the exact-decimal reward-ledger (NO network): fund
    tops up an account from a funding source, payout debits a payable pool to a payee; both are zero-sum
    balanced postings. The dedup key is the posting memo, so idempotency is the ledger's own truth.
  * StripeAdapter — the real-money tier: fund via Payment Intents, payout via Connect transfers, an
    Idempotency-Key header on EVERY call. INERT (status "unconfigured") until an operator key_file is wired
    server-side — exactly like rails.StripeRail; the agent never sees the key. The hermetic selftest never
    needs it; the live PSP leg is opt-in.

No float ever touches it (amounts are exact-decimal Money).
"""
from __future__ import annotations

from decimal import Decimal

from infra.settle import reward_ledger
from infra.settle.money import Money

_FUND_PREFIX = "adapter-fund:"
_PAYOUT_PREFIX = "adapter-payout:"


class SettlementAdapter:
    """The uniform settlement interface. fund/payout move money idempotently; status reports a prior event."""
    name = "abstract"

    def fund(self, idem_key: str, account: str, amount: Money) -> dict:
        raise NotImplementedError

    def payout(self, idem_key: str, dest: str, amount: Money) -> dict:
        raise NotImplementedError

    def status(self, event_id: str) -> dict:
        raise NotImplementedError


class InternalCreditsAdapter(SettlementAdapter):
    """Money moves as zero-sum reward-ledger postings — no network, the default tier. Idempotent per idem_key
    (the posting memo IS the dedup key, so it survives a fresh adapter / process restart: __init__ rebuilds
    the seen-set by scanning the ledger). fund credits an account from a funding source; payout debits a
    payable pool to a payee."""
    name = "internal"

    def __init__(self, entries: list, source: str = "external"):
        self.entries = entries
        self.source = source
        self._seen = {e["memo"] for e in entries
                      if e.get("type") == "posting_set" and isinstance(e.get("memo"), str)}

    def _post(self, prefix: str, idem_key: str, postings) -> bool:
        """Post once per idem_key; return False (no-op) on replay. Source of truth = the ledger memos."""
        memo = prefix + idem_key
        if memo in self._seen:
            return False
        reward_ledger.post(self.entries, postings, memo=memo)
        self._seen.add(memo)
        return True

    def fund(self, idem_key: str, account: str, amount: Money) -> dict:
        ev = _FUND_PREFIX + idem_key
        fresh = self._post(_FUND_PREFIX, idem_key,
                           [reward_ledger._posting(account, amount),
                            reward_ledger._posting(f"fund:{self.source}", -amount)])
        return {"adapter": self.name, "op": "fund", "status": "funded" if fresh else "duplicate",
                "account": account, "amount": str(amount.amount), "currency": amount.currency,
                "idem": idem_key, "event_id": ev}

    def payout(self, idem_key: str, dest: str, amount: Money) -> dict:
        ev = _PAYOUT_PREFIX + idem_key
        fresh = self._post(_PAYOUT_PREFIX, idem_key,
                           [reward_ledger._posting(dest, amount),
                            reward_ledger._posting(f"payout:{self.source}", -amount)])
        return {"adapter": self.name, "op": "payout", "status": "paid" if fresh else "duplicate",
                "dest": dest, "amount": str(amount.amount), "currency": amount.currency,
                "idem": idem_key, "event_id": ev}

    def status(self, event_id: str) -> dict:
        return {"adapter": self.name, "event_id": event_id,
                "status": "recorded" if event_id in self._seen else "unknown"}


class StripeAdapter(SettlementAdapter):
    """Real-money tier: fund via Payment Intents, payout via Connect transfers, Idempotency-Key on EVERY call.
    INERT until config.key_file is set (operator wires the key server-side; the agent never sees it). The
    connected-account id (config.connect_account) is needed for real payouts. Mirrors rails.StripeRail."""
    name = "stripe"
    FUND_API = "https://api.stripe.com/v1/payment_intents"
    PAYOUT_API = "https://api.stripe.com/v1/transfers"

    def __init__(self, config: dict = None):
        self.config = config or {}

    def _keyed(self):
        return bool(self.config.get("key_file"))

    def fund(self, idem_key: str, account: str, amount: Money) -> dict:
        if not self._keyed():
            return {"adapter": self.name, "op": "fund", "status": "unconfigured",
                    "would_fund": str(amount.amount), "currency": amount.currency, "idem": idem_key,
                    "note": "set rails.stripe.key_file (operator key, server-side) to enable; agent never sees it"}
        return self._call(self.FUND_API, idem_key, amount, {
            "amount": _minor(amount), "currency": amount.currency.lower(), "confirm": "true",
            "payment_method": self.config.get("payment_method", "pm_card_visa"),
            "payment_method_types[]": "card", "description": f"cyberware fund {idem_key[:16]}"})

    def payout(self, idem_key: str, dest: str, amount: Money) -> dict:
        if not self._keyed():
            return {"adapter": self.name, "op": "payout", "status": "unconfigured",
                    "would_pay": str(amount.amount), "dest": dest, "idem": idem_key,
                    "note": "set key_file + connect_account to enable Connect transfers"}
        acct = self.config.get("connect_account")
        if not acct:
            return {"adapter": self.name, "op": "payout", "status": "no_connect_account", "idem": idem_key}
        return self._call(self.PAYOUT_API, idem_key, amount, {
            "amount": _minor(amount), "currency": amount.currency.lower(), "destination": acct,
            "transfer_group": idem_key[:32]})

    def _call(self, api: str, idem_key: str, amount: Money, fields: dict) -> dict:
        import json as _json
        import os
        import urllib.error
        import urllib.parse
        import urllib.request
        if int(fields.get("amount", 0)) <= 0:
            return {"adapter": self.name, "status": "below_minimum", "amount": str(amount.amount),
                    "idem": idem_key, "note": "sub-cent — a one-shot PSP call is impossible"}
        key = open(os.path.expanduser(self.config["key_file"]), encoding="utf-8").read().strip()
        req = urllib.request.Request(
            api, data=urllib.parse.urlencode(fields).encode(), method="POST",
            headers={"Authorization": "Bearer " + key, "Idempotency-Key": idem_key,
                     "Content-Type": "application/x-www-form-urlencoded"})
        try:
            with urllib.request.urlopen(req, timeout=20) as r:
                obj = _json.loads(r.read())
            return {"adapter": self.name, "status": "ok", "event_id": obj.get("id"),
                    "psp_status": obj.get("status"), "amount": str(amount.amount), "idem": idem_key}
        except urllib.error.HTTPError as e:                       # PSP rejected — surface the error, never the key
            return {"adapter": self.name, "status": "error", "http": e.code,
                    "detail": e.read().decode()[:300], "idem": idem_key}
        except urllib.error.URLError as e:                        # timeout/DNS/conn-refused — fail graceful, no crash
            return {"adapter": self.name, "status": "error", "detail": str(e.reason)[:300], "idem": idem_key}

    def status(self, event_id: str) -> dict:
        return {"adapter": self.name, "event_id": event_id,
                "status": "unconfigured" if not self._keyed() else "live_lookup_not_implemented"}


def _minor(amount: Money) -> int:
    """Money -> minor units (cents) for the PSP, exact (no float)."""
    return int((amount.amount * 100).to_integral_value())


def adapter_selftest(n_recon: int = 1000, n_dup: int = 10000) -> dict:
    """Hermetic, no-network. (1) interface conformance — both adapters expose fund/payout/status; (2)
    InternalCreditsAdapter fund+payout are zero-sum; (3) the double-entry ledger reconciles EXACTLY (to 0.0001)
    against an independent single-entry sandbox tally across n_recon fund+payout pairs; (4) a duplicate-delivery
    storm — replay every event 2..10x (n_dup total) — leaves balances IDENTICAL with 0 idempotency violations;
    (5) StripeAdapter stays inert (unconfigured) until keyed."""
    cur = "USD"
    led = reward_ledger.open_ledger()
    ad = InternalCreditsAdapter(led, source="psp")

    # (3) reconciliation: the double-entry ledger vs an INDEPENDENT single-entry sandbox tallied in raw Decimal
    #     (NOT Money.__add__/__eq__) — so a regression in Money's own arithmetic is also caught here, not just a
    #     ledger-posting bug. The two sides share no arithmetic code path; the oracle is genuinely independent.
    sandbox: dict = {}   # acct -> Decimal
    def tally(acct, d: Decimal):
        sandbox[acct] = sandbox.get(acct, Decimal(0)) + d
    events = []   # (op, idem, target, amount) — kept for the replay storm
    for i in range(n_recon):
        amt = Money(str((i % 97) + 1) + ".0007", cur)            # deterministic, sub-cent precision
        ad.fund(f"f{i}", "escrow", amt); tally("escrow", amt.amount); tally("fund:psp", -amt.amount)
        payee = f"payee{i % 13}"
        ad.payout(f"p{i}", payee, amt); tally(payee, amt.amount); tally("payout:psp", -amt.amount)
        events += [("fund", f"f{i}", "escrow", amt), ("payout", f"p{i}", payee, amt)]
    led_bal = reward_ledger.balances(led)
    accts = {a for (a, c) in led_bal} | set(sandbox)
    recon_exact = all(led_bal.get((a, cur), Money.zero(cur)).amount == sandbox.get(a, Decimal(0)) for a in accts)

    # (4) duplicate-delivery storm: replay events round-robin to n_dup, every replay must be a no-op duplicate
    before = reward_ledger.balances(led)
    violations = 0
    replays = 0
    j = 0
    while replays < n_dup:
        op, idem, target, amt = events[j % len(events)]
        r = ad.fund(idem, target, amt) if op == "fund" else ad.payout(idem, target, amt)
        if r["status"] != "duplicate":                          # a replay that moved money = a violation
            violations += 1
        replays += 1
        j += 1
    after = reward_ledger.balances(led)
    balances_identical = before == after

    # (5) StripeAdapter inert until keyed
    s_inert = (StripeAdapter({}).fund("x", "escrow", Money("5.00", cur))["status"] == "unconfigured"
               and StripeAdapter({}).payout("y", "acct_1", Money("5.00", cur))["status"] == "unconfigured")

    # (1) interface conformance + (2) zero-sum
    iface = all(callable(getattr(a, m, None)) for a in (InternalCreditsAdapter([]), StripeAdapter({}))
                for m in ("fund", "payout", "status"))
    return {
        "interface_conformance": iface,
        "zero_sum": reward_ledger.global_zero(led),
        "reconcile_exact": recon_exact,
        "recon_payouts": n_recon,
        "idempotent_no_violations": violations == 0 and balances_identical,
        "dup_replays": replays,
        "stripe_inert_until_keyed": s_inert,
    }
