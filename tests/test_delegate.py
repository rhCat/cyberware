"""P2-T12 — govd→exod delegation channel (infra/govern/delegate.py).

The security claim: in delegated mode the AUTHORITATIVE status is exod's SIGNED result (authority=='exod'),
not the agent's self-report; a forged/unverifiable result is refused + recorded as evidence; an unreachable
limb fails closed; a replayed result nonce is caught. The channel is proven here off-Linux with a stub
runner (the real bwrap confinement runs on the exec image)."""
from __future__ import annotations

import subprocess

from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

from infra.exec.exod import Exod
from infra.exec.exodverify import result_body
from infra.govern import delegate
from infra.govern.compiler import build_plan


class _Stub:
    def __init__(self, rc=0):
        self.rc, self.calls = rc, []

    def __call__(self, profile, argv, backend=None):
        self.calls.append((profile, argv, backend))
        return subprocess.CompletedProcess(argv, self.rc, "step-output", "")


def _rec(run_id="R1"):
    plan = build_plan("fs", "find_large")                                # credential_ids comes from the PLAN,
    return {"run_id": run_id, "skill": "fs", "perk": "find_large", "wrapper": plan["wrapper"],   # not hardcoded —
            "seq": plan["sequence"], "snippet_shas": plan["snippet_shas"],                       # mirrors the real
            "credential_ids": plan.get("credential_ids", []), "events": []}                      # govd record


def _inproc(exod_obj, now=1000):
    return lambda socket, req: exod_obj.run_step(req, now=now)


def test_delegated_status_is_exod_signed_not_the_agent(tmp_path):
    gk = Ed25519PrivateKey.generate()                                # govd's grant-issuer key
    exod_obj = Exod(Ed25519PrivateKey.generate(), grant_issuer_pub=gk.public_key(), runner=_Stub(rc=0))
    reply, event = delegate.execute_step(_rec(), "1", "PSHA", exod_socket="x", grant_key=gk,
                                         exod_pub=exod_obj.public_key, base=str(tmp_path),
                                         request=_inproc(exod_obj), now=1000)
    assert reply["status"] == "ok" and reply["authority"] == "exod"  # the agent never reported this
    assert event["type"] == "step_result" and event["authority"] == "exod"
    assert event["exod_keyid"].startswith("ed25519:") and event["result_nonce"]
    assert event["meter"]["by"] == "exod"                            # exod's attested meter, settleable


def test_unreachable_exod_fails_closed(tmp_path):
    gk = Ed25519PrivateKey.generate()
    def boom(_sock, _req):
        raise ConnectionRefusedError("no limb")
    reply, event = delegate.execute_step(_rec(), "1", "PSHA", exod_socket="x", grant_key=gk,
                                         exod_pub=Ed25519PrivateKey.generate().public_key(),
                                         base=str(tmp_path), request=boom, now=1000)
    assert reply["status"] == "refused" and reply["reason"] == "exod_unreachable" and event is None


def test_forged_result_is_refused_and_recorded(tmp_path):
    gk = Ed25519PrivateKey.generate()
    real = Exod(Ed25519PrivateKey.generate(), grant_issuer_pub=gk.public_key(), runner=_Stub())
    impostor_pub = Ed25519PrivateKey.generate().public_key()          # govd expects a DIFFERENT exod key
    reply, event = delegate.execute_step(_rec(), "1", "PSHA", exod_socket="x", grant_key=gk,
                                         exod_pub=impostor_pub, base=str(tmp_path),
                                         request=_inproc(real), now=1000)
    assert reply["status"] == "refused" and reply["reason"].startswith("exod_verify")
    assert event["type"] == "forged_status_refused"                  # recorded as evidence


def test_delegated_credential_reaches_the_confined_step_only_when_granted(tmp_path):
    """A perk that declares credentials gets them resolved by the LIMB's vault into the CONFINED step's env in
    delegated mode (the wiring is live, not dead) — and only the server-authorized IDs, never others."""
    from infra.exec import vault as _vaultmod
    gk = Ed25519PrivateKey.generate()
    secret = "SEKRET-" + "y" * 16
    vault = _vaultmod.EnvStubVault({"api-key": secret, "other": "nope"})
    stub = _Stub(rc=0)
    exod_obj = Exod(Ed25519PrivateKey.generate(), grant_issuer_pub=gk.public_key(), runner=stub, vault=vault)
    rec = _rec()
    rec["credential_ids"] = ["api-key"]                              # a perk that declares one credential
    reply, _event = delegate.execute_step(rec, "1", "PSHA", exod_socket="x", grant_key=gk,
                                          exod_pub=exod_obj.public_key, base=str(tmp_path),
                                          request=_inproc(exod_obj), now=1000)
    assert reply["status"] == "ok"
    prof, _argv, _backend = stub.calls[-1]
    assert prof.env.get("CWS_SECRET_API_KEY") == secret             # the granted secret reached the confined step
    assert "CWS_SECRET_OTHER" not in prof.env                       # an ungranted credential is NOT injected


