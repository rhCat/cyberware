#!/usr/bin/env python3
"""generate_swarm.py — emit the cyberware Foundation Plan v1.1 as a swarm of verifiable task-ledgers.

The plan argued work should decompose into contract-bound, verifiable, dedicated units routed through a
governed channel. The plan is work; therefore the plan becomes that. Each task below is one node of the
construction swarm: it carries an id, the phase + ladder rung it serves, an explicit dependency set
(the DAG), a deliverable contract (what artifact must exist), the validation criteria it satisfies
(by id, traceable to the plan), and an acceptance block a verifier (human or agent) checks against.

Single source of truth in, deterministic JSON files out — no hand-authoring of ~80 files.
Schema is CWP-task-v1.1 (a superset of the cyberware task-ledger: it adds the planning fields the
construction swarm needs — deps, criteria, acceptance, rung — without breaking the runtime shape).
"""
from __future__ import annotations
import collections
import hashlib
import json
import os
import re

_CONCERN = [
    (r"spec|\.md|semantics|envelope|schema", "spec"),
    (r"canonical|sign|digest|vector|verifier|keystore", "core"),
    (r"ledger|checkpoint|chain|crypto-shred", "ledger"),
    (r"exod|grant|sandbox|vault|capability|meter", "exod"),
    (r"sign|cosign|rekor|revocation|approval|attestation|tsa|release", "trust"),
    (r"alchemy|conserve|classify|concord|citrinitas", "alchemy"),
    (r"tlc|tla|apalache|tlaps|workflow|model|invariant", "modelcheck"),
    (r"escrow|settle|reward|quote|fmv|dispute|dust|money|payout|intelligence|llm", "settle"),
    (r"store|tenancy|sse|telemetry|ha|failover", "service"),
    (r"skill\b|author", "skill"),
    (r"bench|chaos|mutat|drill|red.?team", "validate"),
    (r"docker|sbom|deps|supply|infra", "infra"),
]
def _group(phase, title, kind):
    low = (title + " " + kind).lower()
    for pat, name in _CONCERN:
        if re.search(pat, low):
            return f"{phase.lower()}-{name}"
    return phase.lower()

OUT = os.path.join(os.path.dirname(__file__), "tasks")
SCHEMA = "cwp-task-v1.1"

# ─────────────────────────────────────────────────────────────────────────────
# The swarm. Each tuple:
#   id, title, phase, rung, kind, deps[], skill, deliverable, criteria[], acceptance{}, effort, parallel_group
# kind ∈ spec | build | skill | gate | drill | doc | infra
# rung = the SV level this task helps unlock (or "-" for cross-cutting)
# parallel_group = tasks sharing a group may run concurrently once deps clear (swarm scheduler hint)
# ─────────────────────────────────────────────────────────────────────────────

SPINE_IDS = ["P0-T02","P0-T03","P0-T04","P0-T17","P0-T18",
             "P1-T01","P1-T02","P1-T04","P1-T05","P1-T09",
             "P2-T01","P2-T02","P2-T03","P2-T05","P2-T08",
             "P3-T01","P3-T03","P3-T05","P3-T15",
             "P6-T01","P6-T02","P6-T03","P6-T05","P6-T06"]

