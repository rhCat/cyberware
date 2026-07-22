# PG provenance ledger — two-tier value-bearing record: design + playbook

> Status: **PLANNED** (M0–M3, nothing built). Companion task map: [pg-provenance-ledger.playbook.json](pg-provenance-ledger.playbook.json).
> Decided in design review 2026-07-21/22. The value-free chain stays the artifact of record and the only thing
> on the wire/monitor; this adds a SECOND, value-bearing tier for inspection + reproducibility, encrypted at
> rest, federated to the mothership by *mothership-initiated* logical replication.

## Summary

Today the ledger is authorization-and-integrity only: it proves *who* ran *which blessed code* (plan_sha +
snippet_shas + wrapper + exod-signed step results, hash-chained), but the runtime arguments are gone forever —
`var_values` ride the per-run WS into exod's env and are never persisted, so two runs against different targets
produce near-identical records. For security audit and operational reproducibility we add **tier 2**: govd — the
only party that ever holds the (already declared-subset, secret-filtered) values — records them per step,
**envelope-encrypted at rest**, into the store-backend ladder (sqlite standalone → PG at fleet join), and
cross-binds a plaintext commitment `values_sha` into the tier-1 chain. Four independent layers, each revocable
alone: tailnet = reachability, PG roles/RLS = row access, recipient-set encryption = plaintext access,
chain = integrity.

## Invariants (load-bearing — every one gets a test)

1. **Chain supremacy.** `chain.jsonl` remains the sole artifact of record; every PG/sqlite table is a derived
   index, re-verifiable from the chain (`prev`/`link_digest` recompute). Tier-2 rows bind to it via `values_sha`.
2. **`values_sha` commits over canonical PLAINTEXT bytes** — never ciphertext (nonces/rotation would break
   verification). Verify-flow: decrypt → canonical-hash → match chain.
3. **The recordable set is structurally non-secret.** Tier 2 stores exactly the post-filter set from the WS
   step path (declared ∧ non-secret-named ∧ non-reserved ∧ not `CWS_SECRET_*`); `*_FILE` pointers record the
   *path only*. No new secret surface is created — property-tested, not assumed.
4. **The per-run session `token` never leaves the node.** It exists only in the node-local mutable
   `ledger.json`; the full-record mirror strips it before any replicated or exported form.
5. **govd is the sole DB writer; exod gets NO DSN.** exod stays unix-socket-only; its authority in a row is its
   verbatim Ed25519-signed result envelope, which the mothership re-verifies against the registered pubkey.
6. **Overlay ≠ authorization.** Tailnet join gives a path; admission = registration (`:8773`) + pg_hba
   hostssl/per-role cert + the mothership's subscribe act. Any of the three layers severs a node alone.
7. **Standalone holds its own.** A lone node records tier 2 in local sqlite with full fidelity; fleet join is
   a lossless, chain-verified backfill. PG is fleet oversight, not a dependency of the node.
8. **Off-node at rest = ciphertext only.** Replicas, backups (the NAS 3-2-1 chain), and dumps carry encrypted
   value blobs; a DB-role or backup breach yields no plaintext. Canary-tested in the backup drill.
9. **Config stays configurable** — DSNs, key paths, bind addresses from env/`dsn_file`/config, never
   entrypoint-hardcoded.

## Data model

Tier-2 tables (same schema in `SqliteWalBackend` and `PsycopgBackend`; PG adds a derived JSONB column —
**JSONB does not preserve bytes** (key order, dup keys, number formatting), so raw bytes are the hash target
and JSONB is a queryable projection, never the verification input):

