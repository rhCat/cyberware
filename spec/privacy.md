# cyberware — Privacy (`spec/privacy.md`)

> Disposition of grill finding **M5**: immutability collides with privacy law, *metadata is data*, and
> v1.0's `/rep` published PII. This spec decides how an append-only chain coexists with erasure. Normative
> for the ledger (P1 crypto-shredding) and the settlement plane (P6 `/rep` gating).

## 1. Data classes

Three classes **MUST** be distinguished and handled per their class: **task content** (never crosses the
governance boundary — unchanged from v1.0), **identity metadata**, and **value metadata**. Identity and
value metadata **MUST** be treated as data, not as exempt "mere metadata".

## 2. Crypto-shredding

Personal fields inside ledger records **MUST** be stored as ciphertext under a subject-scoped data
encryption key (DEK), and the chain **MUST** hash the ciphertext — so erasure of a subject's data is
performed by destroying that subject's DEK, and the chain **MUST** still verify end-to-end after erasure.

## 3. Bulky payloads

A bulky payload **MUST** be referenced from the chain by hash only; the chain **MUST NOT** inline the
payload itself.

## 4. Retention

Records **MUST** carry a retention tier, and data **MUST NOT** be retained past its tier except where a
superseding legal hold is itself recorded.

## 5. Reputation and index privacy

`/rep/<principal>` detail **MUST** be gated to authenticated counterparties; public reputation views
**MUST** be aggregate-only; and FMV publication **MUST** hold its k-floor of at least 8 distinct
initiators as a privacy property, not merely an anti-gaming rule.

---

*Enforced by: P1-V13 (the erasure drill — destroy a subject DEK, the chain still verifies, the subject's
fields are unrecoverable, non-subject queries unaffected) and P6-V19 (the `/rep` access matrix —
non-counterparties receive aggregates only).*
