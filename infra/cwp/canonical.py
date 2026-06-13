#!/usr/bin/env python3
"""canonical.py — RFC 8785 JSON Canonicalization Scheme (JCS), vendored (P0-T02).

The single canonical-bytes path: `canonical_bytes(obj)` serializes a JSON value to the one byte sequence
RFC 8785 prescribes — object members sorted by their UTF-16 code units, no insignificant whitespace,
minimal string escaping, and ECMAScript `Number::toString` number formatting — so any conformant
implementation (e.g. the Go verifier, P0-T08) reproduces it byte-for-byte. `digest(obj)` is sha256 over
those bytes: cyberware's hashes are this and only this.

Scope: full JCS for objects, arrays, strings, booleans, null, integers (preserved exactly), and IEEE-754
doubles via a complete ES6 Number::toString. NaN / Infinity are rejected (JSON has no such values).

  from infra.cwp import canonical
  canonical.canonicalize(obj) -> str        # the canonical text
  canonical.canonical_bytes(obj) -> bytes    # UTF-8
  canonical.digest(obj) -> str               # sha256 hex of the canonical bytes
"""
from __future__ import annotations
import hashlib
from decimal import Decimal


def _escape(s: str) -> str:
    """Minimal JSON string escaping per RFC 8785 §3.2.2.2: only ", \\, and the C0 controls are escaped
    (short forms for \\b \\t \\n \\f \\r, \\u00xx otherwise); '/' and all non-ASCII stay literal (UTF-8)."""
    out = ['"']
    for ch in s:
        o = ord(ch)
        if ch == '"':
            out.append('\\"')
        elif ch == "\\":
            out.append("\\\\")
        elif o == 0x08:
            out.append("\\b")
        elif o == 0x09:
            out.append("\\t")
        elif o == 0x0A:
            out.append("\\n")
        elif o == 0x0C:
            out.append("\\f")
        elif o == 0x0D:
            out.append("\\r")
        elif o < 0x20:
            out.append("\\u%04x" % o)
        else:
            out.append(ch)
    out.append('"')
    return "".join(out)


def _es6_number(x: float) -> str:
    """ECMAScript Number::toString for a finite double (RFC 8785 §3.2.2.3). Uses the shortest round-trip
    decimal (Python's float repr) and re-formats it under the ES6 positional rules."""
    if x != x or x in (float("inf"), float("-inf")):
        raise ValueError("NaN/Infinity is not a valid JSON number")
    if x == 0:
        return "0"                                            # JCS folds -0 to "0"
    neg = x < 0
    sign, digs, exp = Decimal(repr(abs(x))).normalize().as_tuple()  # shortest digits, trailing zeros stripped
    s = "".join(map(str, digs))
    k = len(s)
    n = exp + k                                               # value = s × 10^(n-k); 10^(k-1) ≤ s < 10^k
    if k <= n <= 21:
        body = s + "0" * (n - k)
    elif 0 < n <= 21:
        body = s[:n] + "." + s[n:]
    elif -6 < n <= 0:
        body = "0." + "0" * (-n) + s
    else:
        mant = s[0] + ("." + s[1:] if k > 1 else "")
        e = n - 1
        body = f"{mant}e{'+' if e >= 0 else '-'}{abs(e)}"
    return ("-" if neg else "") + body


def canonicalize(obj) -> str:
    if obj is True:
        return "true"
    if obj is False:
        return "false"
    if obj is None:
        return "null"
    if isinstance(obj, str):
        return _escape(obj)
    if isinstance(obj, int):                                  # bool already handled above
        return str(obj)
    if isinstance(obj, float):
        return _es6_number(obj)
    if isinstance(obj, (list, tuple)):
        return "[" + ",".join(canonicalize(v) for v in obj) + "]"
    if isinstance(obj, dict):
        for k in obj:
            if not isinstance(k, str):
                raise TypeError(f"JSON object keys must be strings, got {type(k).__name__}")
        items = sorted(obj.items(), key=lambda kv: kv[0].encode("utf-16-be"))  # sort by UTF-16 code units
        return "{" + ",".join(_escape(k) + ":" + canonicalize(v) for k, v in items) + "}"
    raise TypeError(f"not JSON-serializable: {type(obj).__name__}")


def canonical_bytes(obj) -> bytes:
    return canonicalize(obj).encode("utf-8")


def digest(obj) -> str:
    return hashlib.sha256(canonical_bytes(obj)).hexdigest()
