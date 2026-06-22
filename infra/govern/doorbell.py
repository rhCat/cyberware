#!/usr/bin/env python3
"""infra/govern/doorbell.py — P3-T16 SECURITY.md doorbell check (M12: willingness has an address).

A presence check, nothing more: the repo's SECURITY.md must name a CONTACT, an encrypted-reporting
KEY/mechanism, and an acknowledgement SLA. The doorbell only asserts the door exists with a bell on it.
"""
from __future__ import annotations
import os
import re

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def check_doorbell(text):
    """Return {contact, key, ack_sla, ok} for a SECURITY.md body. `contact`: an email or a GitHub private
    advisory channel. `key`: an encrypted-reporting mechanism (age / PGP / GitHub encryption). `ack_sla`: a
    concrete time window paired with an acknowledge/respond commitment."""
    low = text.lower()
    contact = bool(re.search(r"[\w.+-]+@[\w-]+\.\w+", text)) or ("report a vulnerability" in low)
    key = ("pgp" in low) or ("gpg" in low) or ("encrypt" in low) or ("age" in low and "key" in low)
    has_window = bool(re.search(r"\b\d+\s*(hour|hr|day|business day)", low))
    commits = ("acknowledg" in low) or ("respond" in low) or ("sla" in low)
    ack_sla = has_window and commits
    return {"contact": contact, "key": key, "ack_sla": ack_sla, "ok": contact and key and ack_sla}


def doorbell_selftest(root=None):
    """Read <root>/SECURITY.md (default the repo root) and check the doorbell. `ok` is False (never raises)
    when the file is absent — the doorbell has not been installed."""
    path = os.path.join(root or ROOT, "SECURITY.md")
    if not os.path.isfile(path):
        return {"exists": False, "contact": False, "key": False, "ack_sla": False, "ok": False}
    r = check_doorbell(open(path).read())
    r["exists"] = True
    return r


if __name__ == "__main__":
    import json
    import sys
    res = doorbell_selftest()
    print(json.dumps(res, indent=2))
    sys.exit(0 if res["ok"] else 1)
