"""P5-T02 — monitor-feed helpers (infra/govern/feed.py): pagination, SSE framing, change-digest.

Pins both sides of the arithmetic + formatting so the mutants (the ceil-division, the 1-based page clamp,
the slice bounds, the string concat, the hash) are killed — the dashboard's SSE push (replacing the 1.5s
poll) depends on these to page correctly and to push only on a real change."""
from __future__ import annotations

import json

from infra.govern import feed


def test_paginate_first_page_and_metadata():
    p = feed.paginate(list(range(0, 25)), 1, 10)
    assert p["items"] == list(range(0, 10))      # exactly the first window, not 0..9 off by one
    assert p["page"] == 1 and p["pages"] == 3 and p["total"] == 25 and p["limit"] == 10


def test_paginate_middle_and_last_partial_page():
    items = list(range(0, 25))
    assert feed.paginate(items, 2, 10)["items"] == list(range(10, 20))
    last = feed.paginate(items, 3, 10)
    assert last["items"] == list(range(20, 25)) and last["page"] == 3   # partial last page (5 items)


def test_paginate_ceil_division_exact_multiple():
    assert feed.paginate(list(range(0, 20)), 1, 10)["pages"] == 2       # 20/10 == 2, not 3 (ceil edge)
    assert feed.paginate(list(range(0, 21)), 1, 10)["pages"] == 3       # 21 -> 3 pages


def test_paginate_clamps_out_of_range_and_bad_limit():
    items = list(range(0, 25))
    assert feed.paginate(items, 99, 10)["page"] == 3        # over the last page -> clamped to pages
    assert feed.paginate(items, 0, 10)["page"] == 1         # below 1 -> clamped to 1
    assert feed.paginate(items, -5, 10)["page"] == 1
    assert feed.paginate(items, 1, 0)["limit"] == 1         # limit < 1 -> at least 1
    empty = feed.paginate([], 1, 10)
    assert empty["items"] == [] and empty["pages"] == 1 and empty["total"] == 0


def test_sse_frame_is_a_single_data_event():
    f = feed.sse_frame({"a": 1, "b": [2, 3]})
    assert f.startswith("data: ") and f.endswith("\n\n")    # exactly one SSE data event
    assert json.loads(f[len("data: "):].strip()) == {"a": 1, "b": [2, 3]}


def test_digest_is_stable_and_change_sensitive():
    a = {"x": 1, "y": [1, 2]}
    assert feed.digest(a) == feed.digest({"y": [1, 2], "x": 1})     # key order does not matter (stable)
    assert feed.digest(a) != feed.digest({"x": 2, "y": [1, 2]})     # a real change flips the digest
    assert len(feed.digest(a)) == 64                                 # sha256 hex
