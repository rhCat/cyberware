# Per-actor token ACL for govd — design

> Status: **design / v1.2** · grounded in code, adversarially reviewed (3-proposal panel → judge → red-team; 21 blocker/major findings folded in). Not yet implemented.

## Summary

A per-principal (per-token) capability SCOPE bound to each govd-issued actor token: a deny-by-default allow-list of CANONICAL skill/perk ids plus a tier CEILING and a secret-access gate, carried in the sha-keyed principals.json spec (names/labels only, never the token value), threaded into the pure govern() as a defaulted `scope` arg AND re-checked on the WS step path, enforced as APPENDED problems[] -> hard non-self-approvable reject. This FINAL design folds every blocker and major from the adversarial review into the relevant fields. Six structural changes vs the synthesized draft: (1) CANONICALIZE+VALIDATE skill AND perk to their on-disk index ids before any check (kills the './tierwire', 'tierwire/', and macOS case-insensitive 'CWS-OBSERVE' bypasses — the FS isdir gate is no longer the name authority); (2) RE-ENFORCE the ACL on the WS step path (re-resolve the LIVE principal + revoked + expires_at on every step_request, not just at claim time) so revocation/TTL actually bound in-flight multi-step runs; (3) make acl_strict ORTHOGONAL to registry presence — under strict an empty/loopback registry is a hard refusal, never an allow-all 'local'; (4) DROP the false 'off-node binding closes the compromised-node residual' claim — acl_sha is signed by the same per-node govd grant key a compromised node controls, so it is wire-tamper-evidence + audit provenance only; a compromised govd node stays in the ACL TCB (consistent with govd already minting plans); (5) RECOMPUTE acl_sha from the LIVE acl fields at allow-time (never trust the operator-supplied spec field) + boot-validate any stored acl_sha; (6) a PRESENT acl with absent/empty `skills` means DENY-ALL (explicit '*' sentinel for all-skills), and the tier ceiling is gated on the DESTRUCTIVE flag + a secret-access dimension so it carries weight before perks are mass-tier-annotated. The ceiling's fail-safe is SELF-OWNED in acl_allows (never inherited from perk_sandbox_tier's opposite-default None) and property-pinned. All anchors re-verified live: govern() pure at govd.py:186 / bare call 886; spec=reg[pid] under if-reg at 866/870; precedence 256; WS hello session-token-only auth at govd.py:967-970 (THE step-path gap); unknown_skill_perk isdir-only gate at govd.py:200 with perk NEVER run through valid_skill_name (registry.py:42); empty-reg pid='local' at govd.py:864-866; perk_sandbox_tier None-on-undeclared/missing at delegate.py:27-48; secret tier plan-derived ('trusted' if creds) at delegate.py:91-96; exod community-no-secrets at exod.py:130; backend_for_tier None->runsc (NOT bwrap) at sandbox.py:293; strongest() floor at exod.py:300/exod.py:145; mint_grant emit-when-set at grants.py:41; exod dual-control issuer!=exod at exod.py:53. Ship Phase A (acl_strict=false, zero re-mint) then Phase B (strict, deny-by-default) as a coordinated operator-chosen flip.

## Data model — `principals.json` ACL

Extend the per-principal spec in principals.json (the SAME sha-keyed dict already holding token_sha/rate/burst/exec_mode; load_principals passes arbitrary keys through verbatim, so the key rides for free) with ONE optional `acl` sub-object. Token VALUES never enter the spec — acl is CANONICAL skill/perk ids and tier LABELS only.

Schema:
"principals": { "agent-1": {
  "token_sha": "<sha256(token)>",            // unchanged identity, never the value
  "rate": 2.0, "burst": 20,                  // unchanged quota
  "exec_mode": "delegated",                  // unchanged per-principal capability precedent
  "acl": {                                   // NEW, OPTIONAL
    "skills":  ["cws-git", "cws-fs"],        // allow-list of CANONICAL skill ids; deny-by-default WHEN acl PRESENT
    "perks":   {"cws-fs": ["read", "stat"]}, // OPTIONAL per-skill perk allow-list; AUTHORITATIVE for a listed skill
    "max_tier": "verified",                  // catalog-tier CEILING (core<verified<community trust order)
    "secrets": false,                        // NEW: may this token claim a credentialed perk? default false
    "issued_at":  1750000000,                // audit
    "expires_at": 1781536000,                // OPTIONAL TTL (bounds compromise window; checked at claim AND step)
    "revoked":    false                      // clean kill (effective next reload OR via the revocation-file hot path)
  }
  // NOTE: acl_sha is NOT stored authoritatively here. govd RECOMPUTES it from the live {skills,perks,max_tier,secrets}
  //       at allow-time and binds THAT into the grant. An optional stored acl_sha is a boot-time self-check ONLY.
}}

Semantics (load-bearing, every review fail-open closed):
- NO `acl` key: scope passed to govern() depends on acl_strict. acl_strict=false (live-fleet default) => unrestricted (exactly today). acl_strict=true => DENY-ALL (treated as empty allow-list). The knob is how the security-maximal end-state and the zero-remint landing co-exist.
- `acl` PRESENT but `skills` ABSENT or [] => DENY-ALL skills (FIX for the partial-acl fail-open: a present acl is deny-by-default). The ONLY way to grant all skills is the explicit sentinel skills:["*"], which the mint helper logs loudly.
- `acl.skills` is a list of CANONICAL skill ids ONLY. The 'skill/perk' pair-form is FORBIDDEN in skills (rejected at mint+boot) — per-perk granularity lives in exactly ONE place, `acl.perks` (kills the two-mechanism footgun + makes acl_sha a stable identity).
- `acl.perks[skill]` present => AUTHORITATIVE for that skill: perk must be in the list. A skill may appear in `perks` WITHOUT appearing in `skills` (its presence in perks grants it, narrowed to the listed perks). A bare skill in `skills` with no `perks[skill]` key => all that skill's perks allowed (a DOCUMENTED, tested decision, not an accidental skip).
- `acl.max_tier` => the claimed perk's DECLARED catalog tier must be <= the ceiling in trust order. SELF-OWNED fail-safe (see tier_semantics): None/unknown declared tier resolves to community (least-trusted) INSIDE acl_allows; unknown ceiling label resolves to core (tightest). Validated against SANDBOX_TIERS at mint+boot so a typo'd ceiling fails the operator at issuance, not silently at runtime.
- DESTRUCTIVE coupling: a perk with destructive:true in perks.json is NEVER admitted by a bare-skill grant — it must be explicitly named in `acl.perks[skill]`. This makes the ACL bite on destructive perks TODAY, independent of the (currently near-empty) tier annotations.
- `acl.secrets` (default false) => a perk whose plan names credential_ids (credentialed) is rejected (acl_secret_denied) unless secrets:true. Closes the secret-axis gap: a low-trust scoped token cannot reach real credentials even though the secret tier is plan-derived downstream.
- `acl.expires_at` and now > expires_at => reject (acl_expired), checked at claim AND on every step_request.
- `acl.revoked: true` => authenticates to nobody on next reload, OR immediately via the optional revocation-file hot path (see issuance_lifecycle).

Tier rank map: a 3-entry dict {core:0, verified:1, community:2} derived from SANDBOX_TIERS=("core","verified","community") at sandbox.py:280, placed NEXT TO the check. It is the catalog-tier TRUST order, DISTINCT from _BACKEND_STRENGTH {bwrap:1,runsc:2}; keep them separate.

orgs.py path: scope resolution is ONE helper resolve_scope(reg, pid) returning the acl from EITHER the flat reg[pid] OR the org-nested {org:{principals:{pid:{...}}}} spec, called at the single govern() call site so org-scoped principals are not silently scope=None. If do_POST does not currently dispatch to orgs.authorize, org-mode ACL is explicitly Phase-2 (stated, not implied-covered).

## Enforcement point

Edits on govern()'s path PLUS the WS step path; govern() stays PURE (scope passed IN as data).

0. CANONICALIZATION at the trust boundary (NEW, the unifying fix for two blockers). Before any check, resolve the presented (skill, perk) to their CANONICAL on-disk index ids:
   - Validate the perk with the SAME single-segment gate as the skill (registry.valid_skill_name): reject '/', '.', '..', whitespace, absolute, trailing sep, altsep.
   - Resolve skill+perk to the real index.json ids via a case-fold-aware lookup ONCE, then REJECT (problem id `noncanonical_name`) any claim whose presented skill/perk is not byte-identical to its canonical id — do NOT silently coerce. The string the ACL/plan/grant sees is then guaranteed to be the string that executes. This kills './tierwire'/'tierwire/' (collapse-tier-to-None) and macOS 'CWS-OBSERVE' (case-insensitive FS resolves but ACL compare is case-sensitive). The FS isdir gate is NO LONGER the name authority.

