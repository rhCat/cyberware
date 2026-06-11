#!/usr/bin/env python3
"""net_dns — resolve a hostname to its addresses. Reads HOST, RECORD_STORE from env; emits JSON."""
from __future__ import annotations
import json
import os
import socket
import sys


def main() -> int:
    """Resolve HOST and write dns.json."""
    host = os.environ["HOST"]
    store = os.environ["RECORD_STORE"].rstrip("/")
    out = os.path.join(store, "dns.json")
    try:
        canonical, _aliases, addrs = socket.gethostbyname_ex(host)
        result = {"tool": "net_dns", "status": "ok", "host": host, "canonical": canonical, "addresses": addrs, "report": out}
    except OSError as exc:
        result = {"tool": "net_dns", "status": "error", "host": host, "reason": str(exc), "report": out}
    json.dump(result, open(out, "w"), indent=2)
    print(json.dumps(result))
    return 0 if result["status"] == "ok" else 1


if __name__ == "__main__":
    sys.exit(main())
