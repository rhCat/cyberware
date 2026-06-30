# Settlement — the economic layer (SV-6)

The settlement layer (`infra/settle/`) is where governed work turns into money. It is built on one
discipline carried all the way down: **value is only ever moved, never created or destroyed, and never
represented as a binary float.** Every amount is an exact scale-4 `Money` decimal; every money movement is a
balanced double-entry posting set on a prev-hash-chained ledger; and the events that release money — a
priced run admitting, a payout settling — are each keyed on a signed artifact (a funded quote, a dual-signed
validation receipt) so that no payment can happen without proven, authorized work. This document describes
what each module *enforces*, and marks anything that is inert, optional, or keyed on configuration as such.

A note on status: most of what follows is exercised by an in-module `*_selftest()` rather than a live
production deployment. The `StripeRail` is the clearest example of a deliberately inert seam — it does
nothing until an operator wires a key. Where a path is keyed on external config or an external engine, it is
called out below.

## Money — exact decimal, float-banned

`infra/settle/money.py` defines the `Money` type: an exact `Decimal` quantized to **scale 4** (four
fractional digits) under an explicit context that rounds **HALF_EVEN** (banker's rounding). The scale and
context are module constants: `SCALE = 4`, `QUANT = Decimal("1").scaleb(-SCALE)`, and
`CTX = Context(prec=34, rounding=ROUND_HALF_EVEN)`. Arithmetic (`__add__`, `__sub__`, `scale`) stays in
`Decimal` via `CTX` and re-quantizes.

The float ban is enforced at two levels:

- **At the type boundary.** `_to_decimal` accepts only `int`, `str`, or `Decimal`; a `float` (and a `bool`,
  which is an `int` subclass) is rejected with `TypeError`. So a float can never even be *constructed* into a
  `Money`.
- **As an AST lint.** `float_ban_scan(paths)` walks the Python AST of the settlement modules and flags any
  float literal (`ast.Constant` whose value is a `float`) or any `float(...)` call. `float_ban_selftest()`
  asserts the `infra/settle/` tree contains zero such intrusions *and* that the lint actually fires on a
  seeded bad file (so the zero-count is a real verdict, not a no-op).

Splitting an amount uses the **largest-remainder method**: `split(total, weights)` expresses the total in
integer scale-4 units, floors each share, and distributes the leftover units to the shares with the largest
truncated remainders (ties broken by index). The guarantee is that the parts re-add to the total *exactly* —
this is what makes a quote breakdown or a tax split zero-sum to the cent rather than merely "close".
`money_selftest()` checks HALF_EVEN rounding at the scale-4 boundary, float refusal, conservation under
add/sub, and exact re-summing of awkward splits (e.g. `$100` split 1:1:1).

## Quotes and funded-escrow admission

`infra/settle/quote.py` governs whether a *priced* perk is allowed to run at all.

`compute_quote(plan_sha, amount, split_policy, fmv)` builds a value-bound quote: the amount split across the
policy's accounts by exact weights, bound to a `plan_sha` and an FMV string. `sign_quote(quote, priv_pem)`
is the **authorization token** — govd signs the canonicalized quote with Ed25519ph DSSE
(`cosign.sign_ph(..., payload_type=QUOTE_TYPE, keyid="govd-quote")`). `quote_sha` is the content id a grant
references and escrow funds.

`verify_quote(envelope, pinned_pub_pem)` returns `(ok, quote)` and requires the envelope to be the quote
type, signed, verifying under govd's pinned key, *and* to have a breakdown that re-sums to the amount
(`breakdown_balances`). A tampered, unsigned, or wrong-type quote fails here.

Funding is **per-quote isolated**. `fund_quote` holds the amount in the quote's *own* escrow sub-account,
`reward_ledger.escrow_for(quote_sha)` — never a fungible pool. `is_funded` checks that *this* quote's escrow
holds at least its amount, so one quote's funding can never make a different quote look funded.

The admission gate is `grant_admits(envelope, entries, plan_sha, priced, pinned_pub_pem)`. A free perk needs
no quote (`{"allow": True, "reason": "free_perk"}`). A priced perk is admitted only with a quote that is
(1) present, (2) verified, (3) plan-matched (`q["plan_sha"] == plan_sha`, else `plan_mismatch`), and
(4) funded (else `quote_unfunded`). `quote_selftest()` exercises every refusal branch, including
**cross-quote isolation**: funding one quote leaves a distinct same-amount quote `quote_unfunded`.

Escrow has a liveness guarantee in `infra/settle/escrow_expiry.py`. Every funding via `fund_with_expiry`
carries an `expires_at`; `sweep_expired(entries, now)` auto-refunds any funded, unsettled, un-refunded
escrow whose `expires_at <= now` back to its funder as a balanced posting set. The sweep is idempotent
(a refunded key is skipped via `_settled_or_refunded`) and uses a deterministic injected `now` (no wall
clock). `stale_escrow_keys` is the audit that no escrow older than its bound still holds value.

## Payout — settle on a dual-signed pass receipt, at most once

The settlement engine is `infra/settle/engine.py`. `settle(entries, receipt, quote_env, exec_pub,
approver_pub, govd_pub, ...)` is a pure function that consumes a receipt and writes **at most one** atomic
posting set, or refuses and writes nothing. It pays out only when all of these hold, checked in order:

1. the receipt is **dual-signed** (both executor and approver Ed25519-DSSE signatures verify, via
   `receipts.verify_receipt`), else `not_dual_signed`;
2. the receipt's predicate carries **`validation == "pass"`**, else `validation_not_pass` (a flipped verdict
   is rejected);
