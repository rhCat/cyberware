"""P5-T05 — W3C traceparent + in-toto run provenance (infra/govern/tracing.py).

Pins traceparent parse/format/child-span and the cross-plane trace + in-toto statement so the claim→grant→
step trace is retrievable by run_id and the cyberware/run@v1 attestation is well-formed + value-free."""
from __future__ import annotations

from infra.govern import tracing as T


def test_parse_valid_and_rejects_malformed_or_zero():
    tp = T.parse_traceparent("00-" + "a" * 32 + "-" + "b" * 16 + "-01")
    assert tp == {"version": "00", "trace_id": "a" * 32, "span_id": "b" * 16, "flags": "01"}
    assert T.parse_traceparent("") is None
    assert T.parse_traceparent("00-xyz-bbbb-01") is None                 # non-hex
    assert T.parse_traceparent("00-" + "0" * 32 + "-" + "b" * 16 + "-01") is None   # all-zero trace id invalid
    assert T.parse_traceparent("00-" + "a" * 32 + "-" + "0" * 16 + "-01") is None   # all-zero span id invalid


def test_new_and_child_preserve_trace_and_change_span():
    root = T.new_traceparent()
    rp = T.parse_traceparent(root)
    assert rp is not None and rp["flags"] == "01"
    child = T.child_span(root)
    cp = T.parse_traceparent(child)
    assert cp["trace_id"] == rp["trace_id"]                              # SAME trace across the hop
    assert cp["span_id"] != rp["span_id"]                                # but a fresh span
    assert T.child_span("garbage") is None


def _record():
    tp = "00-" + "c" * 32 + "-" + "d" * 16 + "-01"
    return {"run_id": "r1", "ts": "2026-06-22T00:00:00Z", "skill": "fs", "perk": "read",
            "decision": "allow", "principal": "local", "plan_sha": "deadbeef", "traceparent": tp,
            "events": [{"type": "granted", "step": "1", "span": T.child_span(tp)},
                       {"type": "step_result", "step": "1", "status": "ok", "span": T.child_span(tp)}]}


def test_trace_of_reassembles_claim_grant_step_under_one_trace():
    tr = T.trace_of(_record())
    assert tr["run_id"] == "r1" and tr["trace_id"] == "c" * 32
    planes = [s["plane"] for s in tr["spans"]]
    assert planes == ["claim", "granted", "step_result"]                 # full cross-plane trace
    assert all(s["span_id"] for s in tr["spans"])                        # every hop has a span id
    assert T.trace_of({"run_id": "x", "events": []}) is None             # no traceparent -> no trace


def test_intoto_statement_is_well_formed_and_value_free():
    st = T.intoto_statement(_record())
    assert st["_type"] == "https://in-toto.io/Statement/v1"
    assert st["predicateType"] == "https://cyberware.dev/run/v1"         # cyberware/run@v1
    assert st["subject"][0]["digest"]["sha256"] == "deadbeef"
    assert st["predicate"]["plan_sha256"] == "deadbeef"
    assert st["predicate"]["trace_id"] == "c" * 32
    assert [s["step"] for s in st["predicate"]["steps"]] == ["1", "1"]
    blob = __import__("json").dumps(st)
    assert "token" not in blob and "secret" not in blob                  # value-free provenance