TASKS = [
    # ===================== PHASE 0 — protocol extraction → SV-1 =====================
    ("P0-T01", "Write cwp-core.md (message envelopes, error model)", "P0", "SV-1", "spec",
     [], "cws-conform",
     "spec/cwp-core.md — versioned envelope, all message types, field tables, error model",
     ["F11"],
     {"exists": "spec/cwp-core.md", "must": ["envelope schema for claim/verdict/plan/grant/approval/step_*/receipt/revocation",
        "every message carries {cwp, type, body, sig}", "error model enumerated"]},
     "M", "p0-spec"),

    ("P0-T02", "Implement RFC 8785 JCS canonicalizer (vendored)", "P0", "SV-1", "build",
     [], "cws-conform",
     "infra/cwp/canonical.py — canonical_bytes(), validated against external JCS corpora",
     ["F1", "P0-V02"],
     {"exists": "infra/cwp/canonical.py", "passes": "published JCS number-serialization corpus + RFC 8785 appendix",
      "threshold": "100% corpus"},
     "M", "p0-core"),

    ("P0-T03", "Implement sign.py (Ed25519 + DSSE PAE)", "P0", "SV-1", "build",
     ["P0-T02"], "cws-conform",
     "infra/cwp/sign.py — sign()/verify(), DSSE v1.0 envelopes, key-id indirection",
     ["F1", "P0-V05"],
     {"exists": "infra/cwp/sign.py", "interop": "cosign-generated DSSE verifies in cwp.verify and vice versa"},
     "M", "p0-core"),

    ("P0-T04", "One-commit digest cutover (all hashes through canonical_bytes)", "P0", "SV-1", "build",
     ["P0-T02"], "cws-conform",
     "every plan_sha/skill_sha/chip_sha/ledger hash routed through cwp.canonical_bytes",
     ["F1", "P0-V03"],
     {"lint": "grep json.dumps ∧ sha co-occurrence outside infra/cwp = 0"},
     "S", "p0-core"),

    ("P0-T05", "Author JSON Schemas (2020-12) for every CWP message", "P0", "SV-1", "spec",
     ["P0-T01"], "cws-conform",
     "spec/schemas/*.json — one schema per message type",
     ["F11", "P0-V04"],
     {"exists": "spec/schemas/", "validates": "every CWP instance in tests against its schema", "threshold": "100%"},
     "S", "p0-spec"),

    ("P0-T06", "Write lpp-semantics.md (eval order, invariants, failure, operators)", "P0", "SV-1", "spec",
     [], "cws-conform",
     "spec/lpp-semantics.md — state/gate/action evaluation order, invariant meaning, failure semantics, reserved seq/par/choice/saga",
     ["F8", "F11"],
     {"exists": "spec/lpp-semantics.md", "must": ["composition operators defined", "failure semantics defined",
        "refinement: checked abstraction vs enforced data plane"]},
     "M", "p0-spec"),

    ("P0-T07", "Generate the golden vector corpus (≥250)", "P0", "SV-1", "build",
     ["P0-T02", "P0-T03"], "cws-conform",
     "spec/vectors/ — ≥250 vectors: canonicalization edges, digests, DSSE sign/verify, chip fixtures",
     ["P0-V01"],
     {"exists": "spec/vectors/", "count": ">=250", "covers": ["unicode", "number-format", "nesting", "digests", "signatures", "chip"]},
     "M", "p0-core"),

    ("P0-T08", "Build the independent Go verifier (external anchor)", "P0", "SV-1", "build",
     ["P0-T07"], "cws-conform",
     "verifiers/go/ — replays the vector corpus, diffs verdicts (meta-rule M3 anchor)",
     ["P0-V01", "F11"],
     {"reproduces": "100% of vectors byte-for-byte (canonical bytes, digests, sig verdicts)", "ci_gated": True},
     "M", "p0-anchor"),

    ("P0-T09", "Write spec/keys.md (M2: hierarchy, rotation, compromise, bootstrap)", "P0", "SV-1", "spec",
     [], "cws-conform",
     "spec/keys.md — offline root → service keys → store HMAC; rotation overlap; compromise runbook; key bootstrap (pinning; TOFU rejected for priced/destructive)",
     ["M2"],
     {"exists": "spec/keys.md", "must": ["key hierarchy", "rotation with overlap + cross-sign", "compromise runbook", "bootstrap/pinning story"]},
     "M", "p0-spec"),

    ("P0-T10", "Write spec/privacy.md (M5: crypto-shredding, retention, metadata)", "P0", "SV-1", "spec",
     [], "cws-conform",
     "spec/privacy.md — data classes, subject-DEK crypto-shredding, hash-only payload refs, retention tiers, /rep gating, FMV k-floor as privacy",
     ["M5"],
     {"exists": "spec/privacy.md", "must": ["crypto-shredding design", "metadata-is-data treatment", "erasure-with-intact-chain rule"]},
     "M", "p0-spec"),

    ("P0-T11", "Write spec/time.md (M8: NTS, monotonic, TSA)", "P0", "SV-1", "spec",
     [], "cws-conform",
     "spec/time.md — NTS-NTP ops requirement, monotonic clocks for caches/TTLs, TSA countersignature rules",
     ["M8"],
     {"exists": "spec/time.md", "must": ["NTS requirement", "monotonic TTL rule", "TSA threshold + dispute-boundary rule"]},
     "S", "p0-spec"),

    ("P0-T12", "Write spec/inflight.md (M9: the five decided sentences)", "P0", "SV-1", "spec",
     [], "cws-conform",
     "spec/inflight.md — revocation-mid-run, cancel, metered-escrow funds cap, schema evolution, WS resume",
     ["M9"],
     {"exists": "spec/inflight.md", "count": "exactly 5 decided transitions", "each": "one normative sentence with the chosen behavior"},
     "S", "p0-spec"),

    ("P0-T13", "Reproducible engine build baseline (M1/T28)", "P0", "SV-1", "infra",
     [], "cws-conform",
     "Dockerfile pinned FROM@sha256 + SOURCE_DATE_EPOCH + pip --require-hashes; diffoscope CI job",
     ["M1", "P0-V11"],
     {"dual_builder": "CI and an independent builder produce byte-identical digests", "diffoscope": "empty"},
     "M", "p0-infra"),

    ("P0-T14", "deps.lock.json + SBOM + osv-scanner gate (R1/T23)", "P0", "-", "infra",
     [], "cws-conform",
     "deps.lock.json (every runtime dep hash-pinned) + CycloneDX SBOM + osv-scanner CI gate",
     ["P0-V09"],
     {"unpinned_imports": 0, "sbom_emitted": True, "osv": "clean or waivered on record"},
     "S", "p0-infra"),

    ("P0-T15", "KeyStore adapter seam (file + PKCS#11 stub, R2)", "P0", "SV-1", "build",
     ["P0-T09"], "cws-conform",
     "infra/cwp/keystore.py — file backend + PKCS#11 stub, one contract suite (T29)",
     ["M2", "P0-V12"],
     {"both_backends_pass": "one contract suite", "seam_real": True},
     "S", "p0-core"),

    ("P0-T16", "Truth-in-labeling docs pass", "P0", "-", "doc",
     ["P0-T01"], "cws-conform",
     "README/SKILL.md/docs: every ENFORCED claim cites a criterion id; doc-lint enforces",
     ["P0-V08", "M10"],
     {"doc_lint": "no ENFORCED tag without a criterion-id reference"},
     "S", "p0-spec"),

    ("P0-T17", "Author cws-conform skill (vectors, crosslang perks)", "P0", "SV-1", "skill",
     ["P0-T07", "P0-T08"], "cws-conform",
     "skillChip/cws-conform/ — perks: vectors (replay+verdict json), crosslang (drive Go verifier, diff)",
     ["P0-V06"],
     {"governed_run": "conformance verdict produced through the executor", "json": {"failed": 0, "total": ">=250"}},
     "M", "p0-skill"),

    ("P0-T18", "Chip re-pin under JCS (the SV-1 self-referential act)", "P0", "SV-1", "gate",
     ["P0-T04", "P0-T17"], "cws-conform",
     "regenerate every skill index + chip manifest under canonical hashing; commit links old↔new chip_sha",
     ["P0-V07"],
     {"skill_index_check": "green", "transition_commit": "links old chip_sha → new chip_sha"},
     "S", "p0-gate"),

    # ===================== PHASE 1 — integrity hardening → SV-2 =====================
    ("P1-T01", "Ledger v2: append-only JSONL + prev-chain + genesis binding", "P1", "SV-2", "build",
     ["P0-T03"], "cws-ledgercheck",
     "infra/ledger/ — append-only JSONL, seq + full-sha256 prev, genesis binds {run_id, plan_sha}, full digests",
     ["F2", "F7"],
     {"chain_verifiable": True, "genesis_non_transplant": "replay under different {run_id,plan_sha} fails"},
     "L", "p1-ledger"),

    ("P1-T02", "Ledger durability: O_APPEND + fsync + flock + atomic snapshot", "P1", "SV-2", "build",
     ["P1-T01"], "cws-ledgercheck",
     "POSIX durability layer (T06): O_APPEND, fsync, fcntl.flock; govd snapshots via os.replace; torn-tail truncation recorded",
     ["F2", "P1-V01", "P1-V02"],
     {"concurrency": "16 writers x 5000 appends: zero lost/torn, single chain", "crash": "500 kill-9 → verifies, tail truncation recorded"},
     "L", "p1-ledger"),

    ("P1-T03", "Merkle checkpoints in Ledger v2 (M7)", "P1", "SV-2", "build",
     ["P1-T01"], "cws-ledgercheck",
     "checkpoint records: chain head + Merkle balance root every N entries/T minutes, writer-signed",
     ["M7", "P1-V11", "P1-V12"],
     {"cold_verify": "1M-entry chain from last checkpoint <=2s on reference env", "forged_checkpoint": "detected by next audit"},
     "M", "p1-ledger"),

    ("P1-T04", "cyberware ledger verify + Go chain-checker (anchor)", "P1", "SV-2", "build",
     ["P1-T01"], "cws-ledgercheck",
     "ledger verify CLI + ~150-line Go port that cold-verifies any chain (meta-rule M3)",
     ["F2", "P1-V03", "P1-V04"],
     {"single_bit_flip": "detected, names the record", "go_cold_verify": "100% of fixtures + CI ledgers"},
     "M", "p1-anchor"),

    ("P1-T05", "Per-step snippet verification at instant of execution", "P1", "SV-2", "build",
     ["P0-T02"], "cws-ledgercheck",
     "executor verifies each snippet sha256 against index.json immediately before that step (closes F3 + TOCTOU)",
     ["F3", "P1-V05"],
     {"post_bless_mutation": "refuses exactly the affected step with expected-vs-found digests"},
     "M", "p1-exec"),

    ("P1-T06", "Plan as sole source of step truth (delete --list execution)", "P1", "SV-2", "build",
     [], "cws-ledgercheck",
     "step enumeration from blessed plan / compile metadata; remove bash script --list execution (closes F4)",
     ["F4", "P1-V06"],
     {"no_artifact_exec_outside_grant": True, "list_absent_from_tree": True},
     "S", "p1-exec"),

    ("P1-T07", "Crypto-shredding fields in records (M5)", "P1", "SV-2", "build",
     ["P1-T01", "P0-T10"], "cws-ledgercheck",
     "subject-DEK ciphertext for personal fields; chain hashes ciphertext; erasure = DEK destruction",
     ["M5", "P1-V13"],
     {"erasure_drill": "destroy DEK → chain still verifies; subject fields unrecoverable; other queries unaffected"},
     "M", "p1-ledger"),

    ("P1-T08", "Transport tourniquet: bearer auth + TLS edge + rate limit (F5 partial)", "P1", "SV-2", "infra",
     [], "cws-ledgercheck",
     "Authorization: Bearer only (query tokens deprecated); principals.json (id→token-sha→quota); token-bucket; TLS 1.3 edge documented",
     ["F5", "P1-V07"],
     {"no_token": "401", "rate_limit": "burst then 429", "every_record_carries_principal": True},
     "M", "p1-infra"),

    ("P1-T09", "Author cws-ledgercheck skill (verify, torture perks)", "P1", "SV-2", "skill",
     ["P1-T02", "P1-T04"], "cws-ledgercheck",
     "skillChip/cws-ledgercheck/ — verify (chain+sig over a store), torture (N concurrent governed writers)",
     ["P1-V09"],
     {"governed": "torture + verify run through the channel; verify checks the ledger of its own verification run"},
     "M", "p1-skill"),

    ("P1-T10", "Author cws-mutate skill + wire R3 enforcement surface", "P1", "-", "skill",
     ["P1-T04", "P1-T05"], "cws-mutate",
     "skillChip/cws-mutate/ — one perk per R3 gate; mutate→CI-must-fail harness (V-MUT class)",
     ["M11", "P1-V14"],
     {"json": {"mutation_score": ">=0.90"}, "covers": ["chain_verifier", "per_step_snippet_check"]},
     "M", "p1-skill"),

    # ===================== PHASE 2 — exod boundary → SV-3 =====================
    ("P2-T01", "Signed grants (Ed25519-DSSE, skew, nonce, reserved quote_sha)", "P2", "SV-3", "build",
     ["P0-T03", "P0-T11"], "cws-redteam",
     "govd issues signed grant {run_id, plan_sha, snippet_shas, capabilities, credentials, nbf, exp, nonce}; ±60s skew; monotonic nonce cache",
     ["F6", "P2-V04"],
     {"replay_refused": True, "expired_refused": True, "skew_honored": "±60s boundaries", "verifiable_offline": True},
     "M", "p2-grant", ),

    ("P2-T02", "exod daemon: separate principal, UDS/mTLS, per-step verify", "P2", "SV-3", "build",
     ["P2-T01", "P1-T05"], "cws-redteam",
     "infra/exec/exod.py — different UNIX user/container; UDS+SO_PEERCRED local, mTLS+SPIFFE-SAN remote; verifies grant sig + per-step snippet digests; reports status under its own identity",
     ["F9", "M1"],
     {"forged_status_rejected": "a step_result not on exod's channel is refused + recorded", "self_reports_replaced": True},
     "L", "p2-exod"),

    ("P2-T03", "SandboxProfile driver: bwrap core profile (the spine sandbox)", "P2", "SV-3", "build",
     ["P2-T02"], "cws-redteam",
     "bubblewrap + seccomp default + cgroup-v2 + Landlock(where≥5.13); RO registry, RW only RECORD_STORE, egress-allowlist netns (T09)",
     ["F9", "P2-V01", "P2-V02"],
     {"corpus_refused": "≥12 behaviors refused", "kernel_enforced": "refusals hold with in-process scan disabled"},
     "L", "p2-sandbox"),

    ("P2-T04", "SandboxProfile community tier: gVisor/Firecracker (seam proof, R2)", "P2", "-", "build",
     ["P2-T03"], "cws-redteam",
     "gVisor runsc OR Firecracker+jailer behind the same driver (T10) — full corpus green under both (or one + documented stub)",
     ["P2-V10", "R2"],
     {"matrix": "corpus green under both backends", "no_secrets_tier": "community manifest cannot request secrets (schema + runtime)"},
     "L", "p2-sandbox"),

    ("P2-T05", "Vault adapter: sops/age + env-stub (T12, R2)", "P2", "SV-3", "build",
     ["P2-T02"], "cws-redteam",
     "Vault.get(credential_id) over sops/age file + env-stub second impl; secrets injected step-side only; *_FILE deprecated",
     ["F6", "P2-V03"],
     {"agent_has_zero_secret_bytes": "scan environ+fds+coredump during credentialed run", "both_backends": "one contract suite"},
     "M", "p2-exod"),

    ("P2-T06", "Capability manifest enforcement (binds, netns, cgroup, seccomp)", "P2", "SV-3", "build",
     ["P2-T03"], "cws-redteam",
     "contracts.json capabilities materialized by exod per step; destructive:true ⇒ requests write/exec beyond record store",
     ["F9", "P2-V08"],
     {"materialized_exactly": "manifest binds == sandbox binds", "mismatch_refuses": True},
     "M", "p2-sandbox"),

    ("P2-T07", "exod-attested meters + proto-receipts (Phase-6 meter dry-run)", "P2", "SV-3", "build",
     ["P2-T02"], "cws-bench",
     "exod signs proto-receipts carrying attested meters (wall, bytes, provider-usage where applicable)",
     ["P2-V07", "P2-V09"],
     {"meters_attested": "originate from exod, never the agent", "first_attested_meter_artifact": True},
     "M", "p2-exod"),

    ("P2-T08", "Author cws-redteam skill (≥12 attack perks, expect refusal)", "P2", "SV-3", "skill",
     ["P2-T03"], "cws-redteam",
     "skillChip/cws-redteam/ — one perk per attack class; each contract expects nonzero exit + refusal class (meta-rule M4)",
     ["P2-V01", "P2-V09"],
     {"corpus": ">=12 behaviors", "each_expect": {"exit": "nonzero"}, "governed": "run under exod's own observation"},
     "M", "p2-skill"),

    ("P2-T09", "Author cws-bench skill (sandbox, channel overhead perks)", "P2", "SV-3", "skill",
     ["P2-T07"], "cws-bench",
     "skillChip/cws-bench/ — measures overheads through the channel, emits attested-meter receipts",
     ["P2-V07"],
     {"budgets": {"bwrap_p95_per_step_ms": "<=100", "microvm_cold_ms": "<=1500", "microvm_warm_ms": "<=250"}},
     "M", "p2-skill"),

    ("P2-T10", "Author cws-chaos skill + partition/crash drills (V-CHAOS)", "P2", "-", "skill",
     ["P2-T02"], "cws-chaos",
     "skillChip/cws-chaos/ — partition govd↔exod, crash-exod; recovery invariants per spec/inflight.md",
     ["M11", "P2-V11", "P2-V12"],
     {"partition": "running step completes, next refuses closed, WS resume idempotent, zero dup records",
      "crash_exod": "orphan sandbox reaped (cgroup kill), step records error, run resumable"},
     "M", "p2-skill"),

    ("P2-T11", "Legacy in-process path behind [UNGOVERNED-BOUNDARY] banner", "P2", "-", "build",
     ["P2-T02"], "cws-redteam",
     "executor becomes thin client when EXOD_URL set; legacy path prints the banner every run until removal",
     ["F9"],
     {"banner_every_run": True, "honest_distinction_visible_in_logs": True},
     "S", "p2-exod"),

    # ===================== PHASE 3 — marketplace trust → SV-4 =====================
    ("P3-T01", "Publisher signing: cosign over skill_sha + chip manifest (T13)", "P3", "SV-4", "build",
     ["P0-T03"], "cws-release",
     "cosign sign-blob (Fulcio keyless or BYO) over skill_sha; chip manifest signs the set; verify in chipfetch+govd+exod; Sigstore TUF root pinned in deps.lock",
     ["F10", "P3-V01"],
     {"tri_layer_refusal": "unsigned/invalid refuses at chipfetch, govd boot, exod run", "tuf_root_pinned": True},
     "M", "p3-sign"),

    ("P3-T02", "Transparency: Rekor inclusion proofs per release (T14)", "P3", "SV-4", "build",
     ["P3-T01"], "cws-release",
     "every chip release appended to Rekor; inclusion proof stored with the release; offline-verifiable",
     ["F10", "P3-V02"],
     {"offline_proof": "verifies against pinned root, no live log needed"},
     "M", "p3-sign"),

    ("P3-T03", "Revocation feed: Ed25519 {seq, expires, revoked[]} (T15)", "P3", "SV-4", "build",
     ["P0-T03"], "cws-release",
     "signed feed: monotonic seq (anti-rollback), expires (freshness); govd checks at /govern, exod re-checks at run; max-age 15m",
     ["F10", "P3-V03", "P3-V04", "P3-V05"],
     {"revoke_latency": "govd refuses by T+interval+5s; exod on next run", "stale_refused": "feed>max-age → feed_stale", "rollback_refused": True},
     "M", "p3-revoke"),

    ("P3-T04", "WebAuthn approval (challenge=sha256(JCS(doc)); remove --approve) (T16)", "P3", "SV-4", "build",
     ["P0-T02", "P0-T03"], "cws-release",
     "WebAuthn ceremony; assertion+COSE key stored; govd verifies against per-perk/per-env approver registry; --approve flag deleted",
     ["F6", "P3-V06", "P3-V07"],
     {"all_destructive_grants_carry_verified_approval": True, "mutation": "deleting the check fails CI",
      "offline_verify": "from stored assertion+COSE key, no live authenticator"},
     "M", "p3-approve"),

    ("P3-T05", "Engine attestation: cws-release/engine + mutual handshake (M1/T28)", "P3", "SV-4", "build",
     ["P0-T13", "P3-T01", "P3-T02"], "cws-release",
     "engine release signed + Rekor-logged with SLSA provenance; /health attests engine digest; govd↔exod exchange release attestations, refuse engine_unattested on mismatch",
     ["M1", "P3-V11", "P3-V12"],
     {"tamper_handshake_fails": "1-byte-tampered engine on either side → engine_unattested", "health_matches_signed_release": True},
     "L", "p3-engine"),

    ("P3-T06", "Key-rotation drill as a governed workflow (M2/T29)", "P3", "SV-4", "drill",
     ["P0-T15", "P2-T01"], "cws-release",
     "rotate govd-grant with overlap window; cross-signed key_rotation record; in-flight grants honored to exp; old key feed-revoked after window",
     ["M2", "P3-V13"],
     {"overlap_honored": True, "cross_signed_record_present": True, "post_revocation_old_key_grant_refuses": True},
     "M", "p3-engine"),

    ("P3-T07", "Time anchors: TSA countersignatures on high-value receipts (M8/T27)", "P3", "SV-4", "build",
     ["P0-T11"], "cws-release",
     "Timestamper adapter (RFC 3161, two backends per R2); above-threshold receipts + dispute-window boundaries countersigned",
     ["M8", "P3-V14"],
     {"tsa_verifies_offline": "against TSA chain for every above-threshold receipt", "absence_blocks_settlement_eligibility": True},
     "M", "p3-sign"),

    ("P3-T08", "Author alchemy skill (extract, conserve, classify, concord) — the ancestor (T24/T25)", "P3", "SV-4", "skill",
     [], "alchemy",
     "skillChip/alchemy/ — wraps pinned alembic + putrefactio in file-mode (no warehouse dep on the chip path); perks extract/conserve/classify/concord",
     ["F9", "M11", "P3-V15", "P3-V16"],
     {"extract": "L++ emitted per snippet core", "conserve": {"unexplained_defects": 0}, "classify": {"unnamed": 0},
      "concord": "extracted CFG structurally contained in declared blueprint; diff stored", "pinned": "alembic+putrefactio+laws commits in deps.lock"},
     "XL", "p3-alchemy"),

    ("P3-T09", "Citrinitas publish gate wired into cws-release (verified tier)", "P3", "SV-4", "gate",
     ["P3-T08", "P3-T01"], "cws-release",
     "verified-tier admission requires alchemy extract+conserve+classify+concord; citrinitas-clean badge in catalog; community tier may carry unnamed/waivers but never skips concord",
     ["F9", "P3-V15", "P3-V16"],
     {"seeded_triple_blocks": "a seeded conservation defect, an unnamed shape, and a blueprint/CFG mismatch each block verified publish with the named reason",
      "chip_wide_concord": "100% of core+verified skills pass alchemy/concord"},
     "M", "p3-alchemy"),

    ("P3-T10", "Publish-time manifest lint (undeclared binaries/egress/cap mismatch)", "P3", "SV-4", "build",
     ["P3-T01"], "cws-release",
     "CI lints manifests against snippet contents; blocks on disagreement",
     ["F12", "P3-V08"],
     {"seeded_defects_caught": "100% of (undeclared binary, undeclared egress, capability mismatch)"},
     "M", "p3-sign"),

    ("P3-T11", "Tier wiring to P2 sandbox profiles", "P3", "-", "build",
     ["P2-T03", "P2-T04", "P3-T01"], "cws-release",
     "core/verified→bwrap, community→microVM; tier recorded in catalog and enforced at grant",
     ["F12"],
     {"tier_enforced_at_grant": True, "community_no_secrets_schema_and_runtime": True},
     "M", "p3-sign"),

    ("P3-T12", "Feed availability tiers + grace policy (M3)", "P3", "SV-4", "build",
     ["P3-T03"], "cws-release",
     "read-only verified may run stale-but-valid feed to grace-2 (24h); destructive/priced fail closed at max-age; signed feed mirrors documented",
     ["M3", "P3-V17"],
     {"outage_drill": "read-only proceeds to grace-2; destructive refuses; recovery re-converges with no manual ledger surgery"},
     "M", "p3-revoke"),

    ("P3-T13", "Revocation-in-flight implementation + drill (M9)", "P3", "SV-4", "build",
     ["P3-T03", "P2-T02"], "cws-release",
     "boundary-halt by default; severity:critical kills the sandbox immediately (per spec/inflight.md sentence 1)",
     ["M9"],
     {"boundary_halt": "next step_request refuses revoked", "critical_kills_immediately": True},
     "M", "p3-revoke"),

    ("P3-T14", "Receipts finalized (dual Ed25519-DSSE + in-toto export)", "P3", "SV-4", "build",
     ["P2-T07", "P3-T04"], "cws-release",
     "dual-signed receipt: exod(execution+meters) + govd(governance); in-toto/DSSE attestation export",
     ["F6", "P3-V10"],
     {"dual_signed": True, "in_toto_consumable": "cosign verify-attestation-class check passes"},
     "M", "p3-sign"),

    ("P3-T15", "Author cws-release skill (index, sign, log, manifest, engine perks)", "P3", "SV-4", "skill",
     ["P3-T01", "P3-T02", "P3-T05"], "cws-release",
     "skillChip/cws-release/ — the registry (and engine) publishes itself through the channel",
     ["P3-V09", "P3-V12"],
     {"governed_release": "chip + engine release are dual-signed receipts via the channel", "rekor_proof_stored": True},
     "M", "p3-skill"),

    ("P3-T16", "SECURITY.md doorbell (M12 residue)", "P3", "-", "doc",
     [], "cws-release",
     "SECURITY.md — contact, PGP/age key, acknowledgment SLA. Nothing more (willingness has an address)",
     ["M12"],
     {"exists": "SECURITY.md", "must": ["contact", "key", "ack SLA"]},
     "S", "p3-skill"),

    # ===================== PHASE 4 — workflow algebra + 3 cert classes → SV-5 =====================
    ("P4-T01", "Week-one: invariants→TLC (aux flags + INVARIANT clauses)", "P4", "SV-5", "build",
     ["P0-T06"], "cws-modelcheck",
     "emit_tla adds aux booleans (oversight_cleared, governed_run, contract_bound) set by action transitions; emit every safety_invariant as INVARIANT in the .cfg",
     ["F8", "P4-V01"],
     {"seeded_invariant_violations_fail_tlc": "blueprint mutants flipping each aux flag", "threshold": "100% caught"},
     "S", "p4-tlc"),

    ("P4-T02", "Failure as first-class transitions (on_fail: to|retry|compensate)", "P4", "SV-5", "build",
     ["P0-T06"], "cws-modelcheck",
     "on_fail transitions enter the TLA model; failure topology becomes checkable",
     ["F8", "P4-V06"],
     {"failure_edges_in_model": True, "saga_compensation": "provably runs on mid-branch failure in model AND execution"},
     "M", "p4-tlc"),

    ("P4-T03", "Workflow algebra: seq/par/choice/saga → product automaton", "P4", "SV-5", "build",
     ["P4-T02"], "cws-modelcheck",
     "workflow.json composes nodes; composer builds bounded-counter product automaton; workflow_sha over child plan_shas",
     ["F8", "P4-V05"],
     {"budgets": {"states": "<=5e6", "tlc_wall_s": "<=120"}, "bounded_counters": "retry budgets keep state finite"},
     "L", "p4-workflow"),

    ("P4-T04", "Apalache (SYMBOLIC) second checker + dual-checker agreement (T17)", "P4", "SV-5", "build",
     ["P4-T01"], "cws-modelcheck",
     "Apalache with Snowcat type annotations; TLC+Apalache must agree on every shipped blueprint/workflow; disagreements block + triage",
     ["P4-V02", "P4-V03"],
     {"corpus": "6/6 TLC, ≥5/6 Apalache", "agreement": "diffs block and are triaged on record"},
     "M", "p4-workflow"),

    ("P4-T05", "TLAPS (AXIOMATIC) class + P4-W1 Mode-3 THEOREM fix (T26)", "P4", "SV-5", "build",
     ["P4-T01"], "cws-modelcheck",
     "wire pinned tlapm; fix the single Mode-3 fix point in hyper_tla::generate_tla THEOREM emission so invariants earn AXIOMATIC stamps; honest Unproved otherwise",
     ["F8", "P4-V10", "P4-V11"],
     {"axiomatic_or_honest_unproved": "pipeline+settlement safety invariants carry AXIOMATIC or classified Unproved", "cross_arch_reproduces": True},
     "L", "p4-workflow"),

    ("P4-T06", "settlement.blueprint.json + model-check the money (M4)", "P4", "SV-5", "build",
     ["P4-T02", "P4-T04"], "cws-modelcheck",
     "encode the full settlement lifecycle (incl. CANCELLED + escrow-expiry); safety: escrow empties, no settle without dual-sig, no double-settle; liveness: ◇terminal under fairness with expiry timer",
     ["M4", "P4-V08", "P4-V09"],
     {"empirical_plus_symbolic_pass": True, "money_mutants_fail": "remove expiry timer / settle-before-validate / double-settle each caught"},
     "M", "p4-workflow"),

    ("P4-T07", "Emitter mutation testing (V-MUT on emit_tla)", "P4", "-", "gate",
     ["P4-T01", "P1-T10"], "cws-mutate",
     "mutating emit_tla is caught by the vector/corpus suite",
     ["P4-V04"],
     {"json": {"emitter_mutation_score": ">=0.90"}},
     "S", "p4-tlc"),

    ("P4-T08", "Author cws-modelcheck skill (check, corpus perks)", "P4", "SV-5", "skill",
     ["P4-T03", "P4-T04", "P4-T05"], "cws-modelcheck",
     "skillChip/cws-modelcheck/ — check (TLC+Apalache+TLAPS, emit cert json), corpus (assert known-bad all caught)",
     ["P4-V02"],
     {"tlc_verdict": "no_error", "corpus": "caught 6/6", "certs": ["EMPIRICAL", "SYMBOLIC", "AXIOMATIC"]},
     "M", "p4-skill"),

    ("P4-T09", "Encode plan.workflow.json — the plan verifies the plan (SV-5 act)", "P4", "SV-5", "gate",
     ["P4-T03", "P4-T08"], "cws-modelcheck",
     "the remainder of this plan (P5/P6 milestones + deps + failure handling) as a workflow; verify deadlock-free",
     ["P4-V07"],
     {"governed_run": "cws-modelcheck verdict", "plan_as_workflow": "deadlock-free"},
     "M", "p4-gate"),

    # ===================== PHASE 5 — service-grade govd (parallel) =====================
    ("P5-T01", "Store interface: sqlite-WAL → Postgres adapter (R2) + JSONL reconciler", "P5", "-", "build",
     ["P1-T01"], "cws-bench",
     "Store behind an interface; sqlite-WAL then psycopg/Postgres-15; chained JSONL stays artifact of record + continuous reconciler",
     ["F5", "P5-V02", "P5-V05"],
     {"both_adapters_pass": "identical contract suite", "reconciler": "zero divergence across soak; injected divergence alarms within one cycle"},
     "L", "p5-store"),

    ("P5-T02", "SSE push + pagination (replace 1.5s polling)", "P5", "-", "build",
     [], "cws-bench",
     "dashboard moves to SSE push with pagination",
     ["P5-V01"],
     {"latency_budget": "p95 /govern <=150ms at 50rps", "soak": "RSS slope <=1MB/h after warmup"},
     "M", "p5-store"),

    ("P5-T03", "Tenancy: org→principals→policy→quotas + per-org scopes (F5)", "P5", "-", "build",
     ["P1-T08"], "cws-bench",
     "org→principals→policy→quotas; per-org record roots + revocation scopes; SPIFFE identities throughout",
     ["F5", "P5-V03"],
     {"org_isolation": "cross-org reads/claims refused across the endpoint matrix"},
     "L", "p5-tenancy"),

    ("P5-T04", "HA design: active-passive govd + advisory-lock lease (M3)", "P5", "-", "infra",
     ["P5-T01"], "cws-chaos",
     "active-passive over shared Postgres; single-writer via Postgres advisory-lock lease (no split-brain); WS resume per spec/inflight; maintenance mode pre-issues short-TTL grants; standby serves signed feed mirrors",
     ["M3", "P5-V07", "P5-V08", "P5-V09"],
     {"failover_drill": "kill active mid-stream; standby acquires lease, WS resume, zero dup grants, zero lost step_results",
      "no_orphaned_run": "interrupted runs reach terminal/resumable within lease TTL+30s", "split_brain": "second writer cannot append while lease held; attempt recorded"},
     "L", "p5-tenancy"),

    ("P5-T05", "OpenTelemetry traceparent across planes + in-toto provenance (T19)", "P5", "-", "build",
     ["P2-T02"], "cws-bench",
     "W3C traceparent claim→grant→exod step; provenance exports as in-toto cyberware/run@v1 attestations",
     ["P5-V04"],
     {"full_cross_plane_trace": "100% of sampled runs retrievable by run_id"},
     "M", "p5-store"),

    # ===================== PHASE 6 — projection: settlement → SV-6 =====================
    ("P6-T01", "Money type (stdlib decimal scale-4 HALF_EVEN, float-ban lint) (T20)", "P6", "SV-6", "build",
     [], "cws-settle-sim",
     "infra/settle/money.py — decimal scale 4, ROUND_HALF_EVEN, explicit context; AST lint bans binary floats on money paths",
     ["P6-V03"],
     {"float_ban": "no binary float touches money paths (AST lint, 0 occurrences)"},
     "S", "p6-core"),

    ("P6-T02", "Reward ledger = Ledger-v2 + double-entry posting sets", "P6", "SV-6", "build",
     ["P1-T01", "P1-T03", "P6-T01"], "cws-settle-sim",
     "reward ledger as a Ledger-v2 instance; every record a balanced posting set; checkpoints commit balance roots",
     ["M7", "P6-V01"],
     {"zero_sum": "per-record AND global per-currency exact", "10k_storm": "escrow/hold accounts zero at every terminal state"},
     "L", "p6-core"),

    ("P6-T03", "Escrow lifecycle + expiry auto-refund (M4 liveness, M9 sentence 3)", "P6", "SV-6", "build",
     ["P6-T02", "P4-T06"], "cws-settle-sim",
     "escrow accounts funded by initiators; every escrow carries expires_at; expiry without settlement auto-refunds (the V-LIVE guarantee, model-checked in P4)",
     ["M3", "M4", "P6-V12"],
     {"expiry_refund": "stalled escrow auto-refunds at expires_at ± one sweep; zero escrow older than bound at any audit"},
     "M", "p6-core"),

    ("P6-T04", "Quote (Ed25519-DSSE, bound to plan_sha + split policy)", "P6", "SV-6", "build",
     ["P0-T03", "P6-T02"], "cws-settle-sim",
     "govd computes quote from pricing block + current FMV + signed split policy; signs it; grant requires funded quote_sha for priced perks",
     ["P6-V01"],
     {"grant_requires_funded_quote": "priced perks", "breakdown_balances": "quote split sums to amount"},
     "M", "p6-core"),

    ("P6-T05", "Settlement engine = f(dual-signed receipt, signed split policy)", "P6", "SV-6", "build",
     ["P6-T02", "P6-T04", "P3-T14"], "cws-settle-sim",
     "consume receipt: verify both sigs + quote binding + validation:pass; write one atomic posting set; zero escrow; dispute-window holdback",
     ["P6-V02"],
     {"impossible_without_both_sigs_and_validation_pass": "mutant receipts (sig stripped / verdict flipped) rejected"},
     "L", "p6-core"),

    ("P6-T06", "reward verify (chain + per-record zero + global zero + receipt cross-check)", "P6", "SV-6", "build",
     ["P6-T02"], "cws-settle-sim",
     "cyberware reward verify: chain integrity + per-record sum-zero + global per-currency sum-zero + every settlement references a verifying dual-signed pass receipt",
     ["P6-V01"],
     {"cross_checks_receipt_store": "money trail and work trail cannot drift silently"},
     "M", "p6-core"),

    ("P6-T07", "Blueprint↔code concordance for settlement (M4 + ancestor trick)", "P6", "SV-6", "gate",
     ["P6-T05", "P4-T06", "P3-T08"], "cws-modelcheck",
     "implemented lifecycle bisimilar to settlement.blueprint.json; every code transition maps to a blueprint transition; seeded extra transition fails concordance",
     ["M4", "P6-V13"],
     {"bisimilar": True, "seeded_extra_transition_fails": True},
     "M", "p6-core"),

    ("P6-T08", "Attested meters become settleable + provider-receipt capture (6b)", "P6", "SV-6", "build",
     ["P2-T07", "P6-T05"], "cws-settle-sim",
     "exod-attested meters settle; metered pricing floor/cap; provider-receipt capture for llm/*; pass-through reimbursement lane",
     ["P6-V04"],
     {"meter_matches_provider_receipt": "within tolerance on live calls; absent receipt → exod count or unsettleable"},
     "M", "p6-intel"),

    ("P6-T09", "llm/* intelligence perk class (schema-validation payment gate)", "P6", "SV-6", "skill",
     ["P6-T08"], "alchemy",
     "skillChip/llm/ — declared I/O, model class, output contract; schema-fail ⇒ publisher/agent earn zero, initiator refunded per validation_refund",
     ["P6-V05"],
     {"schema_fail_refund_split": "publisher/agent zero; initiator refunded per policy; pass-through + govd fee land per policy",
      "per_contract_intelligence": "the meter measures effort; the contract decides whether effort was work"},
     "L", "p6-intel"),

    ("P6-T10", "Market modes: bounty + reverse auction (6c)", "P6", "SV-6", "build",
     ["P6-T05"], "cws-settle-sim",
     "bounty (first/best-of-N validated wins) + reverse auction (lowest qualified clears)",
     ["P6-V07"],
     {"bounty_one_winner": "exactly one; losers' escrows untouched", "auction_clears_below_posted": "under competition"},
     "M", "p6-market"),

    ("P6-T11", "FMV indices: trimmed VWM + admission rules + signed publication (6c)", "P6", "SV-6", "build",
     ["P6-T05", "P3-T08"], "cws-settle-sim",
     "trimmed volume-weighted median per (skill,perk[,class]); admission n≥20, distinct pairs≥8; common-control exclusion via P3 identity graph; signed fmv_index docs; provisional below admission",
     ["P6-V06"],
     {"manipulation_bound": "20% adversarial volume moves index <2%", "sub_admission_marked_provisional": True},
     "L", "p6-market"),

    ("P6-T12", "Disputes: window + bonds + m-of-n via approval artifacts (6d)", "P6", "SV-6", "build",
     ["P6-T05", "P3-T04"], "cws-settle-sim",
     "dispute window + bonds; m-of-n resolution REUSING the P3 approval artifact over a resolution doc; clawback from holdback; reputation delta",
     ["P6-V08"],
     {"dispute_e2e": "bond posting, m-of-n resolution, clawback from holdback, reputation delta — all ledgered"},
     "L", "p6-market"),

    ("P6-T13", "Derived reputation scores (signed, third-party reproducible) (6d)", "P6", "SV-6", "build",
     ["P6-T05", "P6-T12"], "cws-settle-sim",
     "per-principal-class scores from the ledgers; signed; /rep gated to counterparties; public views aggregate-only",
     ["P6-V10", "P6-V19"],
     {"third_party_reproducible": "score + FMV point recomputable from public ledger data alone",
      "rep_privacy": "unauthenticated/non-counterparty get aggregates only"},
     "M", "p6-market"),

    ("P6-T14", "Stripe SettlementAdapter + internal-credits adapter (T21, R2 seam)", "P6", "SV-6", "build",
     ["P6-T05"], "cws-settle-sim",
     "Stripe Payment Intents (fund) + Connect Express (payout; KYC at PSP) + internal-credits adapter; idempotency keys on every event",
     ["P6-V09", "P6-V15"],
     {"reconciliation": "ledger↔Stripe sandbox exact to 0.0001 CWC across 1k payouts",
      "duplicate_delivery": "every event replayed 2-10x; final balances identical; idempotency violations 0 across 10k"},
     "L", "p6-market"),

    ("P6-T15", "Dust account + adapter-boundary rounding rule (M13 conceded half)", "P6", "SV-6", "build",
     ["P6-T01", "P6-T14"], "cws-settle-sim",
     "banker's rounding at CWC scale-4 ↔ integer cents; residue posts to dust:adapter:<id> inside the same balanced entry; monthly signed sweep to treasury",
     ["M13", "P6-V16"],
     {"dust_conservation": "100k FX-boundary settlements: global zero-sum holds INCLUDING dust accounts; monthly sweep is a balanced signed record"},
     "M", "p6-market"),

    ("P6-T16", "Throughput: single-writer-per-currency group commit + checkpoint resume (M7)", "P6", "SV-6", "build",
     ["P6-T02", "P6-T03"], "cws-bench",
     "single writer per currency with group-commit batching; checkpoint-resume verification",
     ["M7", "P6-V17"],
     {"tps": ">=200 settlements/s sustained 10min on reference env; p95 <=250ms; checkpoint-resume verify <=2s at 1M entries"},
     "M", "p6-core"),

    ("P6-T17", "Settle-engine crash atomicity (V-CHAOS)", "P6", "SV-6", "drill",
     ["P6-T05", "P2-T10"], "cws-chaos",
     "kill settle engine mid-posting-set; set is all-or-nothing (group write + single fsync); recovery replays exactly once; conservation holds",
     ["P6-V18"],
     {"all_or_nothing": True, "replay_exactly_once": True, "conservation_holds_through_crash": True},
     "M", "p6-core"),

    ("P6-T18", "Author cws-settle-sim skill (storm, manipulate, dispute perks)", "P6", "SV-6", "skill",
     ["P6-T05", "P6-T11", "P6-T12"], "cws-settle-sim",
     "skillChip/cws-settle-sim/ — storm (10k randomized settlements), manipulate (FMV adversary), dispute (lifecycle)",
     ["P6-V01", "P6-V06", "P6-V08"],
     {"zero_sum_exact": True, "index_drift": "<2% @ 20% adversarial", "dispute_lifecycle_complete": True},
     "L", "p6-skill"),

    ("P6-T19", "Repatriate the ancestor as priced perks (M11 closing move)", "P6", "SV-6", "build",
     ["P3-T08", "P6-T05"], "alchemy",
     "alchemy extract/conserve/classify/concord published as priced analysis perks; every verified-tier publish pays the lineage",
     ["M11", "P6-V20"],
     {"lineage_receipt": ">=1 real verified-tier publish pays alchemy/* royalties through the reward ledger"},
     "M", "p6-intel"),

    ("P6-T20", "Self-bounty: cyberware's security program through its own ledger (M12 roadmap)", "P6", "SV-6", "drill",
     ["P6-T05", "P3-T16"], "cws-settle-sim",
     "vulnerabilities = bounty tasks; disclosure = the validated deliverable; payment flows through the reward ledger (adversarial dogfooding)",
     ["M12"],
     {"first_external_program": "the economy's first outside users are paid to break it"},
     "M", "p6-market"),

    ("P6-T21", "SV-6 capstone: development enters its own economy", "P6", "SV-6", "gate",
     ["P6-T05", "P6-T11", "P6-T18", "P6-T19"], "cws-settle-sim",
     "≥10 real development milestones settle as internal-credit bounties; first FMV index prices cyberware's own remaining tasks; the plan's completion is a settled, dual-signed, TSA-anchored workflow receipt reconciled against the PSP sandbox — the birth certificate",
     ["P6-V11"],
     {"settled_milestones": ">=10", "plan_completion_receipt": "verifies offline end-to-end — THE LADDER CLOSES"},
     "L", "p6-gate"),
]


