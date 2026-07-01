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