3. the quote envelope **verifies** under govd's key, else `quote_invalid`;
4. the receipt is **bound to that quote** (`pred["quote_sha"] == quote_sha(q)`), else `quote_unbound`;
5. the quote has **not already settled** (the idempotency guard, below), else `quote_already_settled`;
6. the quote is **funded** in its escrow, else `quote_unfunded`.

On success it writes one balanced posting set: the quote's escrow sub-account is drained, the fee and payee
are credited per the quote breakdown, and a **dispute-window holdback** (default `hold_weight=10` /
`keep_weight=90`, an exact `split` of the payee part) is parked in a `hold:{sha[:16]}` account. The posting
set is tagged `settle:quote:{sha}`.

The **at-most-once** property comes from `_already_settled(entries, quote_sha)`, which scans for a
`posting_set` whose memo is the `settle:quote:<sha>` tag. It is keyed on the `quote_sha`, **never** on the
attacker-chosen `run_id` — so re-funding the same quote and replaying the receipt is refused
(`quote_already_settled`) and no second settlement record is written. `engine_selftest()` covers the happy
path (escrow drains to zero, global ledger stays zero-sum), three mutant receipts (signature stripped,
verdict flipped, quote unbound) each settling nothing, the same-quote replay double-pay refusal, cross-quote
escrow isolation, and the post-window holdback release (`release_holdback`).

The ledger underneath is `infra/settle/reward_ledger.py`, a Ledger-v2 instance (the same prev-hash chain as
`infra/cwp/ledger.py`). `post` **refuses** any posting set that is not balanced (`is_balanced` — signed
amounts sum to exactly zero per currency). `global_zero` folds the whole chain to confirm conservation, and
`balance_root` is a Merkle root over the per-account balances, so a verifier can attest the balance set
without replaying the chain. `reward_ledger_selftest` runs a 10k-settlement storm and asserts escrow is zero
at the terminal state and the chain stays globally zero-sum.

A separate cross-plane check lives in `infra/settle/reward_verify.py`. `reward_verify` proves a **bijection**
between the *money trail* (`settled_quote_shas` — every `settle:quote:<sha>` posting set) and the *work
trail* (`authorized_quote_shas` — every dual-signed, `validation==pass`, quote-bound receipt). It flags a
settlement with no authorizing receipt (`money_without_work`), an authorized receipt never paid
(`work_without_money`), and any `double_settled` quote. So the money and work trails cannot silently diverge.

The high-value time anchor is `infra/cwp/tsa.py`. A TSA token is `{receipt_sha, time}` signed by a TSA key
(cosign-shaped DSSE) and verifiable **offline** against a pinned key (`verify_token` — no live TSA call).
`settlement_eligible(receipt, token, value, ..., threshold=DEFAULT_THRESHOLD)` is the value-threshold gate: a
receipt at or above the threshold (default `1000`) is eligible only with a valid token (`tsa_missing` /
`tsa_invalid` are hard stops); below the threshold it settles without one. Note this threshold gate is a
**standalone primitive that currently has no caller** outside its own selftest — the core `engine.settle`
path does not invoke `settlement_eligible`, so the value-keyed TSA requirement is not yet wired into the
settle pipeline. The TSA primitive *is* exercised elsewhere — the capstone (below) uses `tsa.timestamp` /
`tsa.verify_token` directly to anchor the plan-completion receipt — but that is the timestamp-and-verify path,
not the threshold gate.