# ─────────────────────────────────────────────────────────────────────────────
# MILESTONES — the externally-legible checkpoints, derived from the swarm.
# Each is a named rung with: the GATE task(s) that close it, the outward DENOMINATED PROMISE
# (a claim the ladder blesses and a receipt redeems), the DEMO artifact a skeptic can verify,
# and whether it is on the SPINE (the load-bearing path) or compounding work.
# The cumulative task closure is computed at emit time (no hand-maintenance).
# ─────────────────────────────────────────────────────────────────────────────
MILESTONES = [
    # id, label, rung, gate_tasks[], spine?, promise(outward), demo(verifiable), redeemed_by
    ("M0", "The spine stands — governed execution end to end (internal)", "-",
     ["P6-T05"], True,
     "Internal only: a task can be claimed, blessed, executed under attestation, and its outcome recorded — the load-bearing wall is up.",
     "A single governed run: claim → grant → exod step → chained ledger record, no value, no market.",
     "the spine task set complete"),

    ("M1", "SV-1 — the protocol is real and portable", "SV-1",
     ["P0-T18"], True,
     "cyberware is a specification, not a codebase: every hash is canonical and reproduced byte-for-byte by an independent implementation.",
     "The Go verifier reproduces 250+ golden vectors; the chip re-pins its own identity under canonical hashing.",
     "cws-conform governed run + the chip re-pin transition record"),

    ("M2", "SV-2 — evidence becomes tamper-evident", "SV-2",
     ["P1-T09", "P1-T10"], True,
     "Every record of what happened is chained, signed, and independently re-verifiable — history cannot be rewritten.",
     "16 concurrent writers + 500 crash injections survive with a single verified chain; a one-byte flip is caught and named.",
     "cws-ledgercheck torture+verify receipts; the Go chain-checker cold-verify"),

    ("M3", "SV-3 — execution becomes a kernel-enforced boundary  ◀ MVP", "SV-3",
     ["P2-T08", "P2-T09"], True,
     "Agents execute only attested, sandboxed, hash-pinned pathways; the privilege boundary is enforced by the OS, not by software trust.",
     "A 12-attack corpus refuses every case WITH the software scan disabled — the kernel is the counterparty; meters are attested.",
     "cws-redteam expected-refusal receipts + cws-bench attested-meter receipts"),

    ("M4", "SV-4 — the registry and the engine publish and revoke themselves", "SV-4",
     ["P3-T09", "P3-T15"], True,
     "Skills and the engine are signed, publicly logged, and revocable network-wide in minutes; approval to destroy is cryptographically human; the code agrees with its declared blueprint.",
     "The registry publishes itself through a perk; a revocation drill measures kill-switch latency; alchemy/concord proves CFG-vs-blueprint on the whole chip.",
     "dual-signed release receipts + Rekor inclusion proofs + the revocation drill receipt"),

    ("M5", "SV-5 — workflows and the money's lifecycle are model-checked", "SV-5",
     ["P4-T09"], False,
     "Composed workflows — and the settlement lifecycle itself — are proven free of deadlock and conservation violation BEFORE they run, across three independent checkers.",
     "The remaining plan, encoded as a workflow, verifies deadlock-free; settlement.blueprint.json passes EMPIRICAL+SYMBOLIC with seeded money-mutants caught.",
     "cws-modelcheck certificates (EMPIRICAL / SYMBOLIC / AXIOMATIC)"),

    ("M6", "SV-6 — the work pays for the work  (the ladder closes)", "SV-6",
     ["P6-T21"], True,
     "Validated work settles; intelligence is priced per contract; value is never minted, only earned — and the system paid for its own completion.",
     "10+ development milestones settle as internal-credit bounties; the first FMV index prices cyberware's own tasks; the plan's completion is a settled, TSA-anchored receipt reconciled against the PSP sandbox.",
     "the birth-certificate receipt — verified offline end to end"),
]

