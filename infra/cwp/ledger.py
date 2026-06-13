#!/usr/bin/env python3
"""infra/cwp/ledger.py — done-ledger chain digests, schema-major aware (P0-T04 / inflight.md decision 4).

A done-ledger is a prev-hash chain: each entry's `prev` is the digest of the PRIOR entry's *link* (the
entry minus its own `prev`). The digest form is versioned by the chain's schema major:

  - major 1 (FROZEN): sha256 over json.dumps(link, sort_keys=True) — the original form. Kept ONLY so the
    existing v1 chain stays verifiable; never used for new chains.
  - major 2: canonical.digest(link) — the RFC-8785 JCS form (cwp.canonical), reproduced by the Go anchor.

Decision 4: a schema migration MUST be a NEW chain carrying a cross-reference to the old one (never an
in-place rewrite), and verifiers MUST support majors N and N-1. This module is the single place the legacy
json.dumps-into-a-hash form lives — inside infra/cwp, which the digest-cutover lint (cws-conform/digestlint)
exempts, so the cutover criterion holds everywhere else while v1 stays auditable.
"""
from __future__ import annotations
import hashlib
import json

from infra.cwp import canonical

CURRENT_MAJOR = 2


def link_of(entry):
    """The chained content of an entry: everything except its own back-pointer `prev`."""
    return {k: v for k, v in entry.items() if k != "prev"}


def link_digest_v1(link):
    """FROZEN major-1 form — sha256 over json.dumps(sort_keys). Do not use for new chains."""
    return hashlib.sha256(json.dumps(link, sort_keys=True).encode()).hexdigest()


def link_digest_v2(link):
    """Major-2 form — canonical (RFC-8785 JCS) digest, reproduced cross-language by the Go anchor."""
    return canonical.digest(link)


def link_digest(link, schema):
    """Digest a link under its chain's schema major (verifiers support N and N-1: majors 2 and 1)."""
    if schema == 1:
        return link_digest_v1(link)
    if schema == 2:
        return link_digest_v2(link)
    raise ValueError(f"unsupported done-ledger schema major: {schema!r} (verifiers support 1 and 2)")


def head_of(entries, schema):
    """The chain tip: the digest the NEXT entry's `prev` must equal — i.e. the last entry's link digest
    under `schema`. Returns the all-zero genesis pointer for an empty chain."""
    head = "0" * 64
    for e in entries:
        head = link_digest(link_of(e), schema)
    return head
