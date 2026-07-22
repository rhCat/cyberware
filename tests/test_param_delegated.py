"""Parameterized delegated execution — the ACL `params` capability + the non-secret var-VALUE channel.

A delegated run carries caller VALUES (e.g. MODEL_HANDLE, SEARCH_DIR) over the per-run WS, gated by the
actor's `params` ACL axis; secret-named keys never cross the wire (they stay *_FILE pointers / vault
credentials, node-local). govd's claim plane + record stay keys-only; values ride WS -> req["env"] -> exod.
"""
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

from infra.govern import principals as P
from infra.govern import delegate
from infra.govern.govd_client import _wire_values


def test_acl_params_axis_denies_and_allows():
    base = {"skills": ["*"]}
    # a parameterized run WITHOUT the grant is refused (fail-closed), like the secrets axis
    ok, prob = P.acl_allows(base, "general:fs", "find", "core", False, False, parameterized=True)
    assert not ok and prob["id"] == "acl_params_denied"
    # WITH params:true it is allowed
    ok, _ = P.acl_allows({**base, "params": True}, "general:fs", "find", "core", False, False, parameterized=True)
    assert ok
    # a NON-parameterized claim is unaffected whether or not params is granted
    assert P.acl_allows(base, "general:fs", "find", "core", False, False, parameterized=False)[0]
    assert P.acl_allows({**base, "params": True}, "general:fs", "find", "core", False, False)[0]


def test_params_rides_the_acl_digest():
    # the capability is folded into acl_sha, so an off-node grant/attestation binds it (no cross-boundary replay)
    a = P.acl_sha("pid", "toksha", {"skills": ["*"]})
    b = P.acl_sha("pid", "toksha", {"skills": ["*"], "params": True})
    assert a != b


def test_wire_values_drops_secret_named_keeps_plain_and_pointers():
    got = _wire_values({"MODEL_HANDLE": "nvidia/Qwen3.6-35B-A3B-NVFP4", "SEARCH_DIR": "/tmp",
                        "API_TOKEN": "s", "PGPASSWORD": "s", "AWS_SECRET_ACCESS_KEY": "s",
                        "MY_PRIVATE_KEY": "s", "HF_TOKEN_FILE": "/run/hf", "CWS_SECRET_DB": "z"})
    # plain values + *_FILE pointers cross; anything secret-named or the reserved vault namespace is dropped
    assert got == {"MODEL_HANDLE": "nvidia/Qwen3.6-35B-A3B-NVFP4", "SEARCH_DIR": "/tmp", "HF_TOKEN_FILE": "/run/hf"}


def test_execute_step_merges_non_secret_values_into_the_confined_env(tmp_path):
    """execute_step lands caller var_values in req['env'] (-> exod --setenv), atop the fixed non-secret env."""
    captured = {}

    def fake_request(sock, req):
        captured.update(req)                 # snapshot the request govd would send exod...
        raise RuntimeError("captured")       # ...then short-circuit (exod verify is out of scope here)

    gk = Ed25519PrivateKey.generate()
    rec = {"run_id": "r1", "skill": "general:fs", "perk": "find",
           "wrapper": "#!/usr/bin/env bash\n", "snippet_shas": {}, "credential_ids": []}
    reply, event = delegate.execute_step(
        rec, "1", "psha", exod_socket=None, grant_key=gk, exod_pub=gk.public_key(),
        base=str(tmp_path), request=fake_request,
        var_values={"MODEL_HANDLE": "nvidia/Qwen3.6-35B-A3B-NVFP4", "SEARCH_DIR": "/tmp"})
    assert reply["reason"] == "exod_unreachable"          # the stub raised -> caught -> refusal (but it captured)
    env = captured["env"]
    assert env["MODEL_HANDLE"] == "nvidia/Qwen3.6-35B-A3B-NVFP4" and env["SEARCH_DIR"] == "/tmp"
    assert "PATH" in env and "SNIP" in env and "RECORD_STORE" in env   # the fixed govd env survives the merge