1. principals.py — a pure helper sibling to authenticate/rate_ok (pinned both-sides by principals_selftest):
   _TIER_RANK = {"core": 0, "verified": 1, "community": 2}   # catalog trust order, NOT _BACKEND_STRENGTH
   def acl_allows(acl, skill, perk, perk_tier, destructive, credentialed, *, now=None, strict=False) -> (ok, problem|None):
     if acl is None: return (False, {"id":"acl_unscoped"}) if strict else (True, None)
     if acl.get("revoked"): return False, {"id":"acl_revoked"}
     if acl.get("expires_at") is not None and now is not None and now > acl["expires_at"]: return False, {"id":"acl_expired","detail":acl["expires_at"]}
     skills = acl.get("skills")
     allowed_skill = (skills == ["*"]) or (skills is not None and skill in skills) or (skill in (acl.get("perks") or {}))
     if not allowed_skill: return False, {"id":"acl_skill_denied","detail":f"{skill}/{perk}"}
     pmap = acl.get("perks") or {}
     if skill in pmap and perk not in pmap[skill]: return False, {"id":"acl_perk_denied","detail":f"{skill}/{perk}"}
     if destructive and not (skill in pmap and perk in pmap[skill]): return False, {"id":"acl_destructive_unlisted","detail":f"{skill}/{perk}"}  # destructive needs explicit perk listing
     if credentialed and not acl.get("secrets"): return False, {"id":"acl_secret_denied","detail":f"{skill}/{perk}"}
     ceiling = acl.get("max_tier")
     if ceiling is not None:
       want = _TIER_RANK.get(perk_tier, 2)   # SELF-OWNED: None/unknown declared tier -> community(2). NOT inherited from perk_sandbox_tier.
       cap  = _TIER_RANK.get(ceiling, 0)     # unknown ceiling -> core(0, tightest); validated at mint/boot so this never fires in practice
       if want > cap: return False, {"id":"acl_tier_denied","detail":{"perk_tier":perk_tier,"max_tier":ceiling}}
     return True, None
   Note acl_allows takes perk_tier/destructive/credentialed as DATA (caller supplies them); its fail-safe is self-contained and does not depend on any external function's None contract.

2. govern() signature + call site:
   - govd.py:186 -> def govern(ledger, cfg, *, scope=None, strict=False, now=None): (defaults preserve every bare caller, the pure selftest, TLC-cache keying).
   - govd.py:886 -> v = govern(ledger, cfg, scope=resolve_scope(reg, pid) if reg else None, strict=cfg.get("acl_strict", False), now=time.time()). EMPTY reg under strict is handled BEFORE this: do_POST refuses (503 'strict mode requires a configured principals registry') so the loopback 'local' principal is NOT an allow-all bypass under strict.

3. ACL gate INSIDE govern(), inserted AFTER the missing_input loop (~line 234) and BEFORE the compose/TLC block (line 237), among the problems[]-appending gates so it NEVER short-circuits (a claim both out-of-scope AND drifted reports both). It runs AFTER the canonical (skill,perk):
   perk_tier   = delegate.perk_sandbox_tier(skill, perk)              # advisory input; acl_allows owns its own fail-safe
   destructive = <already computed at govd.py for the destructive gate>
   credentialed = bool((plan or {}).get("credential_ids"))           # from the blessed plan
   ok, prob = principals.acl_allows(scope, skill, perk, perk_tier, destructive, credentialed, now=now, strict=strict)
   if not ok: problems.append(prob)
   Note acl_* problems are APPENDED (govd.py:256 precedence UNCHANGED): any acl_* => HARD reject. They are NOT routed through needs_approve, so the approve[] echo (line 258, only {perk,'destructive'}) cannot clear them — an out-of-scope claim CANNOT self-approve and push_back is unreachable. record_decision already serializes [p['id'] ...] so all acl_* reasons surface in the monitor with no observability change.

4. WS STEP-PATH re-enforcement (NEW, the claim-time-only blocker fix). In the step_request branch (govd.py ~978), AFTER authorize_step and BEFORE delegation/grant: re-resolve the LIVE principal scope = resolve_scope(reg0, rec0['principal']) and re-call acl_allows(scope, rec0['skill'], rec0['perk'], perk_tier, destructive, credentialed, now=time.time(), strict=cfg.acl_strict). On revoked/expired/out-of-scope => refuse the step (same fail-closed channel as authorize_step refusals). This makes revoked:true and expires_at actually halt an in-flight multi-step run, and re-binds execution authority to the LIVE principal rather than mere possession of the run's session token. (Cheap path: at minimum re-check revoked+expires_at every step; full scope re-check is correct and recommended since the live registry is in-memory.) The same re-check guards step_result in cooperative mode.

COMPOSE-NEVER-WEAKEN: every gate only ADDS a rejection; it cannot relax bad_var_key/plaintext_secret/registry_drift/missing_input/structural/deadlock_tlc.

## Catalog filtering (the enumeration oracle)

PARTIALLY pulled into the MVP (the review showed the open oracle leaks exactly the tier/destructive map an attacker needs, and Phase A may be long-lived). The split:

MVP (any registry-configured govd, does NOT require the strict flag): Bearer-gate AND scope-filter GET /catalog. Reuse principals.authenticate/bearer_of (already in do_POST). Resolve the caller's scope and drop perks the scope would reject (filter against the per-perk 'tier'/'destructive'/'credentialed' fields catalog() already emits at skill_index.py:171), then drop skills whose surviving perk list is empty. No registry (local dev) => unauthenticated full catalog (back-compat). Registry + valid Bearer => filtered to scope. Registry + missing/invalid Bearer => 401. This removes the ENUMERATION ORACLE in Phase A, not just after the strict flip — a narrow token learns nothing about out-of-scope or untiered/destructive perks.

Phase-2 design (reuses the same helper + canonicalization):
- skill_index.catalog(skills_dir=None, *, scope=None, now=None, strict=False) gains an optional scope filter; scope=None => unfiltered (byte-identical to today).
- Do NOT key the shared single-entry _CATALOG_CACHE (govd.py:128-134) per-principal — that would leak across tokens. Filter the cached snapshot per-request (cheap, value-free).
- Under acl_strict=true ALSO Bearer-gate /price and /flow/<skill> so the hidden roster cannot be side-channel-enumerated; /health stays open (no per-skill roster).
- Apply the token-bucket to authenticated GETs too (it is do_POST-only today) so a scoped token cannot recon-by-flooding the now-authenticated /catalog,/price.
HONEST CAVEAT: the enumeration-oracle-closed property holds for registry-configured nodes once the MVP Bearer-gate lands; an UNAUTHENTICATED scan is blocked from the MVP, but a registry-LESS local-dev node serves the full catalog by design.

## Issuance & lifecycle

A token's permissions are bound at MINT time by whoever holds the issuer/operator role (the 0600 principals.json). Today every setup script inlines a single hardcoded quota-only agent-1 behind an `if [ ! -f principals.json ]` idempotency guard (setup-mac-anchor.sh:45 + setup-lightsail-node.sh:77, setup-confined-body.sh:85, setup-confined-body-user.sh:94, body-entrypoint.sh:41). No ACL anywhere.