# normalize: some tuples carry a trailing comma quirk; coerce to 11 fields
def norm(t):
    t = tuple(t)
    return t[:11]

def task_id_hash(tid, title):
    return hashlib.sha256(f"{tid}:{title}".encode()).hexdigest()[:12]

# the ladder rung at which the GOVERNED channel becomes the executor for construction tasks.
# Before SV-2, tasks run by hand/code (the channel doesn't exist yet). From SV-2, meta-rule M5:
# the task's own CI gate IS a governed run. Validator-authoring tasks are bootstrap-exempt:
# they are validated by the EXTERNAL ANCHOR (meta-rule M3), not by the validator they create.
RUNG_ORDER = {"-":-1,"SV-0":0,"SV-1":1,"SV-2":2,"SV-3":3,"SV-4":4,"SV-5":5,"SV-6":6}

def _executor(kind, rung):
    # how the task itself is performed (NOT what proves it)
    if kind in ("spec", "doc"):
        return "human-authoring"
    if kind in ("skill", "build", "infra"):
        # governed-channel execution becomes available at SV-2; before that, local code
        return "governed-channel" if RUNG_ORDER.get(rung, -1) >= 2 else "local-code"
    if kind in ("gate", "drill"):
        return "governed-channel" if RUNG_ORDER.get(rung, -1) >= 2 else "local-code"
    return "local-code"

