#!/usr/bin/env python3
"""infra/settle/money.py — the Money type (P6-T01, SV-6 / M6).

Money is **exact decimal**, never a binary float. Every amount is a `Decimal` at **scale 4** (four
fractional digits) under an explicit context that rounds **HALF_EVEN** (banker's rounding — the unbiased
default for money). Two invariants the rest of the settlement engine leans on:

  * **no binary float ever touches a money path** — `Money` REFUSES a `float` at construction, and the
    `float_ban` AST lint proves no float literal / `float(...)` call appears in the settlement modules
    (`infra/settle/`). A float would silently re-introduce representation error into balances.
  * **a split sums to the whole, exactly** — `split(total, weights)` allocates by the largest-remainder
    method, so the parts re-add to the total to the cent (scale-4 unit). This is what lets a quote's split
    policy and a settlement's posting set be *zero-sum exact*, not merely "close".
"""
from __future__ import annotations
import ast
import os
from decimal import ROUND_HALF_EVEN, Context, Decimal

SCALE = 4
QUANT = Decimal("1").scaleb(-SCALE)                            # Decimal('0.0001')
CTX = Context(prec=34, rounding=ROUND_HALF_EVEN)              # explicit: HALF_EVEN, generous precision


def _to_decimal(amount) -> Decimal:
    """Coerce to Decimal — REFUSING float (the float-ban at the type boundary). int / str / Decimal only."""
    if isinstance(amount, bool):                              # bool is an int subclass; not a money amount
        raise TypeError("money amount must not be a bool")
    if isinstance(amount, float):
        raise TypeError("money amount must not be a binary float — pass a str/int/Decimal (float-ban)")
    if isinstance(amount, Decimal):
        return amount
    if isinstance(amount, int):
        return Decimal(amount)
    if isinstance(amount, str):
        return Decimal(amount)
    raise TypeError(f"unsupported money amount type: {type(amount).__name__}")


def _q(d: Decimal) -> Decimal:
    """Quantize to scale 4 under the explicit HALF_EVEN context."""
    return d.quantize(QUANT, context=CTX)


class Money:
    """An exact decimal amount in a currency, quantized to scale 4 (HALF_EVEN). Arithmetic stays in Decimal;
    a float is refused everywhere."""
    __slots__ = ("amount", "currency")

    def __init__(self, amount, currency: str = "USD"):
        self.amount = _q(_to_decimal(amount))
        self.currency = currency

    @classmethod
    def zero(cls, currency: str = "USD") -> "Money":
        return cls(0, currency)

    def _same(self, other: "Money"):
        if not isinstance(other, Money):
            raise TypeError("can only combine Money with Money")
        if other.currency != self.currency:
            raise ValueError(f"currency mismatch: {self.currency} vs {other.currency}")

    def __add__(self, other: "Money") -> "Money":
        self._same(other)
        return Money(CTX.add(self.amount, other.amount), self.currency)

    def __sub__(self, other: "Money") -> "Money":
        self._same(other)
        return Money(CTX.subtract(self.amount, other.amount), self.currency)

    def __neg__(self) -> "Money":
        return Money(-self.amount, self.currency)

    def scale(self, ratio) -> "Money":
        """Multiply by a non-float ratio (int/str/Decimal) and re-quantize HALF_EVEN."""
        return Money(CTX.multiply(self.amount, _to_decimal(ratio)), self.currency)

    def __eq__(self, other) -> bool:
        return isinstance(other, Money) and other.currency == self.currency and other.amount == self.amount

    def __lt__(self, other: "Money") -> bool:
        self._same(other)
        return self.amount < other.amount

    def __le__(self, other: "Money") -> bool:
        self._same(other)
        return self.amount <= other.amount

    def __hash__(self):
        return hash((str(self.amount), self.currency))

    def is_zero(self) -> bool:
        return self.amount == Decimal(0)

    def __repr__(self):
        return f"Money('{self.amount}', '{self.currency}')"


