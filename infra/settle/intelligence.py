#!/usr/bin/env python3
"""infra/settle/intelligence.py — P6-T09: the schema-validation PAYMENT GATE for llm/* intelligence steps.

The doctrine, made financial: **the meter measures EFFORT; the contract decides whether effort was WORK.**
An llm/* step burns real provider tokens (effort — metered + exod-attested in `infra/settle/metered.py`) and
emits an output. The skill's DECLARED OUTPUT CONTRACT decides whether that effort counted as work:

  * output SATISFIES the contract → it was work. The publisher/agent earn their `work` share, govd takes its
    `fee`, the provider is reimbursed the `passthrough` (the real, metered API cost), and the initiator's
    escrow drains to zero — they paid for valid work and they got it.
  * output FAILS the contract     → effort, not work. The publisher/agent earn **ZERO**; the initiator is
    **REFUNDED** the `work` share (per the validation_refund policy); BUT the `passthrough` STILL reimburses
    the provider (the tokens were really billed) and the `fee` STILL pays govd (governance happened). Nobody
    eats a cost they did not incur; nobody is paid for work they did not deliver.

Every outcome is ONE atomic, balanced (per-currency zero-sum) posting set drained from THIS quote's escrow
(`reward_ledger.escrow_for(quote_sha)`), idempotent per quote_sha (a re-funded quote cannot double-settle).
No float ever touches it — amounts are exact-decimal Money and the work refund/penalty split is the exact
largest-remainder `money.split` (so the refund + penalty re-sum to the work share to the cent).
"""
from __future__ import annotations

from infra.settle import reward_ledger as RL
from infra.settle.money import Money, split

_INTEL_PREFIX = "intel:quote:"          # an intelligence settlement is tagged by quote_sha (never the run_id)

# the JSON-schema-lite type vocabulary the output contract may declare
_TYPES = {"str": str, "string": str, "int": int, "number": (int, float), "num": (int, float),
          "bool": bool, "list": list, "array": list, "dict": dict, "object": dict}


def validate_output(output, contract: dict) -> dict:
    """Does an llm/* `output` satisfy its DECLARED output contract? The contract is JSON-schema-lite:
      {"required": [keys...], "types": {key: "str"|"int"|"number"|"bool"|"list"|"dict"}, "enum": {key: [...]}}
    Returns {"pass": bool, "reason": str}. Fails CLOSED — a non-dict output, a missing required key, a wrong
    type, or an out-of-enum value is NOT work. `bool` is checked before `int` (a Python bool is an int
    subclass, so a True passed where an int is required is refused, not silently accepted)."""
    if not isinstance(output, dict):
        return {"pass": False, "reason": "output_not_object"}
    for k in contract.get("required", []):
        if k not in output:
            return {"pass": False, "reason": f"missing_required:{k}"}
    for k, tname in contract.get("types", {}).items():
        if k not in output:
            continue
        v = output[k]
        exp = _TYPES.get(tname)
        if exp is None:
            return {"pass": False, "reason": f"contract_unknown_type:{tname}"}
        # bool is an int subclass — a contract asking for int/number must reject a bool
        if tname in ("int", "number", "num") and isinstance(v, bool):
            return {"pass": False, "reason": f"wrong_type:{k}"}
        if not isinstance(v, exp):
            return {"pass": False, "reason": f"wrong_type:{k}"}
    for k, allowed in contract.get("enum", {}).items():
        if k in output and output[k] not in allowed:
            return {"pass": False, "reason": f"enum_violation:{k}"}
    return {"pass": True, "reason": "ok"}


def _already_settled(entries: list, quote_sha: str) -> bool:
    tag = _INTEL_PREFIX + quote_sha
    return any(e.get("type") == "posting_set" and e.get("memo") == tag for e in entries)