def emit(t, authors, phase_validator):
    tid, title, phase, rung, kind, deps, vskill, deliverable, criteria, acceptance, *rest = norm(t)
    effort = rest[0] if rest else "M"
    pgroup = _group(phase, title, kind)
    # a task that AUTHORS its own validator cannot be validated by it — anchor-validated instead
    bootstrap = (kind == "skill" and tid in authors.get(vskill, []))
    return {
        "$schema": SCHEMA,
        "task_id": tid,
        "task_hash": task_id_hash(tid, title),
        "title": title,
        "phase": phase,
        "ladder_rung": rung,
        "kind": kind,
        "effort": effort,
        "parallel_group": pgroup,
        "depends_on": deps,
        # ── doing vs proving, kept distinct (the audit's core fix) ──
        "executor": "external-anchor" if bootstrap else _executor(kind, rung),
        "validated_by": vskill,              # the skill whose criteria gate this task's acceptance
        "bootstrap_exempt": bootstrap,       # M3: validated by the external anchor, not by self
        "validation_available_after": (None if bootstrap else phase_validator.get(phase)),
        # ── cyberware runtime shape (this task, once runnable, is a claim) ──
        "skill": vskill if kind != "skill" else None,   # what it would CLAIM to prove itself; skill-authoring tasks claim nothing yet
        "perk": None,
        "record_store": f"<abs dir for {tid} outputs + run-ledger>",
        "vars": {},
        # ── the planning contract: verifiable + dedicatable ──
        "deliverable": deliverable,
        "satisfies_criteria": criteria,
        "acceptance": acceptance,
        "status": "todo",
        "assignee": None,                    # dedicate by setting a principal id here
    }

