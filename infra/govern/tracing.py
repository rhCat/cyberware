#!/usr/bin/env python3
"""infra/govern/tracing.py — P5-T05 W3C traceparent with in-toto run provenance (prose-clean core).

A run carries ONE W3C `traceparent` (`00-<trace32>-<span16>-<flags2>`) from the agent's claim; govd derives a
child span per plane hop (grant, step) under the same trace id, so the claim->grant->exod-step trace is
retrievable by run_id. `intoto_statement` renders a run record as an in-toto Statement v1 over a
`cyberware/run@v1` predicate -- value-free provenance (no values, secrets, output). No I/O, no randomness in
the parse/format/predicate path; only the fresh-id helpers draw entropy.
"""
from __future__ import annotations
import re
import secrets

CWRUN_PREDICATE = "https://cyberware.dev/run/v1"          # cyberware/run@v1
_ZERO_TRACE = "0" * 32
_ZERO_SPAN = "0" * 16
_TP = re.compile(r"00-([0-9a-f]{32})-([0-9a-f]{16})-([0-9a-f]{2})")
_SPAN_EVENTS = ("granted", "step_result", "step_refused")


def parse_traceparent(s):
    """W3C traceparent -> {version, trace_id, span_id, flags}; None if malformed / all-zero id."""
    m = _TP.fullmatch(s or "")          # fullmatch (not match) so a trailing newline can't slip through `$`
    if m is None:
        return None
    trace_id, span_id, flags = m.groups()
    if trace_id == _ZERO_TRACE or span_id == _ZERO_SPAN:
        return None
    return {"version": "00", "trace_id": trace_id, "span_id": span_id, "flags": flags}


def format_traceparent(trace_id, span_id, flags="01"):
    return f"00-{trace_id}-{span_id}-{flags}"


def new_traceparent():
    """A fresh root traceparent (sampled): a new trace id with a new root span id."""
    return format_traceparent(secrets.token_hex(16), secrets.token_hex(8), "01")


def child_span(traceparent):
    """A new span under the SAME trace -- the next plane's hop. None if the parent is malformed."""
    p = parse_traceparent(traceparent)
    if p is None:
        return None
    return format_traceparent(p["trace_id"], secrets.token_hex(8), p["flags"])


def trace_of(record):
    """Reassemble a run's cross-plane trace from its record: the claim span with one span per recorded plane
    hop (grant / step_result / step_refused), all under the run's trace id. None if the run has no trace."""
    p = parse_traceparent(record.get("traceparent") or "")
    if p is None:
        return None
    spans = [{"plane": "claim", "span_id": p["span_id"], "skill": record.get("skill"),
              "perk": record.get("perk"), "decision": record.get("decision")}]
    for e in record.get("events", []):
        if e.get("type") in _SPAN_EVENTS:
            tp = parse_traceparent(e.get("span") or "")
            spans.append({"plane": e["type"], "step": e.get("step"), "status": e.get("status"),
                          "span_id": tp["span_id"] if tp else None})
    return {"run_id": record.get("run_id"), "trace_id": p["trace_id"],
            "traceparent": record.get("traceparent"), "spans": spans}


def intoto_statement(record):
    """An in-toto Statement v1 over a `cyberware/run@v1` predicate for a run record -- value-free provenance."""
    p = parse_traceparent(record.get("traceparent") or "")
    steps = [{"step": e.get("step"), "type": e.get("type"), "status": e.get("status")}
             for e in record.get("events", []) if e.get("type") in _SPAN_EVENTS]
    return {
        "_type": "https://in-toto.io/Statement/v1",
        "subject": [{"name": str(record.get("run_id")),
                     "digest": {"sha256": record.get("plan_sha") or ""}}],
        "predicateType": CWRUN_PREDICATE,
        "predicate": {
            "run_id": record.get("run_id"), "ts": record.get("ts"),
            "trace_id": p["trace_id"] if p else None,
            "skill": record.get("skill"), "perk": record.get("perk"),
            "decision": record.get("decision"), "principal": record.get("principal"),
            "plan_sha256": record.get("plan_sha") or "", "steps": steps,
        },
    }