def test_execute_step_without_values_is_unchanged(tmp_path):
    """Back-compat: no var_values => the env is exactly the fixed {PATH,SNIP,RECORD_STORE}, no caller keys."""
    captured = {}

    def fake_request(sock, req):
        captured.update(req)
        raise RuntimeError("captured")

    gk = Ed25519PrivateKey.generate()
    rec = {"run_id": "r2", "skill": "general:fs", "perk": "find",
           "wrapper": "#!/usr/bin/env bash\n", "snippet_shas": {}, "credential_ids": []}
    delegate.execute_step(rec, "1", "psha", exod_socket=None, grant_key=gk, exod_pub=gk.public_key(),
                          base=str(tmp_path), request=fake_request)
    assert set(captured["env"]) == {"PATH", "SNIP", "RECORD_STORE"}


# ── hardening (citrinitas+putrefactio review fixes) ──────────────────────────────────────────────

def test_attestation_join_holds_for_params_actor():
    """PD-H01 regression: adding `params` to acl_canonical MUST thread through the attestation body +
    attested_acl, else a params-granted actor's govd grant acl_sha != exod's re-derived acl_sha ->
    acl_join_mismatch -> exod refuses the step. This is the test that would have caught the blocker."""
    from infra.govern import issue
    from infra.exec.aclverify import verify_acl_attestation, attested_acl
    op = Ed25519PrivateKey.generate()
    acl = {"skills": ["*"], "params": True}
    grant_sha = P.acl_sha("pid", "toksha", acl)                 # what govd binds into the grant (params-inclusive)
    att = issue.mint_attestation(op, pid="pid", token_sha="toksha", acl=acl, nbf=0, exp=10**12, attestation_id="a1")
    ok, why = verify_acl_attestation(op.public_key(), att, now=1, expect_acl_sha=grant_sha)
    assert ok, f"join must hold for a params actor, got: {why}"
    # and attested_acl reconstructs params so exod's re-run of acl_allows can re-enforce it
    from infra.exec.aclverify import attestation_body
    assert attested_acl(attestation_body(att)).get("params") is True


def test_attested_acl_carries_params():
    from infra.exec.aclverify import attested_acl
    assert attested_acl({"skills": ["*"], "params": True}).get("params") is True
    assert attested_acl({"skills": ["*"]}).get("params") is None   # absent -> None (matches a params-less grant)


def test_wire_values_drops_broadened_secret_names():
    """PD-H04: the broadened denylist catches the unambiguous secret names the original regex missed —
    passphrase, ssh/gpg/signing key, credential, mnemonic, seed_phrase, bearer."""
    got = _wire_values({
        "MODEL_HANDLE": "ok", "SEARCH_DIR": "/tmp",              # plain -> kept
        "PASSPHRASE": "s", "SSH_KEY": "s", "GPG_KEY": "s", "SIGNING_KEY": "s", "PRIVKEY": "s",
        "DB_CREDENTIAL": "s", "BEARER": "s", "WALLET_MNEMONIC": "s", "SEED_PHRASE": "s",
        "HF_TOKEN_FILE": "/p",                                   # *_FILE pointer -> kept
    })
    assert got == {"MODEL_HANDLE": "ok", "SEARCH_DIR": "/tmp", "HF_TOKEN_FILE": "/p"}


def test_denylist_does_not_over_reject_session_jwt_cookie_metadata():
    """PD-H04 correction (review P3): `session`/`jwt`/`cookie` as bare substrings are NOT in the denylist —
    they over-reject non-secret METADATA (SESSION_ID, SESSION_TIMEOUT, JWT_ALG, JWT_ISSUER, COOKIE_NAME)
    whose genuine secret forms (SESSION_TOKEN via token, JWT_SECRET via secret) are already caught. These
    metadata keys must CROSS as ordinary non-secret values."""
    meta = {"SESSION_ID": "sid", "SESSION_TIMEOUT": "30", "JWT_ALG": "RS256", "JWT_ISSUER": "https://iss",
            "COOKIE_NAME": "sid", "COOKIE_DOMAIN": ".example.com"}
    assert _wire_values(meta) == meta                           # every metadata key rides — none refused
    # the genuine secret compounds STILL drop (caught by token/secret/key, not by session/jwt/cookie)
    assert _wire_values({"SESSION_TOKEN": "s", "JWT_SECRET": "s", "COOKIE_SECRET": "s"}) == {}