def split(total: Money, weights) -> list:
    """Allocate `total` across `weights` (non-float ints/Decimals) so the parts sum to `total` EXACTLY
    (largest-remainder method). Each share is floored to scale 4; the leftover scale-4 units go to the
    shares with the largest truncated remainders (ties by index), so nothing is created or lost."""
    ws = [_to_decimal(w) for w in weights]
    if not ws or any(w < 0 for w in ws):
        raise ValueError("weights must be non-empty and non-negative")
    tw = sum(ws, Decimal(0))
    if tw == 0:
        raise ValueError("weights sum to zero")
    units = (total.amount / QUANT).to_integral_value()         # total expressed in scale-4 integer units
    raw = [units * w / tw for w in ws]
    floors = [r.to_integral_value(rounding="ROUND_FLOOR") for r in raw]
    remainder = int(units - sum(floors, Decimal(0)))
    order = sorted(range(len(ws)), key=lambda i: (raw[i] - floors[i], -i), reverse=True)
    alloc = list(floors)
    for k in range(remainder):
        alloc[order[k % len(order)]] += 1
    return [Money(a * QUANT, total.currency) for a in alloc]


# ── the float-ban AST lint ────────────────────────────────────────────────────

def float_ban_scan(paths) -> list:
    """Scan `.py` files for binary-float intrusions on money paths: a float literal (`ast.Constant` of type
    float) or a `float(...)` call. Returns [{file, line, kind, src}] — empty ⇒ clean."""
    findings = []
    files = []
    for p in paths:
        if os.path.isdir(p):
            for root, _, names in os.walk(p):
                files += [os.path.join(root, n) for n in names if n.endswith(".py")]
        elif p.endswith(".py"):
            files.append(p)
    for f in sorted(set(files)):
        try:
            tree = ast.parse(open(f).read(), filename=f)
        except SyntaxError:
            continue
        for node in ast.walk(tree):
            if isinstance(node, ast.Constant) and isinstance(node.value, float):
                findings.append({"file": f, "line": node.lineno, "kind": "float_literal", "src": repr(node.value)})
            elif isinstance(node, ast.Call) and isinstance(node.func, ast.Name) and node.func.id == "float":
                findings.append({"file": f, "line": node.lineno, "kind": "float_call", "src": "float(...)"})
    return findings


_SETTLE_DIR = os.path.dirname(os.path.abspath(__file__))


def money_selftest() -> dict:
    """P6-T01 money correctness: HALF_EVEN rounds to even at the scale-4 boundary; a float is refused at
    construction; add/sub conserve; and a split re-sums to the total EXACTLY across awkward weights."""
    # banker's rounding at the 5th place: .00005 -> .0000 (even), .00015 -> .0002, .00025 -> .0002 (even)
    half_even = (Money("0.00005").amount == Decimal("0.0000")
                 and Money("0.00015").amount == Decimal("0.0002")
                 and Money("0.00025").amount == Decimal("0.0002"))
    float_refused = False
    bad_float = 1 / 10                                         # a runtime binary float (no literal — money.py stays float-literal-free)
    try:
        Money(bad_float)
    except TypeError:
        float_refused = True
    conserve = (Money("10.0000") - Money("3.3333")) + Money("3.3333") == Money("10.0000")
    # a $100 split 1:1:1 cannot divide evenly at scale 4 → parts must still re-sum to exactly 100.0000
    parts = split(Money("100.0000"), [1, 1, 1])
    summed = parts[0]
    for p in parts[1:]:
        summed = summed + p
    split_exact = summed == Money("100.0000") and len(parts) == 3
    # an awkward weighted split (a third example) also conserves
    p2 = split(Money("0.0001"), [1, 1, 1])                     # one scale-4 unit across three weights
    split_exact_tiny = (p2[0] + p2[1] + p2[2]) == Money("0.0001")
    return {"half_even": half_even, "float_refused": float_refused, "conserve": conserve,
            "split_exact": split_exact, "split_exact_tiny": split_exact_tiny,
            "ok": half_even and float_refused and conserve and split_exact and split_exact_tiny}


def float_ban_selftest(scan_dir: str = None) -> dict:
    """P6-T01 float-ban: the settlement modules (`infra/settle/`) contain ZERO binary-float intrusions; and
    the lint actually fires on a seeded float file (so the 0-count is a real verdict, not a no-op)."""
    import tempfile
    target = scan_dir or _SETTLE_DIR
    clean = float_ban_scan([target])
    # seed a float intrusion and confirm the lint catches both a literal and a float() call
    d = tempfile.mkdtemp(prefix="floatban-")
    open(os.path.join(d, "bad.py"), "w").write("rate = 0.07\nx = float('1.5')\n")
    seeded = float_ban_scan([d])
    return {"settle_float_occurrences": len(clean), "settle_clean": not clean,
            "lint_fires_on_seed": len(seeded) >= 2,
            "seed_kinds": sorted({s["kind"] for s in seeded}),
            "ok": not clean and len(seeded) >= 2}