## Tax and lineage royalty over pluggable rails

`infra/settle/rails.py` collects the platform tax **at settle time**, not as an agent action. The doctrine
is explicit in the module: making the agent call a "pay" skill would itself be a tax (an extra LLM
round-trip it can fumble or skip), so the engine — which already priced the run's shape — collects
automatically; and the tax *is* the transparent itemized price, never a hidden skim.

`charge_from_price(price_quote, plan_sha)` turns the pricer's quote into a named, three-line split:
`substrate` (LLM / NVIDIA usage), `skill_author` (the skill's pay route), and `marketplace` (the platform's
visible cut). `split_balances` requires the breakdown to re-sum to the total exactly, and `collect_tax`
**refuses** any charge whose split does not (a skim). Collection is idempotent on the `plan_sha` via
`_already_collected`.

Three rails implement `collect`:

- **`LedgerRail`** (default) — posts the split to the reward ledger by double entry: the operator is debited
  the total; `substrate` / `skill_author` / `marketplace` are credited their lines. This is the free /
  self-hosted tier and is fully deterministic.
- **`StripeRail`** — the seam. It charges the operator's account for the quoted total with
  `Idempotency-Key = plan_sha` and the line items as metadata. It is **inert until `config.key_file` is
  set** (`{"status": "unconfigured"}`); the operator wires the key server-side and the agent never sees it.
  `usd_to_minor` truncates to integer cents, and a sub-cent total returns `below_minimum` — which is exactly
  why per-call micro-taxes are not viable as one-shot card charges.
- **`CreditRail`** — debits a prepaid balance (see next section), the production per-call model.

`collect_run_tax(skill, perk, plan_sha, ...)` is the one-call settle-time entry point: it prices the plan,
builds the transparent charge, and collects via the rail named by `pricing.json`'s `rails.default`. With no
rail wired it builds the default. It is idempotent on `plan_sha`.

The **lineage royalty** is a separate split in `infra/settle/royalties.py` and is keyed on an external
engine. `publish_with_royalty` attempts a verified-tier publish of a subject; it calls `alchemy.publish_gate`
and only proceeds if alchemy **admits** the subject. On admission the revenue is split (default
`royalty_weight=15` / `keep_weight=85`) — a royalty share to the `alchemy:lineage` account, the rest to the
publisher — as a balanced posting set, and a lineage receipt is returned. A subject alchemy *blocks*
(a conservation defect, an unnamed shape, a CFG mismatch) is not published and pays no royalty. This path
requires the pinned alchemy/putrefactio engine to be present (`alchemy.tools_present()`).

## Credit-tier prepaid billing

`infra/settle/credits.py` is the answer to per-call card fees: a per-call $0.006 usage tax would cost ~50x
its value to collect through a flat ~$0.30 Stripe fee. So the operator **tops up** a credit balance with one
charge (the flat fee amortized over thousands of calls), and each priced run **debits** its tax internally.

- `topup(entries, operator, amount, source, ref)` adds prepaid credits as a balanced posting
  (`credit:{operator}` credited against a `topup:{source}` account), idempotent on `ref`.
- `debit_usage(entries, operator, charge, idem_key)` is what `CreditRail.collect` calls. It draws the total
  down from `credit:{operator}` and posts the same transparent `substrate` / `skill_author` / `marketplace`
  split — with **no Stripe call**. It is idempotent per run (`usage:<idem_key>`).
- The **structural affordability gate**: if the balance can't cover the tax, the debit posts **nothing** and
  returns `insufficient_credits`. The tax is therefore a gate on running, not an after-the-fact bill.
  `admits(entries, operator, tax_total)` is the explicit predicate form.

The whole flow is zero-sum: the debit re-sums to zero (operator drawn down, split credited). The module notes
that real disbursement of the split to connected accounts is a separate Connect step — the credit posting is
the *record*, not the payout to third parties.

## Per-actor credit budget — the gauge + the shutoff

