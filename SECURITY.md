# Security Policy

cyberware is a governance kernel, so security reports matter to us. If you believe you have found a
vulnerability, we want to hear from you — and we will respond.

## Reporting a vulnerability

**Preferred — encrypted, no key exchange needed on your side:** open a private report through GitHub, via the
repository's **Security → "Report a vulnerability"** (GitHub Private Vulnerability Reporting). GitHub encrypts
the report in transit and at rest.

**Alternative:** email the maintainer at **ruihe93@gmail.com**. For end-to-end encrypted email, request our
current **age** public key (or a PGP key) at that address first and we will reply with the recipient before
you send any details — or simply use the GitHub private channel above, which is already encrypted.

Please include the affected version or commit, a description, and a minimal reproduction if you have one.
Please do **not** open a public issue for a suspected vulnerability before it has been addressed.

## Our commitment (acknowledgement SLA)

- **Acknowledgement:** we will acknowledge your report within **72 hours**.
- **Triage:** an initial assessment (severity and whether it is in scope) within **7 days**.
- **Fix and disclosure:** we aim to ship a fix and coordinate disclosure within **90 days**, keeping you
  updated along the way. Credit is offered to reporters who want it.

## Scope

The governance kernel — `infra/` (govd, the executor channel, the verifiers) and the `skillChip/` registry —
is in scope. The enforcement surfaces (`govd.py`, `executor.py`, `oversight.py`, the `*verify.py` cores) are
the highest-value targets. Findings that bypass a governance boundary are especially welcome: a refusal that
should have fired but did not, a value or secret crossing the agent↔govd boundary, or a step running unblessed.

The **delegated execution boundary (SV-3)** is also in scope: **exod** (`infra/exec/exod.py`), the
`closureverify.py` / `grantverify.py` / `exodverify.py` cores, and the confined sandbox (`infra/exec/sandbox.py`).
High-value findings there include a forged exod signature accepted as authoritative status, a grant-nonce
replay that goes undetected, a step running as root despite `exec-never-root`, or a sandbox confinement escape.