```sql
-- per-step recorded values (ciphertext blob + plaintext metadata, searchable without decrypting)
CREATE TABLE run_values(
  node_id TEXT NOT NULL,            -- '' on a standalone node; stamped at publication
  run_id  TEXT NOT NULL, step TEXT NOT NULL, ts TEXT NOT NULL,
  values_sha TEXT NOT NULL,         -- sha256(canonical plaintext) == the chain-bound commitment
  ciphertext BYTEA NOT NULL,        -- AEAD(plaintext canonical bytes) under a fresh per-blob DEK
  dek_wraps  JSONB NOT NULL,        -- {recipient_keyid: wrapped_DEK} — HPKE(X25519+HKDF+AEAD) per recipient
  PRIMARY KEY(node_id, run_id, step));

-- full-record mirror (token STRIPPED node-side, before any write here)
CREATE TABLE run_record(
  node_id TEXT NOT NULL, run_id TEXT NOT NULL,
  record_raw BYTEA NOT NULL,        -- exact canonical bytes (hashable)
  record     JSONB NOT NULL,        -- derived projection of the same bytes (queryable)
  record_sha TEXT NOT NULL, ts TEXT NOT NULL,
  PRIMARY KEY(node_id, run_id));

-- exod attestation, verbatim (authority = the signature, not the writer)
CREATE TABLE step_envelope(
  node_id TEXT NOT NULL, run_id TEXT NOT NULL, step TEXT NOT NULL,
  envelope_raw BYTEA NOT NULL, exod_keyid TEXT NOT NULL,
  PRIMARY KEY(node_id, run_id, step));
```

Mothership grants (per node `n`, role `node_<n>`): `GRANT INSERT, SELECT` only — no UPDATE/DELETE/TRUNCATE
granted to anyone but the owner ("no delete" is a missing grant, not a trusted policy) — plus RLS
`WITH CHECK/USING (node_id = current_user-derived)`; the mothership role reads all. Center ingests into
**per-node schemas** (logical replication applies rows raw — the `_value_free`-style paranoia moves to
read-time, backed by signature/chain verification, size caps, and the schema boundary).

## Crypto