def _milestones(records):
    by_id = {r["task_id"]: r for r in records}
    def closure(t, seen):
        for dep in by_id[t]["depends_on"]:
            if dep not in seen:
                seen.add(dep); closure(dep, seen)
        return seen
    spine = set(["P0-T02","P0-T03","P0-T04","P0-T17","P0-T18","P1-T01","P1-T02","P1-T04","P1-T05",
                 "P1-T09","P2-T01","P2-T02","P2-T03","P2-T05","P2-T08","P3-T01","P3-T03","P3-T05",
                 "P3-T15","P6-T01","P6-T02","P6-T03","P6-T05","P6-T06"])
    out, prev = [], set()
    for mid, label, rung, gates, on_spine, promise, demo, redeemed in MILESTONES:
        req = set()
        for g in gates:
            req |= closure(g, set()) | {g}
        new = sorted(req - prev)
        out.append({
            "id": mid, "label": label, "rung": rung, "on_spine": on_spine,
            "gate_tasks": gates,
            "promise_outward": promise,          # the denominated claim (Principle: denominated promises)
            "demo": demo,                        # what a skeptic verifies
            "redeemed_by": redeemed,             # the receipt/evidence that closes it
            "tasks_cumulative": len(req),
            "tasks_new": new,
            "tasks_new_count": len(new),
            "spine_tasks_new": sorted(t for t in new if t in spine),
        })
        prev = req
    return out


