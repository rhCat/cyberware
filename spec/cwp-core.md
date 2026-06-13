# cyberware — Cyberware Protocol core (`spec/cwp-core.md`)

> Task **P0-T01**. Defines the wire protocol between an agent and the governance plane (`govd`): the
> versioned envelope, every message type, and the error model. Normative for `govd`, `govd_client`, and
> `exod`. Hashes are over the JCS-canonical body (`spec` — RFC 8785, `infra/cwp/canonical.py`).

## 1. The envelope

Every message **MUST** be a JSON object of the form `{cwp, type, body, sig}`:

| field | meaning |
|---|---|
| `cwp` | protocol major version (an integer); a receiver **MUST** reject a major it does not implement |
| `type` | the message type (§2) |
| `body` | the type's value-free payload — names, var **KEYS**, and hashes only; never values, files, or secrets |
| `sig` | a DSSE signature over the canonical `body`, carrying a resolvable `key-id` (`spec/keys.md`); a message whose `sig` does not verify **MUST** be refused |

The `body` **MUST** carry only metadata: a claim names a skill, a perk, and var KEYS — never their values
(the data-stays-local boundary). A `sig` **MUST** sign the JCS-canonical bytes of `body`, so any
implementation reproduces the signed digest.

## 2. Message types

The protocol defines this closed set of message types; a receiver **MUST** refuse an unknown `type`:

- **`claim`** — agent → govd: `{skill, perk, var_keys[]}`. The agent's only output; it **MUST NOT**
  contain commands or values.
- **`plan`** — govd → agent: the value-free, code-free execution plan (tool `sequence`, each snippet's
  sha256, the `${VAR}` wrapper) plus the pinned `plan_sha`.
- **`grant`** — govd → agent: authorization for one step, bound to `(run_id, step, plan_sha)`, with
  `nbf`/`exp`/`nonce`; a `step_request` without a matching prior `grant` **MUST** be refused.
- **`step_request`** / **`step_result`** — the per-step request and its recorded outcome; a `step_result`
  **MUST** be idempotent by `(run_id, step)` (`spec/inflight.md`).
- **`verdict`** — govd → agent: the governance decision for a claim (admitted / pushed-back, with named
  reasons).
- **`approval`** — a WebAuthn-locked consent for a destructive operation (`spec/keys.md`).
- **`receipt`** — the dual-signed record of a completed run (exod execution+meters + govd governance).
- **`revocation`** — a feed entry withdrawing a key or a skill; honored per `spec/inflight.md`.

## 3. Error model

Errors **MUST** be enumerated, not free-form; every refusal carries a stable reason code:
`unknown_type`, `unsupported_cwp`, `bad_sig`, `unknown_key_id`, `value_in_body`, `no_grant`,
`plan_sha_mismatch`, `nonce_replay`, `expired`, `revoked`, `oversight_refused`, `tamper`,
`upstream_missing`, `approval_required`. A refusal **MUST** be recorded as evidence (meta-rule M4), and a
client **MUST** treat any unlisted error as fatal rather than retrying blindly.

---

*Enforced by: the governed-conformance run (P0-V06) and the cross-language golden vectors (P0-T07/T08);
the value-free-body invariant is exercised by govd's "never receives values" test. Messages not yet on the
wire (`receipt`, `revocation`, `approval`) are specified here ahead of their phases (P3/P6) — this is the
protocol, not the current surface.*
