#!/usr/bin/env python3
"""infra/govern/feed.py — P5-T02 monitor-feed helpers (prose-clean core).

Pure logic behind the dashboard's Server-Sent-Events push (replacing the 1.5s client poll) with pagination:
page a list into a bounded window with page metadata; frame a value-free snapshot as an SSE data event; hash
a snapshot's content so the stream pushes only on a real change. No I/O, no connection state -- the govd
server holds the long-lived connection; this module decides WHAT to send.
"""
from __future__ import annotations
import hashlib
import json


def paginate(items, page, limit):
    total = len(items)
    limit = max(1, int(limit))
    pages = max(1, (total + limit - 1) // limit)
    page = min(max(1, int(page)), pages)
    start = (page - 1) * limit
    return {"items": items[start:start + limit], "page": page, "pages": pages,
            "total": total, "limit": limit}


def sse_frame(obj):
    return "data: " + json.dumps(obj, separators=(",", ":")) + "\n\n"


def digest(obj):
    return hashlib.sha256(json.dumps(obj, sort_keys=True, default=str).encode()).hexdigest()
