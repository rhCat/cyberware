"""RFC 8785 JCS canonicalizer (infra/cwp/canonical.py) — the single canonical-bytes path (P0-T02).

The number cases are pinned against ECMAScript `Number::toString` (the values JS `String(x)` produces),
which is the part RFC 8785 §3.2.2.3 mandates and the part naive serializers get wrong.
"""
import json

import pytest

from infra.cwp import canonical as c


@pytest.mark.parametrize("x,expected", [
    (0, "0"), (0.0, "0"), (-0.0, "0"),
    (1, "1"), (100, "100"), (-42, "-42"),
    (4.5, "4.5"), (0.002, "0.002"),
    (1e30, "1e+30"), (1e-27, "1e-27"),
    (1e20, "100000000000000000000"),       # n == 21 → fixed notation, not exponential
    (1e21, "1e+21"),                        # n == 22 → exponential
    (1e-6, "0.000001"),                     # n == -5 → leading-zero fixed
    (1e-7, "1e-7"),                         # n == -6 → exponential, no zero-padded exponent
    (123456789.0, "123456789"),
])
def test_es6_number_formatting_matches_javascript(x, expected):
    assert c.canonicalize(x) == expected


def test_object_keys_sort_by_utf16_code_units():
    # 'é' is U+00E9 (> 'z' U+007A), so it sorts AFTER z, not alphabetically before it
    assert c.canonicalize({"z": 1, "a": 2, "b": 3, "é": 4}) == '{"a":2,"b":3,"z":1,"é":4}'


def test_string_escaping_is_minimal_per_rfc8785():
    assert c.canonicalize('"') == '"\\""'
    assert c.canonicalize("\\") == '"\\\\"'
    assert c.canonicalize("\n") == '"\\n"'
    assert c.canonicalize("\t") == '"\\t"'
    assert c.canonicalize("\x0f") == '"\\u000f"'      # a non-short C0 control → \u00xx (lowercase)
    assert c.canonicalize("/") == '"/"'               # forward slash is NOT escaped
    assert c.canonicalize("€") == '"€"'               # non-ASCII stays literal (UTF-8)


def test_no_insignificant_whitespace_and_nesting():
    assert c.canonicalize({"a": [1, 2, {"b": True}], "c": None}) == '{"a":[1,2,{"b":true}],"c":null}'


def test_canonical_bytes_is_utf8_and_digest_is_stable():
    obj = {"numbers": [1e30, 4.5, 1e-27], "literals": [None, True, False], "s": "€"}
    assert c.canonical_bytes(obj) == c.canonicalize(obj).encode("utf-8")
    # order of construction must not matter — the canonical form (and its digest) is identical
    same = {"s": "€", "literals": [None, True, False], "numbers": [1e30, 4.5, 1e-27]}
    assert c.digest(obj) == c.digest(same)
    assert len(c.digest(obj)) == 64


def test_round_trips_through_json_load():
    obj = {"k": [1, "two", 3.5, False, None], "ünïcøde": "✓"}
    once = c.canonicalize(obj)
    assert c.canonicalize(json.loads(once)) == once       # canonicalizing the parse is a fixed point


def test_nan_and_infinity_are_rejected():
    for bad in (float("nan"), float("inf"), float("-inf")):
        with pytest.raises(ValueError):
            c.canonicalize(bad)


def test_non_string_keys_are_rejected():
    with pytest.raises(TypeError):
        c.canonicalize({1: "a"})