def test_pointer_suffixes_exempt_the_location_not_the_secret():
    """PD-H04 refinement: a secret-matched key ending _FILE/_DIR/_PATH names WHERE something lives (a path,
    read at runtime) — it crosses; a bare secret key (SSH_KEY, BEARER) stays refused."""
    got = _wire_values({
        "SSH_KEY_DIR": "/home/u/.ssh", "SSH_KEY_PATH": "/home/u/.ssh/id", "TOKEN_DIR": "/run/tok",  # pointers -> kept
        "SSH_KEY": "s", "BEARER": "s", "API_TOKEN": "s", "GPG_KEY": "s",   # the credential (non-pointer) -> dropped
    })
    assert got == {"SSH_KEY_DIR": "/home/u/.ssh", "SSH_KEY_PATH": "/home/u/.ssh/id", "TOKEN_DIR": "/run/tok"}
    # and govd's authoritative claim gate agrees (the same POINTER_SUFFIX at the plaintext_secret_key site)
    from infra.govern.govd import SECRET_KEY, POINTER_SUFFIX
    refused = [k for k in ["SSH_KEY_DIR", "SSH_KEY_PATH", "TOKEN_DIR", "SSH_KEY", "BEARER", "API_TOKEN", "GPG_KEY"]
               if SECRET_KEY.search(k) and not k.endswith(POINTER_SUFFIX)]
    assert refused == ["SSH_KEY", "BEARER", "API_TOKEN", "GPG_KEY"]


def test_execute_step_never_lets_a_value_override_the_fixed_env(tmp_path):
    """PD-H03: even if a reserved key reaches execute_step, it must NOT clobber PATH/SNIP/RECORD_STORE."""
    captured = {}
    def fake_request(sock, req):
        captured.update(req); raise RuntimeError("captured")
    gk = Ed25519PrivateKey.generate()
    rec = {"run_id": "r1", "skill": "general:fs", "perk": "find",
           "wrapper": "#!/usr/bin/env bash\n", "snippet_shas": {}, "credential_ids": []}
    delegate.execute_step(rec, "1", "psha", exod_socket=None, grant_key=gk, exod_pub=gk.public_key(),
                          base=str(tmp_path), request=fake_request,
                          var_values={"PATH": "/evil", "SNIP": "/evil", "RECORD_STORE": "/evil", "MODEL_HANDLE": "ok"})
    env = captured["env"]
    assert env["PATH"] != "/evil" and "/evil" not in env["SNIP"] and "/evil" not in env["RECORD_STORE"]
    assert env["MODEL_HANDLE"] == "ok"                          # the legitimate value still lands


# ── PD-H02/PD-H06: exod's OFF-NODE params re-enforcement, driven through the REAL _acl_check ─────
# (not a re-implementation of the derivation — the review proved by mutation that an inline restatement
# lets both the drop-`parameterized=` and drop-RECORD_STORE regressions ship green; these kill them.)
from infra.cwp import sign as _sign
from infra.exec.exod import Exod as _Exod
from infra.govern import issue as _issue

_GRANT = _sign.keygen_from_seed(b"pd-grant".ljust(32, b"0"))
_EXODK = _sign.keygen_from_seed(b"pd-exod".ljust(32, b"0"))
_OP = _sign.keygen_from_seed(b"pd-acl-issuer".ljust(32, b"0"))
_FIXED = {"PATH": "/usr/bin", "SNIP": "/ws/snip", "RECORD_STORE": "/ws/rec"}   # govd's fixed confined env


