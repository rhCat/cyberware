"""infra.cwp — the Cyberware Protocol primitives (canonicalization, digests; signing is ROADMAP).

The one canonical-bytes path: every hash in cyberware (skill_sha, chip_sha, plan_sha, ledger links) is
sha256 over the JCS-canonical form, so an independent implementation reproduces it byte-for-byte.
"""