`infra/settle/budget.py` is the **per-actor** counterpart to the operator credit tier above: for an event
where many principals fire claims at one node (or a fleet), the organizer caps **each actor's** spend, hard-
stops them at the cap, and watches it live. Where the credit tier is one operator balance behind a Stripe
top-up, a budget is **one credit account per principal id**, enforced wherever that actor fires.

- **The ledger is the actor's account.** `account_of(actor) = "budget:<actor>"`; `balance = seeded allowance
  + top-ups − debits`, every term an exact-decimal CREDITS posting in the same zero-sum `reward_ledger`, so
  the existing conservation checks validate the budget chain for free. `seed`/`topup`/`debit` are the in-memory
  posting form; the **durable, concurrency-safe** debit lives on the store backend.
- **The decision is pure.** `budget_ok(actor, price, balance, *, configured) -> (ok, problem)` is I/O-free and
  fail-closed: not configured → `budget_unmetered`; balance unreadable → `budget_unavailable`; balance < price
  → `insufficient_credits` (the shutoff); else allow. `configured_allowance(spec)` resolves an actor's opening
  allowance from its principal spec — `credits:` or, equivalently, `budget:` — and the gate uses that **same**
  predicate, so "configured" ⟺ "seeded" (a key present but null reads as unmetered at both — never a metered-
  but-unseeded lockout).
- **The debit is atomic and actor-wide.** `infra/store/backend.py`'s `budget_ledger` table +
  `budget_debit_atomic(actor, price, idem)` re-read the balance and debit **only if it still fits**, all inside
  one transaction — a `BEGIN IMMEDIATE` (sqlite) or a `pg_advisory_xact_lock(hashtext(actor))` (Postgres) that
  serializes same-actor debits — the **same serialize-then-conditional-write primitive as the HA lease**.
  Two concurrent same-actor claims therefore can't both pass when only one fits; a shared store makes the
  balance truly actor-wide across nodes, and a store partition **fails closed** (balance unreadable → reject),
  never over-spends. Idempotent on `idem` (`usage:<run_id>` for a run debit — a retried run is a no-op, not a
  double charge), scoped to `(actor, idem)` so the same idem under two actors both charge.
- **Pricing is negotiable, declared in the skill.** `infra/settle/credit_price.py` resolves a run's price in
  order: the operator's negotiable `credit_prices` override in `pricing.json` (tried `skill/perk → leaf/perk →
  skill → leaf → namespace` — canonical id then bare leaf, so a legacy un-namespaced table still prices a
  namespaced claim) → the skill's **own** declared `credit_price` (the perk's `metadata.json`) → `_default`.
  The skill author **declares** the price; the operator **negotiates** via the override.
- **The gate is two-phase** (closing the TOCTOU). A pure snapshot pre-check runs **last** in `govern()`
  (skipped if the claim already has other problems or needs approval — no reservation for a doomed claim),
  appends `insufficient_credits` on fail → **403** (a real shutoff, not `--approve`-able). The **authoritative**
  atomic debit then runs in `do_POST` on `allow`, before the record is written; if it loses the race the
  decision flips to `reject`. The snapshot is the clean common-case reject; the atomic debit is the truth. A
  value-free `cost` (a CREDITS string) is stamped on the verdict, the record, and the decisions feed.
- **Enforcement is opt-in.** `budget_enforce` (a config flag, default **OFF**) gates the whole thing — an
  un-flagged server meters nobody (back-compat), and local dev (no principals registry) is always unmetered.
  With it ON, every authenticated actor must carry a non-null `credits`/`budget` allowance (seeded at startup)
  or be rejected `budget_unmetered`.

**Credits in — recharge, no per-run dollar charge.** Two paths add credits, both posting to the same
`budget_ledger`, live with no restart: an **operator grant** (`POST /budget/topup {actor, credits, ref}`,
monitor-token-gated — the event organizer's lever, idempotent on `ref`, a unique ref minted when omitted), and
a **Stripe recharge** (`POST /budget/recharge` mints a PaymentIntent to *buy* credits — the `credits.py`
thesis: one occasional purchase amortized over many internal debits — **inert until the operator wires
`stripe.key_file`**; the agent/system never sees the card, Stripe's own UI does). Per run there is only a
CREDITS **debit**, never a dollar charge.

**Accounting — per-node, fleet, individual.** Each node's monitor renders its own `by_actor` rollup
(`budget.rollup → {by_actor:[{actor, allowance, spent, balance, runs}], fleet}`) at `GET /budget` (+ a JSON
`/budget/state`): a gauge per actor that goes **green < 70%, yellow < 100%, red ≥ 100%** of that actor's
allowance — the node holds the ledger, so it shows allowance/balance directly. The fleet dashboard
(`infra/tool/fleetdash.py`) aggregates spend **across** the fleet from the mirrored value-free `cost`:
`/accounting` ranks per-actor credit spend with a gauge relative to the top spender, and `/principal/<actor>`
is that actor's cross-fleet account.

**Residuals (honest).** Debit timing is **reserve-on-allow = charge** (v1) — a refund-on-never-run reconciler
keyed on the run id is a documented, deferred residual. Single-node (the common event case) is trivially
actor-wide; multi-node is actor-wide via the shared transactional store. Stripe recharge's PaymentIntent
confirmation/webhook is the heavier slice; the operator-grant path is the event MVP.

## Metered usage — pay for work-shape, refund on fail

`infra/settle/metered.py` makes an exod-**attested** usage meter settleable for metered (`llm/*`) steps. The
doctrine, enforced in `settleable(meter, receipt, rate, floor, cap, ...)`:

- the meter must be exod-attested (`meter["by"] == "exod"`), else `meter_not_attested` — an un-attested
  count is never settleable;
- if a provider **receipt** is present, it is honored only if it is in the run's currency, its *tokens*
  reconcile with the attested meter within a relative tolerance (`reconcile`, default `tol="0.05"`), *and*
  its *cost* does not exceed the rate-implied cost of the attested tokens by more than `cost_tol`
  (default `0.10`). A reconciling receipt settles at its cost — a **pass-through reimbursement** of the real
  provider cost, clamped to `[floor, cap]`. A receipt that contradicts the meter on tokens
  (`receipt_meter_mismatch`) or over-bills on dollars (`receipt_cost_exceeds_attested`) is unsettleable —
  never silently paid;
- absent a receipt, the step settles at the exod-attested token count priced at the model rate, clamped —
  the attested fallback, never the agent's word.

The float ban reaches here too: a receipt `cost` that is a binary `float` (or missing) is refused
(`receipt_cost_not_exact`) rather than laundered through `str()`. `reimbursement_posting` is the balanced
payer→provider lane. The "pay for work-shape not effort / refund-on-fail" intent is realized by the clamp to
a metered `[floor, cap]` plus the unsettleable verdicts above: a step whose attested shape doesn't justify
the bill simply doesn't settle.

## Throughput — single-writer-per-currency group commit, O(accounts) resume

`infra/settle/throughput.py` scales settlement without losing the double-entry invariants.

`GroupCommitWriter` is **one writer per currency**. Posting sets are `stage`d and then `commit`ted as a
batch: the *whole* batch is validated balanced and in the writer's currency first, then appended atomically
— a single unbalanced or foreign-currency set raises **before any append** (all-or-nothing; the chain never
sees a partial group) and the rejected batch is dropped from the stage so the writer is not wedged. A
per-writer `threading.Lock` serializes commits so two writers never interleave on the same currency's chain.
The writer keeps **running balances** incrementally (O(postings) per commit), seeded from whatever the chain
already holds.

`checkpoint()` captures the committed balance set plus its balance-root — the *same* Merkle commitment
`reward_ledger.balance_root` computes — in **O(accounts)**, no re-fold of history. `resume_verify(ckpt)`
recomputes the root from the stored balances (must match) and confirms the balances conserve value (zero-sum
per currency), in O(accounts) independent of entry count. It catches an altered balance, a tampered root, and
a non-conserving forged checkpoint. The module is honest that **binding** a checkpoint to a specific ledger
history is a separate full-fold audit, not this O(accounts) resume check.

## Disputes, reputation, FMV, markets, bounties

**Disputes** — `infra/settle/disputes.py`. A settled run can be disputed within a window, all ledgered:

- `open_dispute` posts a **bond** into a `dispute-bond:{sha[:16]}` account (skin in the game).
- Resolution is **m-of-n WebAuthn**: `resolve` counts *distinct* arbiters whose WebAuthn approval over the
  resolution doc verifies offline (`count_approvals`, reusing the P3 WebAuthn artifact with challenge
  `sha256(JCS(doc))`). Quorum must be a real `m >= 2` (`quorum_too_small`), and fewer than `m` distinct
  valid approvals leaves it unresolved (`insufficient_approvals`). An approval over a *different* doc does
  not count.
- On **upheld**, the settlement's holdback is clawed back to the disputer and the bond is returned, and the
  payee's reputation takes a `-1` delta. On **rejected**, the bond is **forfeited** to the payee and the
  disputer takes the delta. Every move is a balanced posting set; `dispute_selftest` confirms the ledger
  stays zero-sum on both paths.

**Reputation** — `infra/settle/reputation.py`. `compute_scores(entries)` derives per-principal scores
(settlement count, settled total, a count-weighted score) and a public `fmv_point` (median credit) from
**public ledger data alone** (`payee:` credits), so any third party recomputes the identical table
byte-for-byte. The table is Ed25519-signed (`sign_scores` / `verify_scores`) — tamper-evident. `rep_view` is
**privacy-gated**: an authenticated counterparty sees per-principal detail; everyone else gets aggregates
only (`n_principals`, a public FMV point, an aggregate score) — never per-principal names or scores.

**FMV** — `infra/settle/fmv.py`. `fmv_index(trades)` is a deliberately manipulation-resistant statistic: a
**volume-weighted median** (a minority of extremes can't drag it), with **common-control capping**
(`_collapse_controls` collapses each `control` to one effective participant capped at the average honest
volume share — sybils and whales can't dominate) and **price-extreme trimming** (`_trim`, the top/bottom
`TRIM_FRACTION = 0.10` of volume). Admission requires `n >= 20` trades from `>= 8` distinct controllers
(`ADMISSION_N` / `ADMISSION_DISTINCT`); below that, or for a **multimodal** market (a dominant gap splitting
volume into two clusters — `_is_multimodal`), the index is published `provisional` with a reason, since a
positional median is unstable across such a gap. The selftest enforces the bound that 20% adversarial volume
at an extreme price moves an admitted unimodal index by under 2%, and that a bimodal market refuses to
publish a firm, manipulable index.

**Markets** — `infra/settle/markets.py`. Two competitive award mechanisms over the escrow/posting machinery:

- `award_bounty` funds one prize escrow and releases it to exactly one **validated** competitor (`first` =
  first validated, or `best` = highest `score`); losers are never debited; with no validated entry the prize
  refunds to the poster.
- `clear_reverse_auction` clears at the **lowest qualified bid** at or below the posted ceiling (first-price),
  and does not clear when no bid qualifies.

**Self-bounty** — `infra/settle/selfbounty.py`. cyberware's own security program runs through its own
ledger: `run_security_program` treats each vulnerability class as a bounty (over `markets.award_bounty`), and
a **validated** disclosure (a reproduced vulnerability) pays an external researcher through the reward
ledger; a class nobody validates refunds the sponsor. The program's front door is the repo `SECURITY.md`
doorbell (the selftest checks `doorbell.doorbell_selftest()`), and the whole program conserves value.

## SV-6 capstone — settling cyberware's own milestones

`infra/settle/capstone.py` is the closing move: cyberware's own development is settled into its own economy.

`redeemed_milestones` reads the real prev-hash-chained done-ledger (`docs/done-ledger-v2.json`) for the
`task_id`s whose `verdict == "pass"`. `settle_bounties` runs each milestone through the **full pipeline** —
a funded quote (`compute_quote` → `sign_quote` → `fund_quote`), a dual-signed `validation:pass` receipt
(`engine.build_receipt`), and the settlement engine (`engine.settle`) writing one balanced posting set per
milestone — and emits one FMV trade observation per settled milestone, **seeding the first FMV index**.

`plan_completion_receipt` then emits the plan's completion as a **dual-signed, TSA-anchored** receipt: a
dual-Ed25519-DSSE in-toto statement over the completion summary, countersigned by the TSA via
`tsa.timestamp`. `verify_plan_completion` verifies it **offline end-to-end**: both signatures
(`receipts.verify_receipt`) *and* the TSA token countersigning this exact receipt (`tsa.verify_token`) — no
network at verification time. `capstone_selftest` asserts the ladder closes when `>= 10` milestones have
settled, the ledger is zero-sum, the FMV index admits, and the completion receipt verifies offline (and a
TSA token bound to a *different* receipt is caught).