def settle_intelligence(entries: list, quote_sha: str, breakdown: dict, schema_pass: bool,
                        initiator: str = "initiator", provider: str = "provider", payee: str = "payee",
                        fee_acct: str = "fee", refund_weight: int = 100, penalty_weight: int = 0) -> dict:
    """Settle ONE metered llm/* step against its schema verdict, draining this quote's escrow in a single
    balanced posting set. `breakdown` is the three legs the funded total was allocated into:
        {"passthrough": Money, "work": Money, "fee": Money}
    The escrow `escrow_for(quote_sha)` must already hold passthrough+work+fee, else refuses (unfunded).

      schema_pass=True  → provider+=passthrough, payee+=work, fee+=fee_leg; escrow drains to zero.
      schema_pass=False → provider+=passthrough, fee+=fee_leg(+penalty), initiator+=refund; payee earns 0.
                          The work share is split EXACTLY by [refund_weight, penalty_weight] (default 100/0 =
                          full refund to the initiator, no validation penalty). Any penalty is govd's per the
                          validation_refund policy.

    Idempotent per quote_sha. Returns the outcome dict (all amounts as exact strings)."""
    cur = breakdown["passthrough"].currency
    passthrough = breakdown["passthrough"]
    work = breakdown["work"]
    fee_leg = breakdown["fee"]
    total = passthrough + work + fee_leg

    if _already_settled(entries, quote_sha):
        return {"settled": False, "reason": "quote_already_settled", "quote_sha": quote_sha}
    esc = RL.escrow_for(quote_sha)
    funded = RL.balances(entries).get((esc, cur), Money.zero(cur))
    if funded < total:
        return {"settled": False, "reason": "quote_unfunded",
                "funded": str(funded.amount), "needed": str(total.amount)}

    # Drain the FULL escrow balance, never just `total`, so THIS quote's escrow always returns to zero at
    # settlement (escrow-zero-at-terminal is a ledger invariant). Any overfunding is `change` that goes back
    # to the initiator — value is never stranded in a per-quote escrow sub-account.
    change = funded - total
    postings = [RL._posting(esc, -funded), RL._posting(provider, passthrough), RL._posting(fee_acct, fee_leg)]
    out = {"settled": True, "schema_pass": schema_pass, "quote_sha": quote_sha, "currency": cur,
           "passthrough": str(passthrough.amount), "fee": str(fee_leg.amount), "change": str(change.amount)}
    if schema_pass:
        postings.append(RL._posting(payee, work))
        out.update({"reason": "work", "work_paid": str(work.amount), "work_refunded": "0", "penalty": "0"})
    else:
        refund, penalty = split(work, [refund_weight, penalty_weight])   # exact; default 100/0 = full refund
        if penalty.amount > 0:
            postings.append(RL._posting(fee_acct, penalty))              # validation penalty → govd, per policy
        if refund.amount > 0:
            postings.append(RL._posting(initiator, refund))             # the initiator gets the work share back
        out.update({"reason": "refund_schema_fail", "work_paid": "0",
                    "work_refunded": str(refund.amount), "penalty": str(penalty.amount)})
    if change.amount > 0:
        postings.append(RL._posting(initiator, change))                 # overfunding returns to the initiator
    RL.post(entries, postings, memo=_INTEL_PREFIX + quote_sha)
    return out


