"""P6-T15 — the adapter-boundary rounding rule + the dust account. A CWC amount (exact-decimal Money, scale-4)
crossing a cents boundary is banker's-rounded (HALF_EVEN); the sub-cent residue posts to dust:adapter:<id> in
the SAME balanced entry, so global zero-sum holds INCLUDING dust; accumulated dust sweeps to treasury as a
balanced, signed record."""
from decimal import Decimal

from infra.settle import dust
from infra.settle import reward_ledger as RL
from infra.settle.money import Money


def test_dust_selftest_all_pass():
    r = dust.dust_selftest(n=2000)                                   # representative; the perk runs the full 100k
    assert all(v for v in r.values() if isinstance(v, bool)), r


def test_split_cents_is_exact_and_bankers():
    for s in ("1.2345", "0.0001", "99.9950", "12.3456"):
        a = Money(s); c, d = dust.split_cents(a)
        assert c + d == a                                            # nothing created or lost
        assert c.amount == c.amount.quantize(Decimal("0.01"))       # cents is exactly 2dp
    # banker's rounding: a half-cent residue rounds to EVEN, not always up
    assert dust.split_cents(Money("0.1250"))[0].amount == Decimal("0.1200")
    assert dust.split_cents(Money("0.1350"))[0].amount == Decimal("0.1400")
    assert dust.to_minor(Money("1.2345")) == 123                    # the integer cents an adapter bills


def test_boundary_posting_is_balanced_and_conserves_the_residue():
    led = RL.open_ledger()
    dust.settle_at_boundary(led, "escrow", "payee", Money("1.2345"), "stripe")
    bal = RL.balances(led)
    assert bal[("escrow", "USD")] == Money("-1.2345")               # the payer was debited the full scale-4 amount
    assert bal[("payee", "USD")] == Money("1.2300")                 # the rounded cents
    assert bal[(dust.dust_account("stripe"), "USD")] == Money("0.0045")  # the sub-cent residue
    assert RL.global_zero(led)                                      # conserved INCLUDING dust


def test_signed_sweep_drains_dust_to_treasury_and_verifies():
    from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
    led = RL.open_ledger()
    for i in range(50):
        dust.settle_at_boundary(led, "escrow", "payee", Money(f"1.00{i:02d}"), "stripe")
    accrued = RL.balances(led)[(dust.dust_account("stripe"), "USD")]
    sk = Ed25519PrivateKey.generate()
    res = dust.sweep_dust(led, "stripe", "treasury", sk)
    after = RL.balances(led)
    assert after.get((dust.dust_account("stripe"), "USD"), Money.zero()).is_zero()   # dust drained
    assert after[("treasury", "USD")] == accrued                                     # to the treasury
    assert RL.global_zero(led)                                                       # still conserved
    from infra.cwp import sign
    assert sign.verify(res["signed"], sk.public_key()) is True                       # the sweep record verifies