Envelope encryption with a **recipient set**: fresh per-blob DEK (AEAD, e.g. XChaCha20-Poly1305 or AES-256-GCM
per what's already vendored); DEK wrapped to each recipient's X25519 public key. Standalone recipient set =
{node}; post-handshake = {node, mothership-oversight}. Fleet join re-wraps *historical DEKs only* (bytes per
blob — never re-encrypts data). Node recipient key: generated at boot if absent, `chmod 600`, beside govd's
existing key material on the config mount — never in the DB, never on a replicated path. Rotation = new
recipient key + lazy re-wrap; revocation = stop wrapping + rotate.

**Honest limit (accepted residual):** govd sees values transiently (it is the writer); a fully compromised
*live* govd host reads them regardless. Encrypt-at-rest defends at-rest surfaces — replicas, backups, stolen
volumes, over-granted roles — which is exactly the surface federation and backup create.

## Write points (anchors, verified 2026-07-22)

- `infra/govern/govd.py` ~1339–1367 — the WS `step_request` handler: the post-filter `var_values` (declared
  subset, secret-stripped, ACL `params`-gated) is the ONE place plaintext exists server-side. Here: canonicalize
  → `values_sha` → encrypt → enqueue `StoreMirror.record_values(...)` (mirror keeps the decision path thin) →
  add `values_sha` to the step event appended at ~1368–1370.
- `infra/govern/delegate.py:153` — the step event dict: gains `values_sha`; the raw exod envelope (`envl`) is
  additionally routed to the mirror for `step_envelope`.
- `infra/store/mirror.py:27–30` — `_SAFE_EVENT_KEYS` gains `values_sha` (commitment only — values NEVER enter
  the chain/index projections). New queue op `values` handled by the single drain worker (preserves
  single-writer; `PsycopgBackend` is not thread-guarded and must stay behind that one worker).
- `infra/store/backend.py` — `StoreBackend` grows `record_values/get_values/record_envelope/record_full`
  (+ `budget_ledger` ported to the PG tier — today it is sqlite-only and a PG-first node would lose the credit
  shutoff); `store_selftest` grows contract cases for the new methods (both adapters, same suite).
- `infra/tool/fleetdash.py:141–152` — **BOTH** allowlists (`_RUN_KEYS`/`_EVENT_KEYS` AND `_INDEX_KEYS` where
  surfaced): `values_sha` only. The dashboard stays value-free; the operator values view reads PG + decrypts
  app-side with the mothership key.
- `deploy/` — PG-15 sidecar compose beside the body: bind the **tailscale interface only, never 0.0.0.0**
  (startup assertion refuses a wide bind — the `:8088` fileserver lesson), volume-backed, DSN via `dsn_file`.
- `infra/govern/fleetd.py` — registration handshake: mothership → node delivers the oversight *pubkey only*
  (nothing secret flows node-ward) + provisions the replication role cert out-of-band (`*_FILE`); node returns
  endpoints + govd/exod pubkeys; mothership then creates the per-node subscription (= admission).

## Milestones

> **Note on the governed board.** The implementation is almost entirely **kernel edits** (`govd.py`, `mirror.py`,
> `backend.py`, `fleetd.py`, `deploy/`), which are NOT `cws-addperk` operations — cyberware's own code is changed
> by normal edits and *gated* by the validator skills. So the companion playbook fires the **gates** (`cws-modelcheck`,
> `py_qc`, `cws-mutate`, `sec`, `cws-redteam-sw`, `cws-conform`, `cws-chaos`) against the working tree; it does not
> scaffold the code. Drive it with `cws:cws-pm/run` (`DRY_RUN=1` validates the whole board structurally; then per
> milestone, author the kernel edit → let the milestone's gate tasks redeem). Baseline dry-run: 25/25 validate.

**M0 — local value tier (standalone holds its own).** `valuecrypt` module (DEK/recipient-set, KATs);
backend methods + sqlite impl; govd WS write point + `values_sha` chain cross-bind; node recipient key at boot;
allowlist updates (mirror + fleetdash, both lists). Gates: property tests on invariant 3 (secret exclusion) and
2 (plaintext commitment); full pytest + selfmonitor (enforcement surface touched); **multi-agent adversarial
review before merge**; mutation floor on the new filter/commit lines (comment tokens stay space-clean).

**M1 — PG sidecar + parity.** Compose + bind assertion + `dsn_file` wiring; `PsycopgBackend` tier-2 tables
(raw+JSONB dual columns) + `budget_ledger` port; token-strip on `run_record`; `store_selftest` parity for PG
(CI: dockerized PG service, hermetic default stays sqlite); backfill tool `infra/tool/pgbackfill.py`
(sqlite/chain → PG, chain-verified, idempotent).

**M2 — fleet share.** Node publication DDL + replication role + pg_hba (hostssl, cert, mothership-addr only);
`fleetd` handshake exchange; mothership aggregate (per-node schemas, RLS/grants DDL, **no inbound port**);
subscribe-on-registration; DEK re-wrap backfill to the mothership recipient; center-side chain-verifier job
(recompute link_digest per node/run; re-verify exod envelopes); tailnet ACL **template** (one line:
`mothership → tag:fleet-node:5432` — real topology never enters the repo).

**M3 — oversight surfaces + drills.** fleetdash reads the PG aggregate (feed parity with the JSON mirror,
which remains the reconcile path); operator values view + audit CLI (`decrypt → values_sha → chain` in one
command); chaos drills: revocation tri-layer (ACL line / subscription / cert — each alone severs), partition →
replication catch-up, key rotation + lazy re-wrap; backup canary (plant a known plaintext value, prove NAS
artifacts carry ciphertext only); docs (`architecture.md`, `governance-service.md`, SECURITY residuals:
live-govd reads values · JSONB normalization · single-mirror-writer · replication-applies-raw).

## Rollout / discipline

One PR per milestone slice, **landed on `main` via PR** (releases cut from main only); adversarial review on
every enforcement-surface change (M0 govd/mirror, M2 fleetd/handshake); CI green = ALL checks before merge;
image rebuild + tag advance after M1 (the body ships psycopg + compose); fleet repull after M2 (repull-trap:
re-pin before restart). Dogfood: run the build tasks through govd per the playbook JSON.
