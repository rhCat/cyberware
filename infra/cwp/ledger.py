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
import json
import os
import uuid

# The chain-VERIFICATION surface (link digests + verify_chain) lives in chainverify.py — a prose-clean
# executable core that is the R3 mutation target (cws-mutate / mut-chain-verifier, P1-T10). ledger.py
# re-exports it so this stays the one import site AND chainverify is the single source of truth (no drift:
# the code the system runs IS the code the mutation gate tests). ledger.py keeps the WRITE path below.
from infra.cwp.chainverify import (  # noqa: F401
    CURRENT_MAJOR, ZERO, head_of, link_digest, link_digest_v1, link_digest_v2, link_of, verify_chain,
)


# ── Ledger-v2 write path (P1-T01) ──────────────────────────────────────────────────────────────────
# An append-only chain: genesis BINDS the chain to its origin {run_id, plan_sha} (both digested into the
# genesis link), then each record's `prev` = the prior link's digest and `seq` increases. verify_chain
# (in chainverify) is the cryptographic re-verification the Go anchor (P1-T04) reproduces.


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
