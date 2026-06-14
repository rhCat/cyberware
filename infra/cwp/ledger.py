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


# ── Ledger-v2 write + verify path (P1-T01) ─────────────────────────────────────────────────────────
# An append-only chain: genesis BINDS the chain to its origin {run_id, plan_sha} (both digested into the
# genesis link), then each record's `prev` = the prior link's digest and `seq` strictly increases. Because
# the genesis link covers run_id+plan_sha, replaying the same records under a different origin recomputes a
# different genesis digest and the first record's stored `prev` no longer matches — the genesis-non-
# transplant property. verify_chain is the cryptographic re-verification the Go anchor (P1-T04) reproduces.

ZERO = "0" * 64


def genesis(run_id, plan_sha, schema=CURRENT_MAJOR):
    """The first entry of a Ledger-v2 chain, binding it to its origin. run_id + plan_sha are ordinary
    link fields (link_of keeps everything but `prev`), so the next record's `prev` covers them."""
    return {"type": "genesis", "schema": schema, "seq": 0,
            "run_id": run_id, "plan_sha": plan_sha, "prev": ZERO}


def append(entries, record, schema=CURRENT_MAJOR):
    """Link `record` onto a non-empty chain (prev = prior link's digest, seq = prior seq + 1), append it
    to `entries` in place, and return the completed record."""
    prev = entries[-1]
    rec = dict(record)
    rec["seq"] = int(prev.get("seq", len(entries) - 1)) + 1
    rec["prev"] = link_digest(link_of(prev), schema)
    entries.append(rec)
    return rec


def _seq_int(v):
    """seq must be a real integer — bool is rejected (True/False are not sequence numbers)."""
    return isinstance(v, int) and not isinstance(v, bool)


def verify_chain(entries, schema, expect_run_id=None, expect_plan_sha=None):
    """Recompute AND structurally validate a prev-hash chain (schema major N or N-1). Returns
    (ok, problems); `problems` names the FIRST offending record. A provenance chain must be a faithful,
    origin-bound record — not merely internally self-consistent — so this enforces:

      * non-empty, and entry[0] is THE GENESIS: type=='genesis', prev==all-zero, and it BINDS an origin
        (run_id+plan_sha for an execution chain, or supersedes/supersedes_head for a migration chain).
        A headless or genesis-less chain is rejected (else a decapitated suffix would verify clean).
      * exactly one genesis: no later record may be type=='genesis' or carry the all-zero prev.
      * seq is mandatory + integer on every NON-genesis record and CONTIGUOUS (+1) — so a deleted or
        inserted record (even with every prev re-linked) shows as a gap. The genesis seq is optional.
      * each record's prev == the prior link's digest under `schema` (catches tamper / partial transplant).
      * NON-TRANSPLANT: when expect_run_id / expect_plan_sha are supplied (sourced OUT-OF-BAND, never from
        the file under test), the genesis must match them. Without them the chain is proven only internally
        consistent + origin-well-formed; the same records re-linked under a different genesis would verify
        clean, so certifying non-transplant REQUIRES the expected origin (or the signed Go anchor, P1-T04)."""
    if not entries:
        return False, ["empty chain — a provenance chain must contain at least the genesis"]
    g = entries[0]
    if not isinstance(g, dict):
        return False, ["entry[0] (genesis) is not a JSON object"]
    problems = []
    if g.get("type") != "genesis":
        problems.append(f"entry[0] is not a genesis record (type={g.get('type')!r})")
    if g.get("prev") != ZERO:
        problems.append("entry[0] (genesis) prev is not the all-zero root")
    if not ((g.get("run_id") and g.get("plan_sha")) or g.get("supersedes_head") or g.get("supersedes")):
        problems.append("entry[0] (genesis) binds no origin (need run_id+plan_sha, or supersedes for a migration)")
    if expect_run_id is not None and g.get("run_id") != expect_run_id:
        problems.append(f"genesis run_id {g.get('run_id')!r} != expected {expect_run_id!r} (transplant)")
    if expect_plan_sha is not None and g.get("plan_sha") != expect_plan_sha:
        problems.append(f"genesis plan_sha {g.get('plan_sha')!r} != expected {expect_plan_sha!r} (transplant)")
    if problems:
        return False, problems
    prev_digest, last_seq = ZERO, None
    for i, e in enumerate(entries):
        if not isinstance(e, dict):
            problems.append(f"entry[{i}] is not a JSON object")
            break
        who = f"seq={e.get('seq')} id={e.get('task_id', e.get('type', '?'))}"
        if i > 0 and (e.get("type") == "genesis" or e.get("prev") == ZERO):
            problems.append(f"entry[{i}] ({who}): a second genesis / all-zero-prev record mid-chain")
            break
        if e.get("prev") != prev_digest:
            problems.append(f"entry[{i}] ({who}): prev {str(e.get('prev'))[:12]}… != "
                            f"recomputed {prev_digest[:12]}… (tamper or transplant)")
            break
        seq = e.get("seq")
        if i == 0:
            last_seq = seq if _seq_int(seq) else None        # genesis seq optional; seeds contiguity if present
        elif not _seq_int(seq):
            problems.append(f"entry[{i}] ({who}): seq {seq!r} missing or not an integer (replay/insert guard)")
            break
        elif last_seq is not None and seq != last_seq + 1:
            problems.append(f"entry[{i}] ({who}): seq {seq} not contiguous after {last_seq} (insert/delete)")
            break
        else:
            last_seq = seq
        prev_digest = link_digest(link_of(e), schema)
    return (not problems), problems


def write_chain(path, entries):
    """Persist a chain as append-only JSONL — one canonical JSON object per line, in order."""
    with open(path, "w") as f:
        for e in entries:
            f.write(json.dumps(e, sort_keys=True) + "\n")


def append_line(path, record):
    """Append a single already-linked record as one JSONL line (the durable write is hardened in P1-T02)."""
    with open(path, "a") as f:
        f.write(json.dumps(record, sort_keys=True) + "\n")


def read_chain(path):
    """Load a chain from JSONL (one object per line), a JSON list, or a {entries:[…]} object.
    Returns (entries, schema)."""
    text = open(path).read()
    try:
        obj = json.loads(text)
        if isinstance(obj, dict) and "entries" in obj:
            return obj["entries"], obj.get("schema", CURRENT_MAJOR)
        if isinstance(obj, list):
            return obj, (obj[0].get("schema", CURRENT_MAJOR) if obj else CURRENT_MAJOR)
    except json.JSONDecodeError:
        pass
    entries = [json.loads(ln) for ln in text.splitlines() if ln.strip()]
    return entries, (entries[0].get("schema", CURRENT_MAJOR) if entries else CURRENT_MAJOR)
