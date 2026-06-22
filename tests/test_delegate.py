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

    def __call__(self, profile, argv):
        self.calls.append((profile, argv))
        return subprocess.CompletedProcess(argv, self.rc, "step-output", "")


def _rec(run_id="R1"):
    plan = build_plan("fs", "find_large")
    return {"run_id": run_id, "skill": "fs", "perk": "find_large", "wrapper": plan["wrapper"],
            "seq": plan["sequence"], "snippet_shas": plan["snippet_shas"], "credential_ids": [], "events": []}


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