def _pd_exod():
    return _Exod(_EXODK, grant_issuer_pub=_GRANT.public_key(), acl_issuer_pub=_OP.public_key(),
                 runner=lambda *a, **k: None)               # _acl_check never touches the runner


def _pd_req(acl, env):
    att = _issue.mint_attestation(_OP, pid="agent-1", token_sha="tok-sha", acl=acl,
                                  nbf=1000, exp=5000, attestation_id="att-pd")
    return {"attestation": att, "env": env}


def _pd_gbody(acl):
    return {"acl_sha": P.acl_sha("agent-1", "tok-sha", acl), "skill": "general:fs", "perk": "find",
            "sandbox_tier": None, "destructive": False, "credentials": []}


def test_exod_refuses_caller_values_for_a_params_less_actor():
    """A grant WITHOUT the params capability + a step env carrying a caller value -> exod itself denies,
    off-node, from what it ACTUALLY received (kills the drop-`parameterized=` mutant at the acl_allows call)."""
    acl = {"skills": ["*"], "max_tier": "community", "secrets": False}          # no params grant
    env = {**_FIXED, "MODEL_HANDLE": "nvidia/Qwen3.6-35B-A3B-NVFP4"}            # a caller value crossed
    assert _pd_exod()._acl_check(_pd_req(acl, env), _pd_gbody(acl), now=1500) == "acl_params_denied"


def test_exod_passes_the_fixed_env_for_a_params_less_actor():
    """The govd-supplied confined triple alone is NOT parameterized — a params-less actor still runs
    (kills the drop-RECORD_STORE-from-the-reserved-set mutant: the triple would misderive as caller values)."""
    acl = {"skills": ["*"], "max_tier": "community", "secrets": False}
    assert _pd_exod()._acl_check(_pd_req(acl, dict(_FIXED)), _pd_gbody(acl), now=1500) is None


def test_exod_passes_caller_values_for_a_params_granted_actor():
    """WITH params:true attested, the same caller value is allowed — the axis gates, it does not prohibit."""
    acl = {"skills": ["*"], "max_tier": "community", "secrets": False, "params": True}
    env = {**_FIXED, "MODEL_HANDLE": "nvidia/Qwen3.6-35B-A3B-NVFP4"}
    assert _pd_exod()._acl_check(_pd_req(acl, env), _pd_gbody(acl), now=1500) is None


def test_value_ledger_records_and_decrypts_the_filtered_values(tmp_path):
    """Tier-2 (docs/pg-provenance-ledger.md): the same declared, non-secret values that ride the WS are
    ENCRYPTED at rest and their PLAINTEXT commitment (values_sha) is what the tier-1 chain step event carries.
    The node decrypts its own ledger with its recipient key; the commitment matches the plaintext."""
    from infra.govern.govd import Store
    from infra.store import valuecrypt

    st = Store(str(tmp_path), cfg={})                    # value ledger default-on
    vals = {"SOURCE": "/repos/curl", "LIMIT": "50"}      # the post-filter (declared, non-secret) values
    sha = st.record_values("runP", "1", "2026-07-22T00:00:00Z", vals)
    assert sha == valuecrypt.values_sha(vals)            # commitment is over the canonical PLAINTEXT
    st.mirror.flush()
    view = st.decrypt_values("runP")
    assert len(view) == 1 and view[0]["values"] == vals and view[0]["values_sha"] == sha


def test_value_ledger_never_records_empty_or_when_disabled(tmp_path):
    from infra.govern.govd import Store
    st = Store(str(tmp_path / "on"), cfg={})
    assert st.record_values("r", "1", "t", {}) is None   # empty filtered set -> nothing recorded, no sha
    off = Store(str(tmp_path / "off"), cfg={"value_ledger": {"enabled": False}})
    assert off.record_values("r", "1", "t", {"A": "1"}) is None
    assert off.decrypt_values("r") == []