def _reverse_index(records):
    """criterion id -> [task ids that satisfy it] — so you can ask 'what proves P6-V11?'"""
    idx = {}
    for r in records:
        for c in r["satisfies_criteria"]:
            idx.setdefault(c, []).append(r["task_id"])
    return {k: sorted(v) for k, v in sorted(idx.items())}


def main():
    os.makedirs(OUT, exist_ok=True)
    # map each validation skill -> the task(s) that author it (for the bootstrap exemption)
    authors = {}
    for t in TASKS:
        tid, title, phase, rung, kind, deps, vskill, *_ = norm(t)
        if kind == "skill":
            authors.setdefault(vskill, []).append(tid)
    phase_validator = {}
    for t in sorted(TASKS, key=lambda x: x[0]):
        tid, title, phase, rung, kind, *_ = norm(t)
        if kind == "skill" and phase not in phase_validator:
            phase_validator[phase] = tid     # the first validator-authoring task in the phase
    # phases without a native validator-authoring task borrow one cross-phase (e.g. P5 reuses P2's
    # cws-bench / cws-chaos). Point such tasks at the earliest authoring task of the skill they use.
    records = [emit(t, authors, phase_validator) for t in TASKS]
    for r in records:
        if not r["bootstrap_exempt"] and r.get("validation_available_after") is None:
            auth = sorted(authors.get(r["validated_by"], []))
            r["validation_available_after"] = auth[0] if auth else None
            if auth: r["validator_cross_phase"] = True
    # per-task files
    for r in records:
        with open(os.path.join(OUT, f"{r['task_id']}.json"), "w") as f:
            json.dump(r, f, indent=2)
            f.write("\n")
    # the swarm manifest: the DAG + roll-ups
    ids = {r["task_id"] for r in records}
    for r in records:
        for d in r["depends_on"]:
            assert d in ids, f"{r['task_id']} depends on unknown task {d}"
    by_phase = {}
    for r in records:
        by_phase.setdefault(r["phase"], []).append(r["task_id"])
    manifest = {
        "$schema": "cwp-swarm-manifest-v1.1",
        "program": "cyberware Foundation Plan v1.1",
        "generated_from": "single-source generator (generate_swarm.py)",
        "task_count": len(records),
        "phases": {p: sorted(v) for p, v in sorted(by_phase.items())},
        "ladder": {
            "SV-1": [r["task_id"] for r in records if r["ladder_rung"] == "SV-1"],
            "SV-2": [r["task_id"] for r in records if r["ladder_rung"] == "SV-2"],
            "SV-3": [r["task_id"] for r in records if r["ladder_rung"] == "SV-3"],
            "SV-4": [r["task_id"] for r in records if r["ladder_rung"] == "SV-4"],
            "SV-5": [r["task_id"] for r in records if r["ladder_rung"] == "SV-5"],
            "SV-6": [r["task_id"] for r in records if r["ladder_rung"] == "SV-6"],
        },
        "spine": ["P0-T02","P0-T03","P0-T04","P0-T17","P0-T18",
                  "P1-T01","P1-T02","P1-T04","P1-T05","P1-T09",
                  "P2-T01","P2-T02","P2-T03","P2-T05","P2-T08",
                  "P3-T01","P3-T03","P3-T05","P3-T15",
                  "P6-T01","P6-T02","P6-T03","P6-T05","P6-T06"],
        "dag_edges": sum(len(r["depends_on"]) for r in records),
        "roots": sorted([r["task_id"] for r in records if not r["depends_on"]]),
        "validation_classes": ["V-AUTO","V-PROP","V-RED","V-BENCH","V-EXT","V-GOV","V-MUT","V-CHAOS","V-LIVE"],
        "criterion_to_tasks": _reverse_index(records),
        "milestones": _milestones(records),

        "validators": {sk: sorted(v) for sk, v in sorted(authors.items())},
        "executors": dict(collections.Counter(r["executor"] for r in records)),
        "bootstrap_exempt": sorted(r["task_id"] for r in records if r["bootstrap_exempt"]),
        "six_month_line": "MS-3 (SV-4) is the ~26-week mark; MS-2 (SV-3) at week 16 is the irreducible MVP if time compresses.",
        "ordering_rule": "Author each phase's validation skill EARLY in its phase so sibling tasks "
                         "can be validated as they land. Validator-authoring tasks are anchor-validated (M3).",
    }
    with open(os.path.join(OUT, "_swarm_manifest.json"), "w") as f:
        json.dump(manifest, f, indent=2)
        f.write("\n")
    print(f"emitted {len(records)} task files + manifest to {OUT}")
    print(f"  phases: {', '.join(f'{p}:{len(v)}' for p,v in sorted(by_phase.items()))}")
    print(f"  roots (no deps): {len(manifest['roots'])}  ·  dag edges: {manifest['dag_edges']}  ·  spine: {len(manifest['spine'])}")

if __name__ == "__main__":
    main()