def intelligence_selftest() -> dict:
    """Hermetic, no-network. Proves the schema-validation payment gate:
      (1) the output contract DISCRIMINATES — a conforming output passes, a malformed one (missing key /
          wrong type / out-of-enum / non-object) fails;
      (2) schema-PASS settles work to the publisher, fee to govd, passthrough to the provider; escrow zeroes;
      (3) schema-FAIL pays the publisher ZERO, refunds the initiator the work share, yet STILL pays the
          provider the passthrough and govd the fee; escrow zeroes;
      (4) a validation-PENALTY policy (refund 80 / penalty 20) refunds 80% to the initiator and routes 20% to
          govd, exactly (no cent lost);
      (5) every posting set is balanced and the ledger stays globally zero-sum;
      (6) settlement is idempotent per quote_sha (a replay is a no-op)."""
    cur = "USD"
    contract = {"required": ["label", "score"], "types": {"label": "str", "score": "int"},
                "enum": {"label": ["spam", "ham"]}}

    # (1) the contract discriminates effort from work
    good = validate_output({"label": "spam", "score": 3}, contract)["pass"] is True
    bad = (validate_output({"score": 3}, contract)["pass"] is False                       # missing label
           and validate_output({"label": "spam", "score": "x"}, contract)["pass"] is False   # wrong type
           and validate_output({"label": "nope", "score": 3}, contract)["pass"] is False     # enum violation
           and validate_output({"label": "spam", "score": True}, contract)["pass"] is False  # bool != int
           and validate_output(["not", "an", "object"], contract)["pass"] is False)          # non-object
    discriminates = good and bad

    bd = {"passthrough": Money("0.2000", cur), "work": Money("1.0000", cur), "fee": Money("0.0500", cur)}
    total = bd["passthrough"] + bd["work"] + bd["fee"]
    z = Money.zero(cur)

    def settle_with_deltas(sha, schema_pass, **kw):
        """Fund this quote's escrow from the initiator, settle, and return the per-account DELTAS the settle
        posting produced — measuring what settlement MOVED, independent of the (initiator -total) funding leg."""
        led = RL.open_ledger()
        RL.fund_escrow(led, "initiator", total, RL.escrow_for(sha), memo="fund")
        before = RL.balances(led)
        r = settle_intelligence(led, sha, bd, schema_pass=schema_pass, **kw)
        after = RL.balances(led)
        d = {k: after.get(k, z) - before.get(k, z) for k in set(before) | set(after)}
        return led, r, d

    esc_pass, esc_fail = RL.escrow_for("qpass"), RL.escrow_for("qfail")

    # (2) schema PASS — publisher earns work, provider reimbursed, govd fee'd, escrow drained
    led_p, rp, dp = settle_with_deltas("qpass", True)
    pass_pays_work = (rp["settled"] and dp.get(("payee", cur), z) == bd["work"]
                      and dp.get(("provider", cur), z) == bd["passthrough"]
                      and dp.get(("fee", cur), z) == bd["fee"]
                      and dp.get((esc_pass, cur), z) == -total
                      and RL.global_zero(led_p))

    # (3) schema FAIL — publisher ZERO, initiator refunded the work share, provider+fee STILL land, escrow drained
    led_f, rf, df = settle_with_deltas("qfail", False)
    fail_refunds = (rf["settled"] and df.get(("payee", cur), z).is_zero()                  # publisher earns 0
                    and df.get(("provider", cur), z) == bd["passthrough"]                  # provider still paid
                    and df.get(("fee", cur), z) == bd["fee"]                               # govd still paid
                    and df.get(("initiator", cur), z) == bd["work"]                        # initiator refunded work
                    and df.get((esc_fail, cur), z) == -total
                    and RL.global_zero(led_f))

    # (4) a validation-penalty policy: refund 80%, govd keeps 20% — exact, no cent lost
    refund_exp, penalty_exp = split(bd["work"], [80, 20])
    led_pen, rpen, dpen = settle_with_deltas("qpen", False, refund_weight=80, penalty_weight=20)
    penalty_exact = (dpen.get(("initiator", cur), z) == refund_exp                         # initiator gets 80%
                     and dpen.get(("fee", cur), z) == bd["fee"] + penalty_exp              # govd: fee + 20% penalty
                     and dpen.get(("payee", cur), z).is_zero()                             # publisher still 0
                     and (refund_exp + penalty_exp) == bd["work"]                          # nothing created/lost
                     and RL.global_zero(led_pen))

    # (6) idempotency — a replay against the SAME quote_sha is a no-op (re-fund the escrow first)
    RL.fund_escrow(led_f, "initiator", total, esc_fail, memo="refund-attempt")
    replay = settle_intelligence(led_f, "qfail", bd, schema_pass=False)
    idempotent = replay["settled"] is False and replay["reason"] == "quote_already_settled"

    # (7) overfunding — the escrow ALWAYS drains to zero; the excess is `change` back to the initiator (no
    #     value stranded in a per-quote escrow). Fund total + 0.50, settle, assert escrow zero + change exact.
    led_o = RL.open_ledger()
    over = total + Money("0.5000", cur)
    esc_over = RL.escrow_for("qover")
    RL.fund_escrow(led_o, "initiator", over, esc_over, memo="overfund")
    ro = settle_intelligence(led_o, "qover", bd, schema_pass=True)
    overfund_returns_change = (ro["settled"] and ro["change"] == "0.5000"
                               and RL.balances(led_o).get((esc_over, cur), z).is_zero()
                               and RL.balances(led_o).get(("initiator", cur), z) == -total  # net cost = total only
                               and RL.global_zero(led_o))

    ok = bool(discriminates and pass_pays_work and fail_refunds and penalty_exact and idempotent
              and overfund_returns_change)
    return {"contract_discriminates": discriminates, "pass_pays_work": pass_pays_work,
            "fail_refunds_initiator": fail_refunds, "penalty_policy_exact": penalty_exact,
            "idempotent": idempotent, "overfund_returns_change": overfund_returns_change, "ok": ok}


if __name__ == "__main__":
    import json
    import sys
    r = intelligence_selftest()
    print(json.dumps(r, indent=2))
    sys.exit(0 if r["ok"] else 1)