MINT-WITH-BOUND-PERMS — infra/govern/issue.py mint_token(pid, *, skills=None, perks=None, max_tier=None, secrets=False, ttl=None, rate, burst, exec_mode=None) -> (token_value, spec):
  1. token = secrets.token_urlsafe(32); 2. token_sha = sha256(token) (only the sha stored);
  3. VALIDATE: every skill/perk id is canonical (resolves to a real index id byte-identically); max_tier in SANDBOX_TIERS or None (unknown label is a HARD mint error, not a silent collapse-to-core); reject any 'skill/perk' pair-form in skills.
  4. normalize scope; compute acl_sha = sha256(canonical_json({skills,perks,max_tier,secrets}, sorted, no whitespace)) as a self-check value;
  5. emit spec {token_sha, rate, burst, exec_mode?, acl:{skills,perks,max_tier,secrets,issued_at,expires_at?,revoked:false}} and UPSERT into principals.json under pid (read-modify-write, NEVER clobber sibling principals);
  6. print the token VALUE ONCE to a give-to-agent-then-delete file (today's setup-mac-anchor.sh:48 pattern); the registry keeps only the sha.
This makes 'you cannot create a scoped principal without binding a VALIDATED scope' structural. Dogfood: build a `cws-principal` perk via cws-addperk/cws-create FIRST (it does not exist today — see swarm_playbook acl-08 which is honestly BLOCKED-ON-CONSTRUCTION); until then issue.py ships as plain infra and the dogfood claim is dropped for the mint helper. Setup scripts accept env-driven scope (CWS_AGENT_SKILLS="cws-git,cws-fs" CWS_AGENT_MAX_TIER="verified").

MIGRATION over the EXISTING fleet (the review's idempotency-guard finding): the inline printf is behind `if [ ! -f ]`, so an updated setup script is a silent NO-OP on a deployed node. The SUPPORTED migration path is an explicit `cws-principal upsert <pid> --skills ... --max-tier ... --secrets` (read-modify-write), documented as the fleet step — NOT a setup rerun. The setup scripts, when principals.json exists, PRINT A WARNING that ACL must be added out-of-band rather than silently no-opping. A fleet audit (cws-ledgercheck/principal) reports per node which principals lack an acl, so 'who is still unscoped' is observable.

SEQUENCING:
  Phase A (default acl_strict=false): ship canonicalization + the three govern() edits + the WS step re-check + the MVP catalog Bearer-gate + mint/upsert helper. Every existing quota-only token keeps working byte-identically (absent acl => unrestricted). Operators add `acl` blocks per node at leisure.
  Phase B (later, coordinated, operator-chosen): flip acl_strict=true. Absent-acl => deny-all; an EMPTY/loopback registry is a hard 503, not allow-all; /catalog,/price,/flow Bearer-gated. Every token MUST carry a scope. This is the security-maximal end-state.

RELOAD / REVOCATION: registry is boot-loaded (govd.py:100), no full hot-reload — acl/rotation changes take effect on restart (no live-mutation attack surface). TWO improvements close the revocation-latency gap the review flagged: (a) the WS step-path re-check (above) makes revoked:true / expires_at bound IN-FLIGHT runs as soon as the registry reflects them, not only NEW claims; (b) a lightweight revocation-LIST file (token_sha list) watched and consulted in authenticate() + the step re-check gives reload-INDEPENDENT kill WITHOUT a full restart — a small, safe, revoke-only surface (no capability is granted by the file, only removed). For genuine bounded exposure, recommend mandatory expires_at on delegated-body tokens. ROTATION: re-mint the token VALUE under the SAME pid+scope (token_sha changes; the recomputed acl_sha is stable for the same effective scope).

## Tier semantics

FOUR orthogonal axes; the ACL now touches THREE (authorization-tier, destructive, secret) and leaves confinement untouched.
(A) CATALOG/SANDBOX tier (confinement strength) — core/verified->bwrap, community->runsc (sandbox.py:281). Author-declared in perks.json, read by delegate.perk_sandbox_tier. Selected at exod via strongest(operator_floor, backend_for_tier(declared)) (exod.py:145), a MONOTONE join. CRITICAL CORRECTION to the draft: backend_for_tier maps None/unknown -> RUNSC (the STRONGER box), NOT bwrap (sandbox.py:293 `_TIER_BACKEND.get(tier, "runsc")`). So an undeclared perk is over-confined toward the strongest box, not floor-neutral-lenient. UNTOUCHED by the ACL.
(B) SECRET tier (community|trusted) — minted per-grant from credential PRESENCE in the plan (delegate.py:94 `"trusted" if creds else "community"`); exod refuses secret resolution for a non-trusted grant (exod.py:130). The ACL now ADDS an authorization gate ABOVE this: acl.secrets (default false) decides whether the actor may CLAIM a credentialed perk at all (acl_secret_denied), closing the gap where a community-ceilinged token still reached real credentials because the secret tier is plan-derived not actor-derived.
(C) PER-ACTOR catalog-tier CEILING — an AUTHORIZATION gate in govern(). acl.max_tier vs the perk's DECLARED catalog tier in trust order via _TIER_RANK {core:0,verified:1,community:2}. SELF-OWNED fail-safe (the crux, property-pinned so a future refactor cannot silently unify the None-mappings):
  - declared None/unknown perk tier -> community rank 2 (FAIL-SAFE-STRICT) RESOLVED INSIDE acl_allows, NOT inherited from perk_sandbox_tier (whose None is owned by axis-A's OPPOSITE default). A test directly feeds perk_tier in {None,'core','garbage'} with max_tier='core' asserting None->reject, 'garbage'->reject, only in-range<=ceiling passes; a SEPARATE test pins perk_sandbox_tier's None-on-OSError contract so a future 'default-to-core' robustness refactor breaks a test rather than silently opening every ceiling.
  - unknown ceiling label -> core rank 0 (TIGHTEST) at runtime as defense-in-depth, but VALIDATED at mint+boot so a typo'd max_tier fails the operator at issuance, never silently bricks a token at runtime.
(D) DESTRUCTIVE coupling (NEW) — the ceiling is near-inert today (only cws-release/tierwire declares a tier; every other perk returns None->community, so any non-community max_tier is a near-total lockout while a community ceiling admits everything). So the ACL does NOT lean on the tier ceiling for destructive-perk safety: a destructive:true perk is admitted ONLY when explicitly named in acl.perks[skill] (acl_destructive_unlisted), independent of tier. This makes the ACL bite on the dangerous perks (cws-release/revoke etc.) TODAY. Pair with the v1.2 'high-risk-must-be-core' annotation pass (cws-conform/labeling) as a PREREQUISITE for the ceiling to mean anything graduated; until then the skill/perk allow-list + destructive coupling + secret gate carry the MVP's real enforcement weight and the ceiling is documented as near-all-or-nothing (do not set max_tier below community on the live fleet expecting graduated behavior).
The ceiling/secret/destructive gates NEVER raise confinement — axis-A's strongest() still applies after an allow, so they compose subtractively without weakening the box.

## Floor-monotone invariant (the v1.2 blocker)

PRECISE STATEMENT (the named v1.2 blocker): for every actor scope `acl` and claim (skill,perk), the per-actor policy may only TIGHTEN the claim set and NEVER loosen the core sandbox floor. Two parts:
  (P1 claim-monotone) acl_allows(...)==True IMPLIES bare govern() (no scope) would also have allowed (skill,perk) modulo the acl gate — the ACL is a PURE RESTRICTION on problems[]: it can only ADD a problem, never remove one, never flip a reject to allow.
  (P2 confinement-neutral) for all acl, perk_sandbox_tier(skill,perk) and therefore strongest(operator_floor, backend_for_tier(tier)) at exod is UNCHANGED by the acl — the ACL never feeds backend selection, so it cannot request a weaker box.

HOW ENFORCED (structurally):
1. INTERSECTION-ONLY: the gate is an APPEND to problems[] (govd.py ~235), AFTER the canonicalization reject, unknown_skill_perk (line 200) and the structural/destructive gates — all still run and still reject. An acl naming a nonexistent (or non-canonical) skill is simply ineffective; an acl cannot conjure capability.
2. CEILING/SECRET/DESTRUCTIVE LOWER ONLY: there is no 'raise above core' operation; core (rank 0) is the most permissive grantable and still subjects the run to every other gate. Self-owned fail-safes (None perk tier->community, unknown ceiling->core, secrets default false, destructive needs explicit listing) all fail CLOSED.
3. OFF-NODE the SAME monotonicity holds: exod re-applies strongest() over its OWN backend floor (exod.py:145) regardless of the grant, so a grant can never request a WEAKER box than the floor.

TLC/TEST-CHECKED — the proof must catch CONTENT, not just SHAPE (the draft's single FloorMonotone invariant is trivially true for ANY append-only gate and caught none of the real holes). The obligation (cws-modelcheck/check, TLC not Apalache) extends the governance TLA+ spec with an actor-scope variable and FOUR invariants:
  - FloorMonotone == \A actor,claim: Allowed(actor,claim) => Allowed(unscoped,claim) /\ Confinement(actor,claim)=Confinement(unscoped,claim). (shape)
  - NoUnscopedOpenUnderStrict == strict /\ scope=None => claim rejected. (catches the empty-registry / loopback-'local' allow-all bypass under strict)
  - CeilingFailsClosed == perk_tier \notin KnownTiers => want=community(2) /\ unknown(ceiling) => cap=core(0). (catches the ceiling resolution drift)
  - StepReEnforced == revoked(actor) \/ expired(actor) => no further step executes. (catches the claim-time-only / in-flight-run blocker)
A property test (new tests/test_acl.py, sibling to principals_selftest) asserts P1 over a generated (acl,skill,perk,tier,destructive,credentialed) space; that acl_allows is invariant under FS-equivalent name variants (case, trailing sep, dot-segment) — a name resolving to an in-scope perk's dir but not its canonical id is REJECTED, never admitted; the self-owned tier fail-safes; the destructive-unlisted and secret-denied paths; and P2 (acl_allows never alters perk_sandbox_tier's result). HONEST SCOPE: the TLC model proves the in-process append-only + fail-safe-resolution + step-re-enforcement properties; it does NOT and CANNOT model the compromised-node grant property (there is no independent ACL signer — see delegated_grant_binding), so that is stated as a TCB assumption, not a machine-checked guarantee.

## Backward-compat & migration

Guarantees for shipping over the live fleet (Mac anchor, DGX bodies, runner-agent) with ZERO coordinated re-mint and no Phase-A outage:
1. acl_strict default FALSE: a spec with no `acl` => scope None, strict false => acl_allows returns (True,None). Every existing quota-only token behaves exactly as today. This is the decision that lets enforcement LAND without re-minting. Phase B flips strict=true as a coordinated operator-chosen migration.
2. Registry presence is now ORTHOGONAL to strict (FIX for the loopback-'local' bypass): under acl_strict=FALSE an empty/absent registry runs as 'local' allow-all exactly as today (local-dev contract preserved, pure selftest + local runs never regress). Under acl_strict=TRUE an empty/absent registry is a HARD 503 ('strict mode requires a configured principals registry') — 'local' is NOT minted allow-all, so the Phase-B deny-all end-state cannot be silently voided by simply not configuring a registry. Additionally, load_principals must DISTINGUISH 'file absent' (local dev, {}) from 'file present but empty/unparseable' (a present-but-broken registry FAILS rather than silently emptying to allow-all).
3. govern() gains scope=None/strict=false/now=None defaults => the pure selftest, bare test_govd.py govern(ledger,cfg) callers, and TLC-cache keying are unaffected (behavior byte-identical).
4. Grant/schema: new body fields (acl_sha, skill) are OPTIONAL, emitted ONLY when set (mirroring sandbox_tier at grants.py:41), so legacy grant bodies stay byte-identical; grant.schema.json declares acl_sha (^[0-9a-f]{64}$) and skill (string) as optional properties so additionalProperties is satisfied; verify_grant gates are opt-in (expect_*=None). additionalProperties:false is NOT runtime-enforced (exod reads gbody.get directly), so the L3 path is genuinely incremental.
5. /catalog: the MVP Bearer-gate (catalog_filtering) DOES change the discovery contract for registry-configured nodes — discovery tests are UPDATED to send a Bearer when a registry is present and assert the scoped roster; registry-LESS local-dev discovery tests stay green unchanged. (This is a deliberate departure from the draft, which deferred all catalog work; the review showed deferral leaves the oracle open through an indefinite Phase A.)

NEW observable behavior in Phase A: (a) a principal WITH an acl excluding the claimed skill/tier/destructive-perk/secret returns reject with an acl_* problem (dormant until an operator opts a token in); (b) a registry-configured /catalog now requires a Bearer and returns a scope-filtered roster; (c) an in-flight run whose token is revoked/expired halts at the next step. Tests are ADDITIONS plus the discovery-contract update: extend principals_selftest with acl_allows cases (no-acl unrestricted under strict=false; deny-all under strict=true; present-acl-absent-skills => deny-all; '*' sentinel; skill in/out; perk authoritative; bare-skill-all-perks documented; destructive-unlisted; secret-denied; tier under/over with self-owned None->community + unknown-ceiling->core; expired; revoked; canonicalization rejects of './x','x/','CASE'); a test_govd.py case threading scope + the WS-step re-check (revoked mid-run halts); an empty-registry-under-strict 503; a grant round-trip pinning acl_sha optionality + recompute-from-live equality. Per ci-merge-discipline (enforcement surface): run FULL pytest + FULL selfmonitor (not --no-mutation); per review-before-merge-discipline, COMMIT first then run the multi-agent adversarial review (subagents git-revert the submodule).

## Delegated-grant binding (honest TCB scope)

Bind the actor scope into the DSSE grant for WIRE-TAMPER-EVIDENCE and AUDIT PROVENANCE — and state HONESTLY what it does and does NOT defend, correcting the draft's overclaim.

WHAT IT IS NOT (the blocker correction): acl_sha and the bound skill are signed by the SAME per-node govd grant key that a compromised node controls (delegate.execute_step is the single mint site, delegate.py:92; the node holds grant_key). exod verifies the signature FIRST (grantverify.py:49) and that signature is VALID — it is govd's real key. exod's dual-control (exod.py:53, issuer-keyid != exod-keyid) only ensures two DIFFERENT keys exist; it does NOT give exod an independent copy of the actor's ACL. So a compromised govd node CAN mint a grant for any skill/acl_sha it likes and exod honors it. Therefore: a compromised govd node REMAINS in the TCB for ACL enforcement — consistent with the existing model where govd is already trusted to mint plans. The draft's 'a compromised node cannot mint a widened grant' is STRUCK. acl_sha-in-grant defends against a MITM on the govd->exod wire (which DSSE already covered for run_id/plan_sha) and gives tamper-evident audit provenance; it is NOT enforcement against a compromised issuer. (A genuinely-independent defense would need a SEPARATE authority — the operator who owns principals.json — to sign an actor->ACL attestation pinned in exod's config under three-way dual-control attestation-issuer != grant-issuer != exod; that is listed as an open decision, not claimed as shipped.)

WHAT IT IS (kept, with the freshness fix):
- acl_sha is RECOMPUTED by govd from the LIVE acl fields at allow-time (sha256 of canonical {skills,perks,max_tier,secrets}), NOT read from the operator-supplied spec field (FIX for the certify-a-phantom-policy hole). The operator-supplied stored acl_sha is an OPTIONAL boot-time self-check ONLY: if present and != canonical_sha(live fields), refuse to LOAD that principal (acl_sha_mismatch) so a hand-edited block with a stale digest fails loudly.
- At allow-time govd attaches the recomputed acl_sha and the canonical bound `skill` onto the run record (govd.py:902, beside `principal`). To defeat the stale-record-across-restart attack the review found (disk record survives a restart carrying the OLD acl_sha while exec_mode/principal are re-read live), STAMP a registry epoch (sha over the loaded registry) on each allow-record AND on the live registry; on any in-flight delegated step, if live-epoch != record-epoch, re-resolve the LIVE acl, recompute acl_sha, and re-derive grant scope from the live acl (fail-closed if no longer permitted) — this is the same WS-step re-check as enforcement_point #4 applied to the delegated leg.
- delegate.execute_step passes acl_sha=rec.get('acl_sha'), skill=rec.get('skill') into grants.mint_grant.
- grants.mint_grant gains optional acl_sha, skill kwargs emitted ONLY when set (the grants.py:41 pattern). grant.schema.json adds acl_sha (^[0-9a-f]{64}$) and skill (string), optional; required unchanged.
- grantverify.verify_grant gains opt-in expect_acl_sha=None, expect_skill=None (mirroring expect_run_id/expect_plan_sha). Signature checked FIRST. Mismatch => (False,"acl_mismatch")/(False,"wrong_skill").
- exod.run_step pins the request's canonical skill against the grant's signed skill/acl_sha; outside the signed scope => refuse() (the fail-closed channel).

DELEGATED-MODE SCOPE: this off-node binding exists ONLY in delegated mode (exec_mode is per-principal, govd.py:984). In cooperative mode there is no exod, no grant, no acl_sha — the ACL lived only in govern() + the WS step re-check on the (trusted) node. State precisely: off-node tamper-EVIDENCE applies to delegated runs only; a cooperative-mode node is trusted for its own claims. RECOMMENDATION: forbid cooperative mode for any principal whose acl is non-trivial (an ACL'd token implies you don't fully trust it, which implies you want exod re-enforcement). Surface acl_sha on /health and every record_decision entry for the drift detector.

## New reject reasons

`noncanonical_name`, `acl_skill_denied`, `acl_perk_denied`, `acl_destructive_unlisted`, `acl_secret_denied`, `acl_tier_denied`, `acl_unscoped`, `acl_expired`, `acl_revoked`, `acl_sha_mismatch`, `acl_mismatch`, `wrong_skill`

## Security properties

- Least-privilege claim boundary (PROVABLE): an authenticated token may CLAIM only skills/perks in its allow-list (deny-by-default when acl present; '*' sentinel for all), only perks at/below acl.max_tier, never a destructive perk unless explicitly perk-listed, and never a credentialed perk unless acl.secrets — a compromised/over-broad token is bounded at the claim boundary (govern() hard reject) AND re-checked on every step.
- Canonical-name integrity (PROVABLE): skill AND perk are validated and resolved to their byte-identical on-disk index ids before any check; a non-canonical name (./x, x/, CASE-variant on a case-insensitive FS) is REJECTED, so the string the ACL/plan/grant sees is exactly the string that executes — closes the perk-divergence and macOS case bypasses.
- Step-bound revocation (PROVABLE): revoked:true and expires_at are re-checked on the WS step path, so an in-flight multi-step run HALTS at the next step when the token is revoked/expired — not merely blocked from NEW claims. With the optional revocation-file hot path, this is reload-independent.
- Non-self-approvable (PROVABLE): acl_* problems are APPENDED to problems[] (not routed through needs_approve), so an out-of-scope claim cannot be cleared by approve[] and can never reach the approvable push_back verdict (govd.py:256-258).
- Compose-never-weaken / floor-monotone (MACHINE-CHECKED in-process): the gate only ADDS a rejection and never feeds backend selection; proven by the property test (acl_allows==True => unscoped govern allowed) and the TLA+ FloorMonotone + CeilingFailsClosed + NoUnscopedOpenUnderStrict + StepReEnforced invariants under TLC.
- Self-owned fail-safe authorization (PROVABLE): the tier ceiling's None->community and unknown-ceiling->core resolutions live INSIDE acl_allows and are property-pinned, NOT inherited from perk_sandbox_tier's opposite default — a future robustness refactor of that function breaks a test rather than silently opening every ceiling.
- Secret-axis bounded (PROVABLE): acl.secrets (default false) gates whether a token may claim a credentialed perk, so a low-trust scoped token cannot reach real credentials even though the secret tier is plan-derived downstream.
- Strict-mode has no registry-absence escape (PROVABLE): under acl_strict=true an empty/loopback registry is a hard 503, and absent-acl is deny-all — the Phase-B end-state cannot be voided by failing to configure a registry.
- Value-free preserved (PROVABLE): acl carries only canonical skill/perk ids and tier labels; acl_sha is a digest over names/labels recomputed from live fields; token VALUES never enter the registry, ledger, or grant.
- Off-node tamper-EVIDENCE (PROVABLE, narrow): acl_sha + bound skill are signed into the DSSE grant and re-verified by exod, giving wire-tamper-evidence and audit provenance for delegated runs. (DESIGN/TCB, NOT a guarantee: a COMPROMISED govd NODE remains trusted for ACL enforcement because it holds the grant key and exod has no independent ACL authority — closing this needs a separate operator-signed ACL attestation, an open decision.)
- Enumeration-oracle closed for configured nodes (PROVABLE once MVP catalog gate lands): Bearer-gated, scope-filtered /catalog means a narrow token cannot recon out-of-scope/untiered/destructive perks; registry-less local-dev still serves the full catalog by design.

## The cws-pm swarm (build + govern)

| # | task_id | skill/perk | redeem | gates |
|---|---|---|---|---|
| 1 | `acl-01-schema-conform` | `cws-conform/schemas` | False | the new acl spec schema + optional grant body fields are well-formed, labeled, and cross-language-consistent before code is written (design  |
| 2 | `acl-02-tier-annotate` | `cws-conform/labeling` | False | the PREREQUISITE tier-annotation pass — until perks declare tiers the ceiling is near-all-or-nothing; labels the high-risk perks core so a l |
| 3 | `acl-03-modelcheck-floor` | `cws-modelcheck/check` | True | the floor-monotone BLOCKER plus the three content invariants the bare shape-only invariant misses (strict-no-registry-open, ceiling-fail-clo |
| 4 | `acl-04-implement-qc` | `py_qc/test` | True | the enforcement spine + step re-check + L3 binding pass full pytest (extended principals_selftest + tests/test_acl.py property tests) and li |
| 5 | `acl-05-mutate-enforce` | `cws-mutate/mutate` | True | a flipped comparison or dropped problem-append must be killed — especially the `skill in pmap` skip branch and the self-owned None->communit |
| 6 | `acl-06-redteam-bypass` | `cws-redteam-sw/rt-grant-forged` | True | adversarial proof there is NO reachable bypass of the claim gate, the step re-check, the canonical-name gate, or the off-node acl_sha check. |
| 7 | `acl-07-sec-scan` | `sec/secrets` | False | no secret/token leakage in the new issuance path; sha-only + value-free upheld by static scan. Real perks: sec/secrets + sec/audit. |
| 8 | `acl-08-create-principal-perk` | `cws-addperk/apply` | False | honestly builds the missing dogfood perk FIRST (cws-principal) so issuance runs through a governed skill; until built, issue.py ships as pla |
| 9 | `acl-09-codebaseqc` | `codebaseqc/audit` | False | every new function is used per contract, scope is threaded at all call sites (incl. the step path the draft missed), no dead/under-tested en |
| 10 | `acl-10-ledgercheck` | `cws-ledgercheck/principal` | False | acl_sha + acl_* decision entries are recorded with integrity, and the per-node 'who is still unscoped' migration audit is produced. Real per |
| 11 | `acl-11-chaos` | `cws-chaos/drill` | False | the ACL holds under reload/TTL/revocation/restart chaos — proves the step re-check + registry-epoch stamp halt an in-flight or stale-record  |
| 12 | `acl-12-release` | `cws-release/sign` | True | the enforcement-surface change is signed, transparency-logged, and manifest-linted. Real perks: cws-release/sign + transparency + manifestli |
| 13 | `acl-13-observe` | `cws-observe/redeem` | False | tracks redemption of the gating perks and confirms acl_sha is surfaced on /health for the drift detector. Real perks: cws-observe/redeem + s |

## Open decisions (your call)

1. INDEPENDENT ACL ATTESTATION (the only honest path to the compromised-node property): ship acl_sha-in-grant as wire-tamper-evidence + audit only (compromised govd node stays in the ACL TCB, consistent with it already minting plans) — OR add a SEPARATE operator-signed actor->ACL attestation (DSSE keyed to token_sha/pid) pinned in exod's config so exod verifies under three-way dual-control (attestation-issuer != grant-issuer != exod). The latter is the only way a node editing its own principals.json fails; it is real work (a second signer + key distribution to exod) and is NOT in the MVP. User decides whether the compromised-node residual is in scope.
2. DEFAULT-DENY vs DEFAULT-OPEN steady state: ship Phase A default-OPEN (absent acl => unrestricted, zero re-mint) and flip acl_strict=true later as a coordinated migration — OR bite the breaking change now and mint every token deny-by-default. Recommendation: knob + two-phase flip; user decides when (or whether) Phase B lands.
3. REVOCATION HOT PATH: accept reload-bounded revocation augmented only by the WS step re-check + expires_at — OR add the watched revocation-LIST file (token_sha) for genuinely reload-independent kill without a full restart. Recommendation: ship the step re-check now (bounds in-flight runs); add the revocation-file if the fleet needs sub-restart kill latency.
4. MANDATORY TTL on delegated-body tokens: make expires_at required for delegated tokens (bounded compromise window, stronger revocation) — OR keep it operator-opt-in everywhere. Recommendation: optional now, strongly consider mandatory for delegated bodies.
5. COOPERATIVE MODE WITH AN ACL: allow an ACL'd token to run cooperative (ACL enforced only by the trusted node's govern + step re-check) — OR forbid cooperative mode for any non-trivial acl so exod re-enforcement is mandatory (an ACL'd token implies reduced trust). Recommendation: forbid cooperative for ACL'd tokens.
6. TIER-ANNOTATION TIMING: ship the high-risk-must-be-core labeling pass (acl-02) as a hard PREREQUISITE so the ceiling discriminates before anyone sets max_tier — OR ship the ceiling latent and lean on the skill/perk allow-list + destructive coupling + secret gate for the MVP. Recommendation: do the labeling pass first; until then document max_tier below community as near-total-deny.
7. ORGS NESTING: ship the flat resolve_scope hook now and treat orgs.py nesting (org-isolation + SPIFFE) as a follow-on reusing the identical acl schema — OR adopt org-nesting immediately. Note do_POST must actually dispatch to orgs.authorize for org-mode ACL to bind; if it does not today, org-mode ACL is explicitly Phase-2. Recommendation: flat now, org-nesting reuses the same block.
8. ATOMIC vs ROLLING FLEET MIGRATION: re-scope all five node types (mac-anchor, lightsail, edge, confined-body x2, runner-agent) in one window — OR roll node-by-node under default-open via cws-principal upsert (the setup-script idempotency guard makes a rerun a no-op, so upsert is the only safe path). Recommendation: rolling, default-open makes it safe.


---

# Locked decisions (this session)

1. **Rollout = two-phase.** Phase A `acl_strict=false` (absent-acl unrestricted, zero re-mint); flip `acl_strict=true` later as a coordinated migration. **Gate the hard flip on M2, not M1** — flipping on the ceiling alone advertises escalation-resistance the code lacks.
2. **Compromised node = operator-signed attestation (+ client proof).** Not audit-only. See the attestation subsystem below.
3. **Forbid cooperative mode for any ACL-bearing token** — enforced **client-side** (the forbid rule in govd's TCB is ignorable by a compromised govd; the brain must refuse cooperative for ACL tokens, and the attestation marks `delegated_required`).

# Milestones (the attestation design reframes this as THREE, not two)

- **M0 — base ACL (prerequisite, UNBUILT today):** `principals.acl` block + pure `acl_allows` appended to `govern()` + WS step re-check + `acl_sha` recomputed from live fields. `grep` confirms zero `acl_allows`/`acl_sha`/`acl_strict` in `infra/` — this must land first.
- **M1 — operator attestation (the ceiling):** a third operator ACL-issuer key (private half off-body) signs a DSSE actor→ACL attestation; exod pins the operator pub, three-way dual-control (acl-issuer ≠ grant-issuer ≠ exod), and **re-runs `acl_allows`** so govd cannot *widen* a token. **Does not meet the goal alone** — a compromised govd can substitute a higher-privileged principal's attestation (union ceiling = escalation).
- **M2 — client token-possession proof (the binding):** an independent client-generated key (NOT HKDF-from-bearer — govd already holds the bearer) signs a per-(run,plan,step) proof; exod welds grant+attestation+proof so a run executes only under the ACL of the token that *actually holds it*. Closes misattribution.

# Operator-signed ACL attestation — Operator-signed ACL attestation + client token-possession proof: the final design (M0 base-ACL prereq, then ceiling, then binding)

FINAL design folds both proposals + every red-team blocker/major, verified against live code at HEAD 40cfb50 (root tree; submodule skillChip @ 7158635). Two independent Ed25519-signed DSSE envelopes ride verbatim alongside the existing govd-minted grant: (A) an OPERATOR ACL attestation (third key, private half off-body) that lets exod re-enforce each actor's ceiling so a compromised govd cannot WIDEN a token; and (B) a CLIENT token-possession proof that BINDS a run to the token that actually holds it, closing govd-driven misattribution. Both red-teams independently confirmed three blockers I verified directly: (1) the 'base ACL design' both proposals extend is UNBUILT — grep finds zero acl_allows/acl_sha/acl_strict/acl-block anywhere in infra/, and grants.mint_grant (grants.py:38-40) signs only {run_id,plan_sha,snippet_shas,capabilities,credentials,tier,nbf,exp,nonce[,sandbox_tier]} with NO skill/perk/acl_sha; principals.py knows only {token_sha,rate,burst}. So this is THREE milestones, not two: M0 base ACL (prerequisite), M1 operator attestation (ceiling), M2 client possession proof (binding). (2) Proposal 1 standalone does NOT meet the goal: with multiple attestations a compromised govd substitutes a more-privileged principal's attestation (it freely picks rec['principal'] at govd.py:902) and the effective ceiling becomes the UNION of all attested ACLs, not the actor's own — that is escalation, not DoS, so acl_strict must NOT hard-flip on the ceiling alone. (3) The proof key must NOT be HKDF-derived from the bearer token: govd receives the live bearer on every /govern POST (govd.py:867) and would already hold it, so HKDF-from-token is forgeable by the exact adversary — the proof key is an INDEPENDENT client-generated key whose public half the client registers with the operator. Additional folded fixes: pid+token_sha folded INTO the acl_sha preimage (else same-ACL actors' attestations are interchangeable); proof bound to (run_id,plan_sha,STEP) with an exod-side per-(token_sha,run_id,step) NonceCache (kills the delegate.py:83 nonce-ordering hole and replay-within-run); degenerate-proof_pubkey guard (sign.verify ignores keyid, sign.py:65); three-way dual-control asserted WHENEVER acl-issuer pub is set (both phases); minutes-TTL attestation exp as the load-bearing revocation bound with a monotonic-floor denylist read off the read-only mount (govd-relayed denylist is suppressible within TTL); cooperative-downgrade closed CLIENT-side (the forbid-cooperative rule lives in govd's TCB at govd.py:984, so a compromised govd ignores it). HONEST RESIDUAL kept split exactly along what each weld proves.

## Attestation schema (two DSSE envelopes)

TWO independent DSSE envelopes (infra/cwp/sign.py shape {payload(b64 canonical body), payloadType, signatures:[{keyid,sig}]}), both relayed verbatim by govd which holds NEITHER private key.

(A) OPERATOR ACL ATTESTATION — payloadType "application/vnd.cyberware.acl-attestation+json" (new sibling of GRANT_TYPE). Signed by the operator ACL-issuer key over canonical body (JCS via infra/cwp/canonical.py, the SAME canonicalization sign.py PAE uses):
{
  "pid":           "<principal id matching principals.json key>",
  "token_sha":     "<sha256(token)>",                 # the SAME value principals.py:18-19 stores
  "proof_pubkey":  "<raw32 b64 of the CLIENT-registered proof public key>",   # M2; independent key, NOT HKDF-from-token (RED-TEAM 2-major3 / B-major)
  "acl_sha":       "<sha256(canonical {pid, token_sha, skills, perks, max_tier, secrets})>",   # pid+token_sha FOLDED IN (RED-TEAM 1-major4) so same-ACL actors are NOT interchangeable
  "skills":        ["<canonical skill id>" | "*"],
  "perks":         {"<skill>": ["<perk id>" | "*"]},
  "max_tier":      "community" | "verified" | "core",
  "secrets":       ["<credential id>", ...],
  "nbf":           <int unix s>,
  "exp":           <int unix s>,                       # MINUTES-to-hours, NOT days (RED-TEAM 2-major5): exp is the load-bearing revocation bound
  "attestation_id":"<ulid>"                            # revocation-list key
}
NO "revoked" field is trusted from the body (an attacker relays an old revoked=false). exod RE-DERIVES acl_sha from the body's own {pid,token_sha,skills,perks,max_tier,secrets} and checks ==body.acl_sha AND ==grant.acl_sha — acl_sha is a self-consistency + join check, never trusted on faith.

(B) CLIENT TOKEN-POSSESSION PROOF — payloadType "application/vnd.cyberware.token-proof+json". Signed by the CLIENT's independent proof private key (the one whose public half is in (A).proof_pubkey) over canonical body:
{
  "run_id":    "<run_id>",
  "plan_sha":  "<plan_sha>",
  "step":      "<step id>",          # STEP included + exod asserts proof.step==grant.step (RED-TEAM 2-blocker1: replay-within-run was open)
  "token_sha": "<sha256(token)>",    # must ==attestation.token_sha
  "ts":        <int unix s>
}
The proof binds to client-known values (run_id,plan_sha,step) that the brain has at step-send time — NO dependence on govd's grant nonce (which is minted inside delegate.execute_step at delegate.py:83 AFTER the step arrives, so the client cannot sign over it without a govd-controlled round trip — RED-TEAM 2-blocker1 / B-major4). exod gives the proof its OWN per-(token_sha,run_id,step) NonceCache for single-use, independent of the grant nonce.

THE JOIN exod enforces: attestation.acl_sha==grant.acl_sha (govd recomputes from live principals.json incl pid+token_sha); proof verified by attestation.proof_pubkey; proof.token_sha==attestation.token_sha; proof.run_id/plan_sha/step == grant's. The grant supplies run-binding+nonce; the attestation supplies ceiling+proof_pubkey (actor-bound); the proof supplies "the holder of THIS token opened THIS step."

## Issuance (three keys, three issuers)

THREE issuers, three keys, deliberately separated — verified distinct in live code (grant.key/exod.key minted on the body at deploy/setup-confined-body.sh:60-76; principals.py stores token_sha only):

1. OPERATOR ACL-ISSUER KEY (the third key) — owned by whoever owns principals.json (human/role operator), private half lives ENTIRELY off every body (offline/HSM, same custody root as principals.json). Signs attestation (A). NEW operator-side tool `infra/govern/issue.py` (alias `cws acl-attest <pid>`): reads principals.json + the operator key, recomputes acl_sha = sha256(canonical {pid, token_sha, skills, perks, max_tier, secrets}) the SAME way govd will at allow-time, reads that principal's CLIENT-registered proof_pubkey (see #3), and emits one signed envelope per non-trivial-ACL principal. Re-issued whenever that principal's acl block changes or its window lapses — slow-changing, per-actor, NOT per-run. exp set to MINUTES-to-hours for privileged actors (it is the load-bearing revocation bound). This tool is explicitly NOT run by govd and the key is NOT minted by setup-confined-body.sh:60-76 (which mints grant+exod only).

2. GOVD GRANT KEY — unchanged (delegate.py:92 grants.mint_grant with grant_key; per-node, deploy-minted). M0 ADDS: delegate.execute_step stamps grant.acl_sha (recomputed from live principals.json incl pid+token_sha) + the canonical skill/perk/destructive/credentialed claims into the grant body. A compromised govd can mint grants but CANNOT forge (A) or (B).

3. CLIENT PROOF KEY (M2) — an INDEPENDENT Ed25519 keypair generated by the brain/client, NOT derived from the bearer (RED-TEAM: HKDF-from-token is forgeable because govd already receives the live bearer at govd.py:867). At provisioning the client registers proof_pubkey with the operator (out-of-band, alongside choosing its token) so the operator signs over a client-supplied pubkey it never needs the cleartext token to derive — this preserves the principals.py "sha-only, token VALUES never enter the registry" invariant and survives token rotation. The proof private key stays with the client; govd only ever relays the signed (B) envelope, never holds the key.

acl_strict TWO-PHASE (locked decision 1): phase 1 (acl_strict=false) exod VERIFIES any attestation/proof handed to it and emits a signed "acl:audit_would_refuse"/"proof:audit_would_refuse" advisory but does NOT block; govd's own govern()/WS acl_allows is the only hard gate. Flip to acl_strict=true (exod flag --acl-strict / EXOD_ACL_STRICT) makes every failure a hard refuse. CRITICAL (RED-TEAM 1-blocker3 / 2-blocker2): do NOT flip on the CEILING (M1) alone — that advertises escalation-resistance the code lacks while attestation substitution is still open. Gate the hard flip on M2 (possession proof) landing.

## Distribution

RIDES THE GRANT-DELIVERY PATH, NOT THE GRANT BODY — the grant stays SINGLE-signed by govd's grant_key (govd must never co-hold the operator or client key).

ATTESTATION (A): pre-distributed, per-principal, long-lived. Published to the read-only NAS gallery the bodies already mount (source-distribution memory) — public-verifiable, safe to distribute openly because forging needs the operator private key. At delegated step-time govd reads rec['principal'] (govd.py:984) and RELAYS the matching attestation verbatim as a NEW top-level field req["attestation"] in delegate.execute_step (alongside req["grant"], delegate.py:97). govd cannot forge it; at worst it relays the WRONG principal's attestation — exactly the misattribution the proof closes.

CLIENT PROOF (B): ORIGINATES at the brain, carried opaquely through govd. The client signs (B) over (run_id, plan_sha, step) — all four known at step-send time, NONE requiring a govd echo (this deletes Proposal 2's nonce-echo round trip AND the delegate.py:83 nonce-ordering hole). The agent attaches the signed proof envelope to the WS step message; govd does NOT inspect/sign it and copies it verbatim into req["token_proof"] in delegate.execute_step (delegate.py:97). govd can neither forge a proof for a token whose proof key it lacks nor replay a stale proof (exod's per-(token_sha,run_id,step) NonceCache rejects reuse).

grant.acl_sha JOIN: delegate.execute_step sets the grant body's acl_sha (M0) to the SAME acl_sha govd recomputes from live principals.json incl pid+token_sha — so grant.acl_sha and attestation.acl_sha agree iff govd attached the right, current attestation.

OPERATOR PUB PINNING in exod: add --acl-issuer-pub / EXOD_ACL_ISSUER_PUB to exod.main (sibling of --issuer-pub), load raw 32 bytes, pass acl_issuer_pub= into Exod.__init__, store self._acl_issuer_pub. The proof_pubkey is NOT pinned globally — it travels inside each operator-signed attestation, so trusting it reduces to trusting the pinned operator key.

DEPLOY: the acl-issuer key is the ONE key the body deploy must NOT mint. Only its PUBLIC half ships to the body at $CW_KEYS/acl-issuer.pub (operator scp or pulled from the verified read-only NAS gallery). The keygen block (setup-confined-body.sh:60-76) stays grant+exod only. Add an ORDERED provisioning step (RED-TEAM 2-minor7): REQUIRE $CW_KEYS/acl-issuer.pub present AND assert its keyid distinct from grant.pub AND exod.pub (mirror the line-70 assert as a three-way check) BEFORE enabling --acl-strict, so a swapped/colliding acl-issuer.pub is caught at deploy and a --acl-strict body is never left non-bootable with no guidance. The exod systemd unit (setup-confined-body.sh:120) gains --acl-issuer-pub $CW_KEYS/acl-issuer.pub (and --acl-strict at phase 2). govd.json is UNCHANGED in trust — govd never receives the acl-issuer or client proof private key.

THREE-WAY DUAL-CONTROL: extend the 2-way assert at exod.py:53 to require _principal(acl_issuer_pub), _principal(grant_issuer_pub), _principal(self._sk.public_key()) PAIRWISE distinct. Run this WHENEVER acl_issuer_pub is provided, in BOTH phases (RED-TEAM 1-minor) — else phase-1 verify-and-log could verify attestations against a govd-controlled key and produce falsely-reassuring logs.

## exod verification (step 1b, fail-closed, signature-first)

A new step "1b" in Exod.run_step, slotted BETWEEN grant-OK (exod.py:98-101) and capability (exod.py:104), BEFORE the grant nonce is spent (exod.py:116) so an ACL/proof deny NEVER burns a valid grant. Every deny rides the existing refuse(tag) closure (exod.py:93-95) — a signed "refused" step-result on exod's channel, recorded by govd as a delegation-refused event, auditable for free, retryable. Under acl_strict=false the block AUDITS (emits "acl:audit_would_refuse"/"proof:audit_would_refuse" and proceeds); under true it hard-refuses.

A new verifier file infra/exec/aclverify.py (its own prose-clean mutation target, sibling of grantverify.py). All checks fail-CLOSED, signature-FIRST (mirroring grantverify.py:49):

1. GRANT authenticity (existing, exod.py:98-101) — verify_grant(self._issuer_pub, req["grant"], expect_run_id, expect_plan_sha). Unchanged.

2. THREE-WAY dual-control (construction, exod.py:53) — acl-issuer != grant-issuer != exod, pairwise.

3. ATTESTATION authenticity (verify_acl_attestation, sibling of verify_grant): sign.verify(req["attestation"], self._acl_issuer_pub) FIRST -> else "acl:bad_signature"; payloadType==ACL_ATTESTATION_TYPE; nbf/exp ±DEFAULT_SKEW (the same ±60s as grantverify.py:55-59) -> "acl:expired"/"acl:not_yet_valid".

4. acl_sha RE-DERIVE + JOIN: recompute acl_sha from the attestation body's OWN {pid,token_sha,skills,perks,max_tier,secrets}; require ==body.acl_sha (-> "acl:acl_sha_mismatch") AND ==grant_body.acl_sha (-> "acl:acl_join_mismatch"). exod trusts no acl_sha it did not recompute.

5. RE-RUN acl_allows (the SAME pure principals.acl_allows M0 appends to govern()): acl_allows({skills,perks,max_tier,secrets from the ATTESTATION body}, skill=gbody["skill"], perk=gbody["perk"], perk_tier=gbody.get("sandbox_tier"), destructive=gbody.get("destructive"), credentialed=bool(gbody.get("credentials"))). On deny -> refuse("acl:"+reason) e.g. acl:skill_not_allowed / acl:tier_exceeds_max. Credentials cross-check: every id in grant.credentials MUST be a subset of attestation.secrets -> else acl:secret_not_allowed. exod does NOT trust govd's allow; it independently NARROWS against the operator-attested ACL.

6. CLIENT POSSESSION PROOF (M2 — closes misattribution): verify req["token_proof"]:
   a. DEGENERATE-PUBKEY GUARD (RED-TEAM 1-major / B-major6): reject "proof:degenerate_pubkey" if attestation.proof_pubkey equals any of {grant_issuer_pub, acl_issuer_pub, exod pub} — sign.verify (sign.py:65) ignores keyid, so a proof_pubkey set to grant_issuer_pub would let govd (holding grant_key) sign a valid 'proof'.
   b. sign.verify(req["token_proof"], proof_pubkey-from-the-verified-attestation) -> "proof:bad_signature"; payloadType==TOKEN_PROOF_TYPE.
   c. proof.token_sha == attestation.token_sha -> "proof:token_mismatch" (load-bearing: a valid proof means the signer held the key the operator bound to THIS token_sha).
   d. proof.run_id==grant.run_id AND proof.plan_sha==grant.plan_sha AND proof.step==grant.step==req.step -> "proof:wrong_step" (STEP equality added — RED-TEAM 2-blocker1 left replay-within-run open).
   e. exod-side per-(token_sha, run_id, step) NonceCache single-use spend -> "proof:replay" (independent of the grant nonce; a captured proof is not reusable across runs/steps and govd cannot lift T's proof onto a P-attestation).
   f. (optional) |now - proof.ts| <= skew.

7. ONLY after 1-6: spend the grant nonce (exod.py:116) and proceed (capability exod.py:104, closure exod.py:113, secret/sandbox tiers).

REVOCATION (step 1b add): refuse "acl:revoked" if attestation.attestation_id is in a currently-valid denylist loaded from the READ-ONLY mount $CW_KEYS/acl-revoked.json (NOT govd-relayed — RED-TEAM 2-major5), verified under the pinned operator key, with a persisted monotonic issued-at floor exod ratchets so a body cannot roll back to a pre-revocation list.

## Misattribution handling (what each weld proves)

SPLIT EXACTLY along what each weld proves — the line both red-teams demanded.

CLOSED BY (A) ALONE (the ceiling, M1): a compromised govd holds grant_key (delegate.py:92, can mint any grant) but NOT the operator key, so for a token T whose attestation it relays exod independently RE-RUNS acl_allows and refuses any skill/perk/tier/secret outside T's operator-attested ACL. govd cannot WIDEN T's own attestation. BUT — and this is the honest correction both red-teams forced — (A) ALONE does NOT meet the goal in the normal MULTI-attestation case: govd freely chooses rec['principal'] (govd.py:902) and which attestation file to relay, so it can take a T-authenticated run and attach a more-privileged P's attestation + a grant whose acl_sha it recomputes from P's real principals.json fields. Every check 1-5 passes; the effective ceiling becomes the UNION of all attested ACLs, not the actor's own. That is escalation, not DoS. Folding pid+token_sha into the acl_sha preimage stops same-ACL actors being interchangeable and forces a deliberate grant rewrite, but does NOT bind the run to the token. Therefore M1 must NOT hard-flip acl_strict.

CLOSED BY (A)+(B) (the binding, M2): exod requires a self-consistent TRIPLE (grant, attestation, proof) cryptographically welded — attestation.acl_sha==grant.acl_sha; proof verified by attestation.proof_pubkey; proof.token_sha==attestation.token_sha; proof.run_id/plan_sha/step==grant's; proof single-use in exod's NonceCache. To run T's run under P's ACL govd must produce a proof signed by P's INDEPENDENT proof private key over THIS step — it does not hold that key (it is client-held, NOT HKDF-from-bearer, so receiving the bearer at govd.py:867 does not yield it), so the only proof it can relay is the real client's, which carries token_sha(T) and fails step 6c against P's attestation. Omitting the proof fails 6b; reusing any proof fails 6e. The run<->token edge moves OUT of govd's TCB.

THE COOPERATIVE-DOWNGRADE HOLE (RED-TEAM 2-major6, verified at govd.py:984/1040): exec_mode is selected per-principal by the SAME compromised govd we defend against. It can mark an ACL-bearing run "cooperative", skip delegate.execute_step entirely, and self-report — no exod in the loop. The forbid-cooperative rule (locked decision 3) lives in govd's TCB and a compromised govd ignores it. FIX: enforce the floor CLIENT-side — the brain refuses to run cooperatively for any ACL-bearing token, and the operator attestation marks the actor delegated-required so a cooperative self-report is unattested. Without this client-side floor, the ceiling claim has a cooperative-downgrade escape inside govd's TCB; state it as a residual until the client floor lands.

## Revocation & rotation

REVOKE AN ATTESTATION (do NOT trust body.revoked):
(1) EXPIRY is the load-bearing bound (RED-TEAM 2-major5): set exp to MINUTES-to-hours for privileged actors (the attestation is per-principal and cacheable; re-issue via an operator cron/`cws acl-attest`). Under a COMPROMISED govd the denylist gives nothing (it relays the freshest-unexpired-but-pre-revocation copy), so revocation latency == attestation exp remaining. Honest statement: latency = min(attestation exp remaining, denylist TTL) under an honest govd; = attestation exp remaining under a compromised one.
(2) DENYLIST with a monotonic floor: operator publishes acl-revoked.json (signed by the acl-issuer key, carrying attestation_ids + an issued-at counter + nbf/exp) to the READ-ONLY mount $CW_KEYS/acl-revoked.json — exod loads it OFF the mount, NOT govd-relayed, and PERSISTS+RATCHETS a minimum acceptable issued-at so a compromised body cannot roll back to a pre-revocation list. refuse "acl:revoked".
(3) acl_sha JOIN as implicit revoke-on-change: editing principals.json changes the live acl_sha; an honest govd's recompute no longer joins the old attestation. Does NOT bind a compromised govd (it pairs the old attestation with an old-acl_sha grant) — hence (1)+(2) remain necessary.

ROTATE the operator ACL-issuer key: mint a new keypair; distribute the new PUBLIC half to bodies (NAS gallery / $CW_KEYS/acl-issuer.pub); exod accepts a SMALL PINNED SET (keyring) of acl-issuer pubs during an overlap window, the three-way dual-control applies to each member; re-issue all attestations under the new key; drop the old pub. Private half never lived on a body, so no body-side secret to scrub.

ROTATE a token / client proof key: rotating the token changes token_sha (and the principal identity); rotating the client proof key changes proof_pubkey. Operator re-issues the attestation (new token_sha and/or proof_pubkey) and lists the old attestation_id as revoked; old proofs fail step 6c against the new attestation. Atomic at the operator: one re-attest + one denylist entry. Because the proof key is client-generated and independent, token rotation does NOT require the operator to re-learn any cleartext secret.

EXPIRY enforced by aclverify with the SAME ±DEFAULT_SKEW machinery as grantverify.py:55-59. GRANT-issuer / exod key rotation unchanged (setup-confined-body.sh re-mint); the 3-way dual-control assert must keep all three keyids distinct across any rotation.

## Honest residual + TCB statement

AFTER M0+M1+M2 land, a COMPROMISED govd can STILL:
1. DENIAL OF SERVICE — refuse to relay a valid attestation/proof, mint a wrong-run grant, mark an ACL run cooperative and skip exod (govd.py:984), or drop steps. exod fails closed, so integrity holds but AVAILABILITY is fully govd's. govd could always DoS; unchanged. The cooperative-downgrade specifically can BYPASS exod entirely unless the CLIENT-side delegated-floor (misattribution_handling) is in place — until then it is a real integrity escape inside govd's TCB, stated plainly, not as mere DoS.
2. ACT WITHIN A TOKEN IT GENUINELY HOLDS — if a privileged token (or its independent proof private key) is provisioned onto the govd host, govd IS that principal within that principal's attested ACL. No widening. Mitigation is operational: keep privileged tokens + proof keys with a SEPARATE brain on a DIFFERENT machine. Caveat (RED-TEAM 2-minor8): in the single-box confined-body deploy govd and exod share a host/uid (setup-confined-body.sh runs both units, same $CW_USER) — a root/host compromise lifts BOTH grant_key AND exod's verification state, collapsing the keys-only dual-control. The strong TCB split requires govd!=exod as distinct OS principals (ideally distinct hosts), referencing the exec-never-root residual; on a single-uid box the dual-control is keys-only.
3. LIE IN ITS OWN LEDGER about which principal ran a step (it still maps Bearer->principal at govd.py:867 for its own accounting). It can no longer make EXOD execute under a mis-bound ACL, so the residual demotes from "govd controls a run's authority" to "govd controls its own audit narrative" — detectable by reconciling govd's ledger principal against exod's signed refusals/results.
4. Pre-existing accepted residuals (govd-known-residuals memory): HTTP-plane TOCTOU, fragmentation, rate-limit, agent-proposes-data plan content — out of scope for the run<->token<->ACL edge.

TCB STATEMENT (split exactly along the welds):
- "No token exceeds its operator-attested ACL": TCB = {operator acl-issuer key owner, exod, the pinning + 3-way dual-control of the 3rd pub}. govd EXCLUDED. (Win lands at M1, but holds only per-token; the cross-token substitution is closed at M2.)
- "A run executes under the ACL of the token that ACTUALLY holds it": TCB = {operator key owner, exod, the client/brain holding the token, the token secret + the independent proof key, the Ed25519 crypto}. govd EXCLUDED — the NEW result, landing only at M2. Previously {govd}.
Trust roots that REMAIN: operator acl-issuer private-key custody (off-body); CLIENT proof private-key custody; the integrity of the pub-distribution channel (a swapped acl-issuer.pub on a body lets a forged attestation through — pub provenance matters as much as grant.pub); govd!=exod OS separation for the dual-control to be more than keys-only.
OVERCLAIM GUARD: we claim exactly (1) govd cannot widen a token (operator attestation, M1) and (2) govd cannot bind a run to a token it does not hold (client proof, M2). We do NOT claim removal of govd from availability, from its own audit narrative, from a token it legitimately holds, or from cooperative-downgrade absent the client floor.

## Concrete code changes

- **`infra/govern/principals.py`** — M0 PREREQUISITE (UNBUILT today — verified: registry is only {token_sha,rate,burst}). Add an optional `acl` block per principal: {skills:[canonical id|"*"], perks:{skill:[...]}, max_tier, secrets:[...], delegated_required:bool, expires_at?, revoked?}. Add a PURE function acl_allows(acl, *, skill, perk, perk_tier, destructive, credentialed) -> (bool, reason) that NARROWS: skill not in skills -> skill_not_allowed; perk not in perks[skill] -> perk_not_allowed; perk_tier above max_tier -> tier_exceeds_max; credentialed and any grant credential not in secrets -> secret_not_allowed. Add acl_sha(pid, token_sha, acl) = sha256(canonical {pid,token_sha,skills,perks,max_tier,secrets}) (pid+token_sha FOLDED IN). Keep token VALUES out of the registry (sha-only invariant preserved).
- **`infra/govern/govd.py`** — M0: append acl_allows to govern()'s problems[] (hard reject) using the authenticated pid's acl; re-check on the WS step path. M1/M2: at delegated step-time (near govd.py:984) load the relayed operator attestation for rec['principal'] and pass it to delegate.execute_step; relay the client token_proof from the WS step message. NOTE the cooperative-downgrade residual: exec_mode is selected here (govd.py:984/1040) inside govd's TCB — the forbid-cooperative-for-ACL rule cannot be made unbypassable here against a compromised govd; document and enforce the floor CLIENT-side.
- **`infra/govern/issue.py`** — NEW operator-side minting tool (does NOT exist today — `find` confirms). `cws acl-attest <pid>` / `python -m infra.govern.issue mint`: reads principals.json + the operator acl-issuer PRIVATE key (off-body), recomputes acl_sha=sha256(canonical {pid,token_sha,skills,perks,max_tier,secrets}), reads the client-registered proof_pubkey, and emits one DSSE attestation envelope per non-trivial-ACL principal (payloadType application/vnd.cyberware.acl-attestation+json) with minutes-to-hours exp. Also `revoke <attestation_id>` to append to a signed acl-revoked.json with a monotonic issued-at. Explicitly NOT run by govd.
- **`infra/exec/grants.py`** — M0: extend mint_grant body (currently exactly {run_id,plan_sha,snippet_shas,capabilities,credentials,tier,nbf,exp,nonce[,sandbox_tier]} at grants.py:38-40) with optional acl_sha + canonical skill + perk + destructive (value-free claim facts). A legacy grant without acl_sha is refused under acl_strict (test it).
- **`infra/exec/grantverify.py`** — No behavior change to verify_grant; export grant_body/_issuer for aclverify reuse. Add the new acl_sha/skill/perk/destructive fields to the grant_body accessor surface.
- **`infra/exec/aclverify.py`** — NEW file (sibling of grantverify.py, prose-clean mutation target). verify_acl_attestation(acl_issuer_pub, envelope, *, now, expect_acl_sha, expect_pid_token_fields, skew) -> (ok, reason): sign.verify FIRST, payloadType, nbf/exp ±skew, RE-DERIVE acl_sha from body's own {pid,token_sha,skills,perks,max_tier,secrets} ==body.acl_sha ==expect_acl_sha. verify_token_proof(proof_pubkey, envelope, *, expect_run_id, expect_plan_sha, expect_step, expect_token_sha, banned_pubkeys, nonce_cache): degenerate-pubkey guard, sign.verify, payloadType, token_sha/run_id/plan_sha/step equality, single-use spend.
- **`infra/exec/exod.py`** — M1/M2: add acl_issuer_pub kwarg to Exod.__init__ (exod.py:51), store self._acl_issuer_pub; extend the 2-way dual-control assert at exod.py:53 to THREE-WAY (run it whenever acl_issuer_pub is set, both phases). Add --acl-issuer-pub/EXOD_ACL_ISSUER_PUB and --acl-strict/EXOD_ACL_STRICT to main() (sibling of --issuer-pub), load raw 32 bytes, pass into Exod(). Add a per-(token_sha,run_id,step) NonceCache. Insert step 1b in run_step BETWEEN grant-OK (exod.py:98-101) and capability (exod.py:104), BEFORE nonce spend (exod.py:116): verify attestation, acl_sha join, RE-RUN acl_allows on the grant's claimed skill/perk/tier/credentials, then (M2) verify the client token_proof. Load acl-revoked.json off $CW_KEYS (NOT govd-relayed) with a persisted monotonic floor. Each deny -> refuse('acl:'/'proof:'+reason).
- **`spec/schemas/grant.schema.json`** — Add optional acl_sha + skill + perk + destructive to the grant body schema. NOTE this CWP {cwp,type,body,sig} schema already DIVERGES from the runtime DSSE envelope in grants.py — fix or annotate the divergence while here. Add two NEW sibling schemas: acl-attestation.schema.json and token-proof.schema.json matching the DSSE runtime shape.
- **`deploy/setup-confined-body.sh`** — Keep the keygen block (setup-confined-body.sh:60-76) grant+exod ONLY — do NOT mint the acl-issuer key. Add an ORDERED provisioning step: REQUIRE $CW_KEYS/acl-issuer.pub present (operator scp or pulled from the verified read-only NAS gallery) AND assert its keyid distinct from grant.pub AND exod.pub (mirror the line-70 assert, three-way) BEFORE enabling --acl-strict. Extend the exod ExecStart (setup-confined-body.sh:120) with --acl-issuer-pub $CW_KEYS/acl-issuer.pub (and --acl-strict at phase 2). Mount/point $CW_KEYS/acl-revoked.json read-only. govd.json unchanged (no acl-issuer or proof private key).

## Open decisions (attestation layer)

1. SEQUENCING: confirm the three-milestone order (M0 base ACL -> M1 ceiling -> M2 binding) and that acl_strict's HARD flip is gated on M2 landing, not M1. Both red-teams: flipping on the ceiling alone advertises escalation-resistance the code lacks (multi-attestation substitution is escalation, not DoS).
2. CLIENT PROOF KEY PROVISIONING: the proof key is an INDEPENDENT client-generated key whose public half the client registers with the operator at provisioning (NOT HKDF-from-bearer). Decide the registration channel (does it ride principal provisioning? a self-register endpoint? out-of-band to the operator?) and how rotation re-registers proof_pubkey without the operator learning any cleartext token.
3. COOPERATIVE-DOWNGRADE FLOOR: the forbid-cooperative-for-ACL rule lives in govd's TCB (exec_mode at govd.py:984) and a compromised govd ignores it. Decide whether to ship the CLIENT-side delegated-required floor (brain refuses cooperative for ACL-bearing tokens; attestation marks delegated_required) NOW with M1, or accept cooperative-downgrade as a stated integrity residual until a later milestone.
4. GOVD!=EXOD HOST SEPARATION: the strong TCB split assumes govd and exod are distinct OS principals/hosts, but the single-box confined-body deploy runs both as the same $CW_USER. Decide whether to require distinct uids/hosts for the strict claim (tie to the exec-never-root residual) or scope the strong claim to the fleet topology only.
5. acl_sha PREIMAGE: confirm folding pid+token_sha INTO acl_sha = sha256(canonical {pid,token_sha,skills,perks,max_tier,secrets}) (so same-ACL actors are not interchangeable). This changes the join semantics govd recomputes — confirm govd has pid+token_sha at recompute time (it does: it authenticated the bearer).
6. REVOCATION INFRA: decide whether to ship the operator-signed denylist with a persisted monotonic floor (read off the read-only mount) in M1, or rely solely on short attestation exp as the load-bearing bound and defer the denylist. Under a compromised govd the denylist adds nothing within-TTL.
7. PROOF FRESHNESS / CLOCK: decide whether to enforce |now - proof.ts| <= skew (the proof is already step-and-nonce bound, so a ts window is belt-and-braces); pick the skew to match grantverify's ±60s or tighten it.
8. grant.schema.json DIVERGENCE: the CWP {cwp,type,body,sig} schema already does NOT match the runtime DSSE envelope in grants.py. Decide whether to fix the schema to the runtime truth (and add the two new attestation/proof schemas) or annotate the divergence as known.