def test_delegated_refusal_is_recorded_under_a_distinct_type_not_step_result(tmp_path):
    """A step exod REFUSES (here a credential is granted but the limb has no vault) is recorded as evidence
    under a DISTINCT type — OUTSIDE the at-most-once done-set — so a transient refusal does not wedge the run
    (a completed ok/error step stays a step_result and is never re-run)."""
    gk = Ed25519PrivateKey.generate()
    exod_obj = Exod(Ed25519PrivateKey.generate(), grant_issuer_pub=gk.public_key(), runner=_Stub(rc=0))  # NO vault
    rec = _rec()
    rec["credential_ids"] = ["api-key"]                              # forces exod to refuse (vault:unavailable)
    reply, event = delegate.execute_step(rec, "1", "PSHA", exod_socket="x", grant_key=gk,
                                         exod_pub=exod_obj.public_key, base=str(tmp_path),
                                         request=_inproc(exod_obj), now=1000)
    assert reply["status"] == "refused"
    assert event["type"] == "step_delegation_refused" and event["status"] == "refused"   # not a step_result


def test_replayed_result_nonce_is_refused(tmp_path):
    from infra.cwp import sign
    gk = Ed25519PrivateKey.generate()
    exod_obj = Exod(Ed25519PrivateKey.generate(), grant_issuer_pub=gk.public_key(), runner=_Stub())
    rec = _rec()
    _reply, event = delegate.execute_step(rec, "1", "PSHA", exod_socket="x", grant_key=gk,
                                          exod_pub=exod_obj.public_key, base=str(tmp_path),
                                          request=_inproc(exod_obj), now=1000)
    rec["events"].append(event)                                      # the run already recorded this result nonce
    old_nonce = event["result_nonce"]

    def replay(_sock, req):                                          # a freshly-signed result carrying the OLD nonce
        envl = exod_obj.run_step(req, now=1000)
        body = result_body(envl)
        body["nonce"] = old_nonce
        return sign.sign(body, exod_obj._sk, payload_type=envl["payloadType"])
    reply2, event2 = delegate.execute_step(rec, "1", "PSHA", exod_socket="x", grant_key=gk,
                                           exod_pub=exod_obj.public_key, base=str(tmp_path),
                                           request=replay, now=1000)
    assert reply2["status"] == "refused" and reply2["reason"] == "result_replay" and event2 is None


def _registry_with_tier(root, tier):
    """A minimal registry: one skill 'mkt' with a perk 'p1' declaring sandbox tier `tier` in perks.json."""
    import json
    import os
    sd = os.path.join(root, "mkt")
    os.makedirs(sd, exist_ok=True)
    json.dump({"perks": [{"id": "p1", "summary": "", "tier": tier}]}, open(os.path.join(sd, "perks.json"), "w"))
    return root


def test_perk_declared_tier_flows_into_the_grant(tmp_path):
    """P3-T11: a perk that DECLARES `tier: community` in perks.json makes govd mint the grant with
    sandbox_tier=community (the backend selector); an unrecognized tier is fail-safed to community; an
    undeclared/absent perk leaves sandbox_tier None so the grant takes the operator floor (no regression)."""
    from infra.exec.grantverify import grant_body
    reg = _registry_with_tier(str(tmp_path / "reg"), "community")
    assert delegate.perk_sandbox_tier("mkt", "p1", reg) == "community"
    assert delegate.perk_sandbox_tier("mkt", "absent", reg) is None         # absent perk → None (operator floor)
    garbage = _registry_with_tier(str(tmp_path / "r2"), "not-a-tier")
    assert delegate.perk_sandbox_tier("mkt", "p1", garbage) == "community"  # unrecognized tier → fail-safe community
    core = _registry_with_tier(str(tmp_path / "r3"), "core")
    assert delegate.perk_sandbox_tier("mkt", "p1", core) == "core"          # a trusted-family tier is preserved

    captured = {}

    def capture(_sock, req):
        captured["sandbox_tier"] = grant_body(req["grant"]).get("sandbox_tier")
        raise RuntimeError("captured — short-circuit before exod runs")     # delegate → fails closed, grant still minted

    gk = Ed25519PrivateKey.generate()
    exod_obj = Exod(Ed25519PrivateKey.generate(), grant_issuer_pub=gk.public_key())
    rec = {"run_id": "R1", "skill": "mkt", "perk": "p1", "wrapper": "#!/bin/sh\n",
           "snippet_shas": {}, "credential_ids": [], "events": []}
    delegate.execute_step(rec, "1", "PSHA", exod_socket="x", grant_key=gk, exod_pub=exod_obj.public_key,
                          base=str(tmp_path / "ws"), request=capture, registry=reg, now=1000)
    assert captured["sandbox_tier"] == "community"                          # the declared tier reached the grant
