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
import fcntl
import hashlib
import json
import os
import uuid

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


# ── durability (P1-T02): O_APPEND + flock + fsync + atomic snapshot + torn-tail recovery ────────────
# A crash mid-write must never lose a committed record nor corrupt the chain. Single appends serialize
# under an exclusive lock and are fsync'd before the lock drops; snapshots are written to a sibling tmp and
# os.replace'd (atomic) with a directory fsync; a read recovers a crash-truncated FINAL line (recording the
# truncation) while still surfacing mid-chain corruption. (Advisory flock on a LOCAL fs — not NFS-safe.)


def _parse_jsonl(text, allow_torn_tail=False):
    """Parse JSONL into (entries, truncation). A crash-truncated FINAL line (unparseable) is dropped and
    reported when allow_torn_tail; a non-final unparseable line is real corruption and raises."""
    lines = [ln for ln in text.splitlines() if ln.strip()]
    entries, truncation, last_seq = [], None, None
    for i, ln in enumerate(lines):
        try:
            e = json.loads(ln)
        except json.JSONDecodeError:
            if allow_torn_tail and i == len(lines) - 1:      # a torn tail is a crash artifact, not corruption
                truncation = {"was_torn": True, "last_valid_seq": last_seq, "torn_line_idx": i}
                break
            raise
        entries.append(e)
        if isinstance(e, dict) and isinstance(e.get("seq"), int) and not isinstance(e.get("seq"), bool):
            last_seq = e["seq"]
    return entries, truncation


def _write_all(fd, data: bytes):
    """Write ALL of `data`, advancing past short writes. os.write may transfer FEWER bytes than requested
    without raising (ENOSPC, a partial EINTR, RLIMIT_FSIZE) — ignoring the count would commit a torn line.
    A genuinely stuck write (e.g. a full disk) raises OSError on the next iteration, which propagates as a
    FAILED write rather than a silently-truncated record."""
    mv = memoryview(data)
    off = 0
    while off < len(mv):
        off += os.write(fd, mv[off:])


def _tail_record(fd):
    """Return (last_complete_record | None, clean_end_offset): the chain tip and the byte offset just past
    the last newline (any bytes beyond it are a crash-torn fragment). Reads a window backward from EOF, so
    extending a chain is O(1) in its depth — NOT a full re-read per append. Widens the window only if a
    single line spans it (huge records); a file with no newline at all is entirely torn."""
    size = os.lseek(fd, 0, os.SEEK_END)
    if size == 0:
        return None, 0
    window = min(size, 65536)
    while True:
        os.lseek(fd, size - window, os.SEEK_SET)
        chunk = os.read(fd, window)
        last_nl = chunk.rfind(b"\n")
        if last_nl == -1:                                    # no complete line in the window
            if window >= size:
                return None, 0                               # nothing newline-terminated anywhere — all torn
            window = min(size, window * 4)
            continue
        clean_end = (size - window) + last_nl + 1            # byte just past the last complete line
        start = chunk.rfind(b"\n", 0, last_nl)               # newline before that last line
        if start == -1 and window < size:                    # the last line began before the window
            window = min(size, window * 4)
            continue
        last_line = chunk[start + 1:last_nl]
        return (json.loads(last_line.decode()) if last_line.strip() else None), clean_end


def _atomic_write(path, data: bytes):
    """Write bytes to `path` atomically + durably: a sibling tmp, fsync, os.replace, then a dir fsync.
    A crash leaves the OLD file intact (never a half-written one)."""
    d = os.path.dirname(os.path.abspath(path)) or "."
    tmp = f"{path}.tmp.{os.getpid()}.{uuid.uuid4().hex[:8]}"
    try:
        fd = os.open(tmp, os.O_CREAT | os.O_WRONLY | os.O_EXCL, 0o644)
        try:
            _write_all(fd, data)
            os.fsync(fd)
        finally:
            os.close(fd)
        os.replace(tmp, path)                                # POSIX-atomic within the same filesystem
    except BaseException:
        if os.path.exists(tmp):
            try:
                os.unlink(tmp)
            except OSError:
                pass
        raise
    dfd = None
    try:                                                     # make the rename durable (best-effort)
        dfd = os.open(d, os.O_RDONLY)
        os.fsync(dfd)
    except OSError:
        pass
    finally:
        if dfd is not None:
            os.close(dfd)                                    # close even if fsync raised (no fd leak)


