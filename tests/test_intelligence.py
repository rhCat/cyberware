"""P6-T09 — the schema-validation PAYMENT GATE for llm/* intelligence steps. "The meter measures effort; the
contract decides whether effort was work." A schema-PASS pays the publisher the work share; a schema-FAIL pays
the publisher ZERO and refunds the initiator the work share, yet STILL reimburses the provider passthrough and
pays govd the fee — every outcome one balanced, zero-sum, idempotent posting set."""
from infra.settle import intelligence
from infra.settle import reward_ledger as RL
from infra.settle.money import Money

_CUR = "USD"
_CONTRACT = {"required": ["label", "score"], "types": {"label": "str", "score": "int"},
             "enum": {"label": ["spam", "ham"]}}


def test_intelligence_selftest_all_pass():
    r = intelligence.intelligence_selftest()
    assert all(v for v in r.values() if isinstance(v, bool)), r


def test_validate_output_discriminates():
    assert intelligence.validate_output({"label": "spam", "score": 3}, _CONTRACT)["pass"] is True
    # missing required, wrong type, enum violation, bool-where-int, non-object — all refused
    assert intelligence.validate_output({"score": 3}, _CONTRACT)["pass"] is False
    assert intelligence.validate_output({"label": "spam", "score": "x"}, _CONTRACT)["pass"] is False
    assert intelligence.validate_output({"label": "nope", "score": 3}, _CONTRACT)["pass"] is False
    assert intelligence.validate_output({"label": "spam", "score": True}, _CONTRACT)["pass"] is False
    assert intelligence.validate_output(["not", "an", "object"], _CONTRACT)["pass"] is False


def _funded(sha, bd):
    total = bd["passthrough"] + bd["work"] + bd["fee"]
    led = RL.open_ledger()
    RL.fund_escrow(led, "initiator", total, RL.escrow_for(sha), memo="fund")
    return led


def _bd():
    return {"passthrough": Money("0.2000", _CUR), "work": Money("1.0000", _CUR), "fee": Money("0.0500", _CUR)}


def test_schema_pass_pays_work():
    bd = _bd()
    led = _funded("qp", bd)
    r = intelligence.settle_intelligence(led, "qp", bd, schema_pass=True)
    bal = RL.balances(led)
    assert r["settled"] and r["work_paid"] == "1.0000"
    assert bal[("payee", _CUR)] == bd["work"]
    assert bal[("provider", _CUR)] == bd["passthrough"]
    assert bal[("fee", _CUR)] == bd["fee"]
    assert bal.get((RL.escrow_for("qp"), _CUR), Money.zero(_CUR)).is_zero()
    assert RL.global_zero(led)


def test_schema_fail_pays_publisher_zero_refunds_initiator():
    bd = _bd()
    led = _funded("qf", bd)
    before_init = RL.balances(led)[("initiator", _CUR)]
    r = intelligence.settle_intelligence(led, "qf", bd, schema_pass=False)
    bal = RL.balances(led)
    assert r["settled"] and r["work_paid"] == "0" and r["work_refunded"] == "1.0000"
    assert ("payee", _CUR) not in bal                              # publisher earns nothing
    assert bal[("provider", _CUR)] == bd["passthrough"]           # provider still reimbursed
    assert bal[("fee", _CUR)] == bd["fee"]                        # govd still paid
    # the initiator got the work share back: net cost is only the real (passthrough + fee)
    assert bal[("initiator", _CUR)] - before_init == bd["work"]
    assert bal[("initiator", _CUR)] == -(bd["passthrough"] + bd["fee"])
    assert bal.get((RL.escrow_for("qf"), _CUR), Money.zero(_CUR)).is_zero()
    assert RL.global_zero(led)


def test_penalty_policy_splits_work_exactly():
    bd = _bd()
    led = _funded("qpen", bd)
    r = intelligence.settle_intelligence(led, "qpen", bd, schema_pass=False,
                                         refund_weight=80, penalty_weight=20)
    from infra.settle.money import split
    refund_exp, penalty_exp = split(bd["work"], [80, 20])
    bal = RL.balances(led)
    assert bal[("initiator", _CUR)] == -(bd["passthrough"] + bd["fee"] + penalty_exp)
    assert bal[("fee", _CUR)] == bd["fee"] + penalty_exp
    assert ("payee", _CUR) not in bal
    assert refund_exp + penalty_exp == bd["work"]                 # nothing created or lost
    assert RL.global_zero(led)


def test_idempotent_per_quote_sha():
    bd = _bd()
    led = _funded("qi", bd)
    assert intelligence.settle_intelligence(led, "qi", bd, schema_pass=True)["settled"] is True
    RL.fund_escrow(led, "initiator", bd["passthrough"] + bd["work"] + bd["fee"],
                   RL.escrow_for("qi"), memo="replay")            # re-fund the replay vector
    replay = intelligence.settle_intelligence(led, "qi", bd, schema_pass=True)
    assert replay["settled"] is False and replay["reason"] == "quote_already_settled"


def test_unfunded_quote_refused():
    bd = _bd()
    led = RL.open_ledger()                                        # no escrow funded
    r = intelligence.settle_intelligence(led, "qu", bd, schema_pass=True)
    assert r["settled"] is False and r["reason"] == "quote_unfunded"


def test_overfunded_escrow_drains_to_zero_change_to_initiator():
    """A per-quote escrow must NEVER strand value: an overfunded escrow drains fully, the excess returns to
    the initiator as change, and escrow ends at exactly zero."""
    bd = _bd()
    total = bd["passthrough"] + bd["work"] + bd["fee"]
    led = RL.open_ledger()
    RL.fund_escrow(led, "initiator", total + Money("0.5000", _CUR), RL.escrow_for("qo"), memo="overfund")
    r = intelligence.settle_intelligence(led, "qo", bd, schema_pass=True)
    bal = RL.balances(led)
    assert r["settled"] and r["change"] == "0.5000"
    assert bal.get((RL.escrow_for("qo"), _CUR), Money.zero(_CUR)).is_zero()   # nothing stranded
    assert bal[("initiator", _CUR)] == -total                    # net cost is the quote total, not the overfund
    assert RL.global_zero(led)
