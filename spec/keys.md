# cyberware — Key lifecycle (`spec/keys.md`)

> Disposition of grill finding **M2**: v1.0 had no key lifecycle — generation, custody, rotation,
> compromise, and bootstrap were unstated. This spec decides them. Normative for `govd`, `exod`, the
> settlement plane, and the release pipeline; the custody seam is T29, the rotation drill is P3-T06.

## 1. The hierarchy

Keys **MUST** form a three-tier hierarchy: an offline **deployment root** (held on a hardware token,
used only to sign overrides, key rotations, and release policy), online **service keys**
(`govd-grant`, `exod-receipt`, `settle-ledger`, `feed-sign`), and per-store **HMAC keys**. A service key
**MUST NOT** sign anything the deployment root is responsible for, and the deployment root **MUST NOT** be
an online key.

## 2. Key identity

Every DSSE envelope **MUST** carry a resolvable `key-id`; a signature whose `key-id` does not resolve to a
known, non-revoked key **MUST** fail closed.

## 3. Rotation

A service key **MUST** be rotatable with an overlap window during which both the old and new key verify,
and each rotation **MUST** append a cross-signed `key_rotation` record to the ledger; in-flight grants
signed by the old key remain honored until their `exp`, after which the old key **MUST** be feed-revoked.

## 4. Compromise

On compromise the key **MUST** be feed-revoked with a `compromised_at` timestamp, and everything signed by
that key after that instant **MUST** be treated as invalid; recovery **MUST** follow the documented
re-attestation procedure, never a silent re-issue.

## 5. Bootstrap

An agent **MUST** learn `govd`'s key by deployment-config pinning (distributed like SSH `known_hosts`);
trust-on-first-use **MUST** be rejected for priced or destructive operations, and **MAY** be permitted,
with a warning, only for read-only discovery.

---

*Enforced by: P0-V12 (the `KeyStore` seam — file + PKCS#11 stub), P0-V13 (every DSSE carries a resolvable
key-id; an unknown one fails closed), and P3-V13 (the rotation drill — a grant signed by the old key after
its revocation refuses). Custody backends evolve behind the T29 `KeyStore` adapter.*
