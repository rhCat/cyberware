# cyberware — Time authority (`spec/time.md`)

> Disposition of grill finding **M8**: v1.0 trusted clocks and self-asserted timestamps. This spec
> decides what time is authoritative and when. Normative for `govd` (grant skew, nonce caches), `exod`
> (meters), and the settlement plane (dispute windows). The adapter is the T27 `Timestamper`.

## 1. Wall-clock source

Hosts **MUST** run NTS-secured NTP as an operational requirement; an unauthenticated NTP source **MUST
NOT** be relied on for any wall-clock check that gates a priced or destructive operation.

## 2. Monotonic clocks

Nonce caches and TTLs **MUST** be driven by a monotonic clock, not the wall clock, so that a wall-clock
adjustment (or a skew attack) cannot expire or revive them incorrectly.

## 3. Timestamps are claims

A ledger timestamp **MUST** be treated as an unverified claim unless it is countersigned by an RFC 3161
TSA; consumers **MUST NOT** treat a self-asserted timestamp as authoritative for value or dispute logic.

## 4. Third-party anchors

A receipt above the configured value threshold, and every dispute-window boundary, **MUST** carry a TSA
countersignature; absence of a required countersignature **MUST** block settlement eligibility.

---

*Enforced by: P2-V14 (clock-skew injection — grants and nonce caches behave per this spec; monotonic TTLs
unaffected, wall-clock checks fail closed) and P3-V14 (every above-threshold receipt's TSA countersignature
verifies offline; absence blocks settlement).*
