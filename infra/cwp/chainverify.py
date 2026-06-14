#!/usr/bin/env python3
# infra/cwp/chainverify.py: the Ledger-v2 chain-verification surface (P1-T01), extracted from ledger.py
# as a prose-clean executable core. ledger.py re-exports these names (single source of truth); the R3
# mutation gate (cws-mutate / mut-chain-verifier, P1-T10) mutates this file. Comments here carry NO
# space-anchored operator tokens, so every surviving mutant is a real, test-killable comparison rather
# than an un-killable operator-word inside prose. Messages keep the keyword a verdict needs (transplant,
# contiguous, genesis) without those tokens.
from __future__ import annotations
import hashlib
import json

from infra.cwp import canonical

CURRENT_MAJOR = 2
ZERO = "0" * 64


def link_of(entry):
    # the chained content of an entry: every field except its back-pointer prev
    return {k: v for k, v in entry.items() if k != "prev"}


def link_digest_v1(link):
    # FROZEN major-1 form: sha256 over json.dumps(sort_keys). Never used for new chains.
    return hashlib.sha256(json.dumps(link, sort_keys=True).encode()).hexdigest()


def link_digest_v2(link):
    # major-2 form: canonical RFC-8785 JCS digest, reproduced cross-language by the Go anchor
    return canonical.digest(link)


def link_digest(link, schema):
    # digest a link under its chain's schema major (verifiers carry majors 2, 1)
    if schema == 1:
        return link_digest_v1(link)
    if schema == 2:
        return link_digest_v2(link)
    raise ValueError(f"unsupported done-ledger schema major: {schema!r}")


def head_of(entries, schema):
    # the chain tip: the digest the next entry's prev must equal; all-zero root for an empty chain
    head = ZERO
    for e in entries:
        head = link_digest(link_of(e), schema)
    return head


def _seq_int(v):
    # a sequence number must be a real integer; a bool is rejected
    return isinstance(v, int) and not isinstance(v, bool)


def verify_chain(entries, schema, expect_run_id=None, expect_plan_sha=None):
    # Recompute, structurally validate a prev-hash chain. Returns (ok, problems); problems names the first
    # offending record. A provenance chain must be a faithful, origin-bound record:
    #   * non-empty, entry[0] is the genesis (type genesis, prev all-zero, binds an origin via
    #     run_id/plan_sha for an execution chain, supersedes for a migration). A headless chain is rejected.
    #   * exactly one genesis: no later record is the genesis type, none carries the all-zero prev.
    #   * seq is mandatory, integer, contiguous on every non-genesis record (a deleted/inserted record
    #     shows as a gap). The genesis seq is optional.
    #   * each record's prev recomputes to the prior link's digest (tamper, partial transplant).
    #   * non-transplant: when expect_run_id/expect_plan_sha are given out-of-band, the genesis must match.
    if not entries:
        return False, ["empty chain: a provenance chain needs at least the genesis"]
    g = entries[0]
    if not isinstance(g, dict):
        return False, ["entry[0] genesis is not a JSON object"]
    problems = []
    if g.get("type") != "genesis":
        problems.append(f"entry[0] is not a genesis record (type={g.get('type')!r})")
    if g.get("prev") != ZERO:
        problems.append("entry[0] genesis prev is not the all-zero root")
    if not ((g.get("run_id") and g.get("plan_sha")) or g.get("supersedes_head") or g.get("supersedes")):
        problems.append("entry[0] genesis binds no origin (need run_id/plan_sha, supersedes for a migration)")
    if expect_run_id is not None and g.get("run_id") != expect_run_id:
        problems.append(f"genesis run_id {g.get('run_id')!r} mismatch expected {expect_run_id!r} (transplant)")
    if expect_plan_sha is not None and g.get("plan_sha") != expect_plan_sha:
        problems.append(f"genesis plan_sha {g.get('plan_sha')!r} mismatch expected {expect_plan_sha!r} (transplant)")
    if problems:
        return False, problems
    prev_digest, last_seq = ZERO, None
    for i, e in enumerate(entries):
        if not isinstance(e, dict):
            problems.append(f"entry[{i}] is not a JSON object")
            break
        who = f"seq={e.get('seq')} id={e.get('task_id', e.get('type', '?'))}"
        if i > 0 and (e.get("type") == "genesis" or e.get("prev") == ZERO):
            problems.append(f"entry[{i}] ({who}): a second genesis, zero-prev record mid-chain")
            break
        if e.get("prev") != prev_digest:
            problems.append(f"entry[{i}] ({who}): prev {str(e.get('prev'))[:12]} recompute mismatch "
                            f"{prev_digest[:12]} (tamper, transplant)")
            break
        seq = e.get("seq")
        if i == 0:
            last_seq = seq if _seq_int(seq) else None
        elif not _seq_int(seq):
            problems.append(f"entry[{i}] ({who}): seq {seq!r} missing, not an integer (replay-insert guard)")
            break
        elif last_seq is not None and seq != last_seq + 1:
            problems.append(f"entry[{i}] ({who}): seq {seq} not contiguous after {last_seq} (insert-delete)")
            break
        else:
            last_seq = seq
        prev_digest = link_digest(link_of(e), schema)
    return (not problems), problems