def write_chain(path, entries):
    """Persist a chain as append-only JSONL — written atomically (tmp + fsync + os.replace + dir fsync)."""
    _atomic_write(path, "".join(json.dumps(e, sort_keys=True) + "\n" for e in entries).encode())


def write_object_atomic(path, obj):
    """Persist a JSON object (e.g. the {chain, schema, entries} done-ledger) atomically + durably."""
    _atomic_write(path, (json.dumps(obj, indent=2) + "\n").encode())


def _heal_and_append(fd, line: bytes, clean_end, size):
    """Drop any torn (newline-less) trailing bytes (ftruncate to clean_end) so a prior crash fragment can
    never become mid-chain, then full-write `line` at that offset + fsync. Caller holds flock(LOCK_EX)."""
    if clean_end < size:
        os.ftruncate(fd, clean_end)                          # heal a crash-truncated tail before appending
    os.lseek(fd, clean_end, os.SEEK_SET)
    _write_all(fd, line)
    os.fsync(fd)                                             # durable before the lock drops


def append_line(path, record):
    """Append one already-linked record as a crash-safe JSONL line: exclusive lock, heal a torn tail,
    full write, fsync (ordering is load-bearing — flock before write, fsync before unlock)."""
    fd = os.open(path, os.O_RDWR | os.O_CREAT, 0o644)
    try:
        fcntl.flock(fd, fcntl.LOCK_EX)
        _tail, clean_end = _tail_record(fd)
        size = os.lseek(fd, 0, os.SEEK_END)
        _heal_and_append(fd, (json.dumps(record, sort_keys=True) + "\n").encode(), clean_end, size)
    finally:
        fcntl.flock(fd, fcntl.LOCK_UN)
        os.close(fd)


def durable_append(path, record, schema=CURRENT_MAJOR):
    """Concurrency-safe chain extension. Holds ONE exclusive lock across {read current tip → compute prev
    + seq → heal torn tail → append → fsync}, so N processes serialize into a single valid prev-hash chain
    (no two writers ever compute the same prev/seq, and a crash-truncated tail is dropped before the new
    record so it can never glue into mid-chain corruption). Returns the linked record. The whole critical
    section under flock is the correctness guarantee — never link from a stale in-memory copy. O(1) in chain
    depth (reads only the tip), so it scales to the acceptance's 16x5000."""
    fd = os.open(path, os.O_RDWR | os.O_CREAT, 0o644)
    try:
        fcntl.flock(fd, fcntl.LOCK_EX)
        tip, clean_end = _tail_record(fd)
        size = os.lseek(fd, 0, os.SEEK_END)
        rec = dict(record)
        rec["seq"] = int(tip.get("seq", 0)) + 1 if tip else 0
        rec["prev"] = link_digest(link_of(tip), schema) if tip else ZERO
        _heal_and_append(fd, (json.dumps(rec, sort_keys=True) + "\n").encode(), clean_end, size)
        return rec
    finally:
        fcntl.flock(fd, fcntl.LOCK_UN)
        os.close(fd)


def read_chain(path, allow_torn_tail=False):
    """Load a chain from a {entries:[…]} object, a JSON list, or JSONL. Returns (entries, schema) — or
    (entries, schema, truncation_or_None) when allow_torn_tail, where a crash-truncated final JSONL line is
    dropped and reported (mid-chain corruption still raises)."""
    text = open(path).read()
    try:
        obj = json.loads(text)
        if isinstance(obj, dict) and "entries" in obj:
            entries, schema = obj["entries"], obj.get("schema", CURRENT_MAJOR)
            return (entries, schema, None) if allow_torn_tail else (entries, schema)
        if isinstance(obj, list):
            schema = obj[0].get("schema", CURRENT_MAJOR) if obj else CURRENT_MAJOR
            return (obj, schema, None) if allow_torn_tail else (obj, schema)
    except json.JSONDecodeError:
        pass
    entries, truncation = _parse_jsonl(text, allow_torn_tail)
    schema = entries[0].get("schema", CURRENT_MAJOR) if entries else CURRENT_MAJOR
    return (entries, schema, truncation) if allow_torn_tail else (entries, schema)
