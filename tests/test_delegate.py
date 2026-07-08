"""P2-T12 — govd→exod delegation channel (infra/govern/delegate.py).

The security claim: in delegated mode the AUTHORITATIVE status is exod's SIGNED result (authority=='exod'),
not the agent's self-report; a forged/unverifiable result is refused + recorded as evidence; an unreachable
limb fails closed; a replayed result nonce is caught. The channel is proven here off-Linux with a stub
runner (the real bwrap confinement runs on the exec image)."""
from __future__ import annotations

import os
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


def test_grant_acl_fields_are_all_or_nothing_gated_on_acl_sha(tmp_path):
    """ACL M1 (citrinitas D3): an UNSCOPED (no acl_sha) grant body stays BYTE-IDENTICAL to the pre-ACL form —
    none of acl_sha/skill/perk/destructive is stamped, and no attestation rides. An ACL'd rec carries all four
    binding fields together + relays the attestation. This pins the all-or-nothing gate at the live call site."""
    from infra.exec.grantverify import grant_body
    gk = Ed25519PrivateKey.generate()
    cap = {}

    def capture(_sock, req):
        cap["g"] = grant_body(req["grant"])
        cap["att"] = req.get("attestation")
        raise RuntimeError("captured — short-circuit before exod runs")     # delegate fails closed; grant minted

    # unscoped: rec has no acl_sha -> the grant body gains NONE of the ACL keys (byte-identical to pre-ACL)
    delegate.execute_step(_rec(), "1", "PSHA", exod_socket="x", grant_key=gk, exod_pub=gk.public_key(),
                          base=str(tmp_path / "a"), request=capture, now=1000)
    assert not any(k in cap["g"] for k in ("acl_sha", "skill", "perk", "destructive"))
    assert cap["att"] is None

    # ACL'd: rec carries acl_sha -> all four binding fields travel together + the attestation is relayed
    rec = {**_rec(), "acl_sha": "ab" * 32, "destructive": False}
    delegate.execute_step(rec, "1", "PSHA", exod_socket="x", grant_key=gk, exod_pub=gk.public_key(),
                          base=str(tmp_path / "b"), request=capture, now=1000, attestation={"payload": "x"})
    g = cap["g"]
    assert g["acl_sha"] == "ab" * 32 and g["skill"] == "fs" and g["perk"] == "find_large" and g["destructive"] is False
    assert cap["att"] == {"payload": "x"}


def test_acl_delegated_end_to_end_exod_reenforces_off_node(tmp_path):
    """ACL M1 end-to-end: an ACL'd rec → delegate binds acl_sha + relays the operator attestation → exod
    (acl-issuer pinned, strict) re-derives acl_sha, JOINs it against the grant, and re-runs acl_allows. An
    IN-SCOPE claim executes; an OUT-OF-SCOPE claim is REFUSED by exod off-node even though govd minted the
    grant — the compromised-govd-can't-widen property, exercised through the full govd→delegate→exod path."""
    from infra.govern import issue, principals
    op = Ed25519PrivateKey.generate()
    gk = Ed25519PrivateKey.generate()
    exod_obj = Exod(Ed25519PrivateKey.generate(), grant_issuer_pub=gk.public_key(),
                    acl_issuer_pub=op.public_key(), acl_strict=True, runner=_Stub(0))

    def _run(acl, base):
        # govd recomputes acl_sha from the live fields; the operator attests the SAME acl (so the join holds)
        sha = principals.acl_sha("agent-1", "sha-x", acl)
        att = issue.mint_attestation(op, pid="agent-1", token_sha="sha-x", acl=acl, nbf=990, exp=2000, attestation_id="a1")
        rec = {**_rec(), "acl_sha": sha, "destructive": False}             # the claim is always fs/find_large
        return delegate.execute_step(rec, "1", "PSHA", exod_socket="x", grant_key=gk, exod_pub=exod_obj.public_key,
                                     base=str(base), request=_inproc(exod_obj), now=1000, attestation=att)

    in_scope = {"skills": ["fs"], "perks": {"fs": ["find_large"]}, "max_tier": "community", "secrets": False}
    out_scope = {"skills": ["fs"], "perks": {"fs": ["nope"]}, "max_tier": "community", "secrets": False}
    ok_reply, ok_event = _run(in_scope, tmp_path / "ok")
    assert ok_reply.get("status") == "ok" and ok_event is not None         # in scope → exod ran it + signed
    no_reply, _ = _run(out_scope, tmp_path / "no")
    assert no_reply.get("status") == "refused"                            # out of scope → exod refused off-node


def test_acl_m2_delegated_end_to_end_token_proof(tmp_path):
    """ACL M2 e2e: an attestation that BINDS a client proof_pubkey → delegate relays the token_proof → exod
    REQUIRES + verifies it. A valid proof executes; a missing proof (a govd relaying the attestation without
    the actor's proof) is refused off-node — the run<->token misattribution close, through the full path."""
    import base64
    from cryptography.hazmat.primitives import serialization as _s
    from infra.exec import aclverify
    from infra.govern import issue, principals
    op = Ed25519PrivateKey.generate()
    gk = Ed25519PrivateKey.generate()
    pk = Ed25519PrivateKey.generate()                                     # the actor's INDEPENDENT proof key
    ppub_b64 = base64.b64encode(pk.public_key().public_bytes(_s.Encoding.Raw, _s.PublicFormat.Raw)).decode()
    exod_obj = Exod(Ed25519PrivateKey.generate(), grant_issuer_pub=gk.public_key(),
                    acl_issuer_pub=op.public_key(), acl_strict=True, runner=_Stub(0))
    acl = {"skills": ["fs"], "perks": {"fs": ["find_large"]}, "max_tier": "community", "secrets": False}
    rec = {**_rec(), "acl_sha": principals.acl_sha("agent-1", "sha-x", acl), "destructive": False}
    att = issue.mint_attestation(op, pid="agent-1", token_sha="sha-x", acl=acl, nbf=990, exp=2000,
                                 attestation_id="a1", proof_pubkey=ppub_b64)

    def run(token_proof, base):
        return delegate.execute_step(rec, "1", "PSHA", exod_socket="x", grant_key=gk, exod_pub=exod_obj.public_key,
                                     base=str(base), request=_inproc(exod_obj), now=1000,
                                     attestation=att, token_proof=token_proof)

    good = aclverify.mint_token_proof(pk, run_id=rec["run_id"], plan_sha="PSHA", step="1", token_sha="sha-x")
    ok_reply, ok_event = run(good, tmp_path / "ok")
    assert ok_reply.get("status") == "ok" and ok_event is not None       # valid proof → exod ran it
    no_reply, _ = run(None, tmp_path / "no")
    assert no_reply.get("status") == "refused"                           # proof bound but not relayed → refused


def test_materialize_workspace_writes_the_wrapper_verbatim(tmp_path):
    """run.sh must BE the blessed wrapper (byte-for-byte) — and an absent wrapper degrades to an empty file,
    never a crash. Pins the `or ""` default so a flipped operator can't silently write an EMPTY run.sh for a
    real wrapper (the confined step would no-op 'ok' without running its gated sequence)."""
    from infra.govern.delegate import materialize_workspace
    wrapper = "#!/usr/bin/env bash\nset -uo pipefail\nstep1() { echo x; }\n"
    ws, env, run_sh = materialize_workspace({"run_id": "rw1", "wrapper": wrapper,
                                             "skill": "nosuch", "perk": "nosuch"}, str(tmp_path))
    assert open(run_sh).read() == wrapper
    ws2, _, run_sh2 = materialize_workspace({"run_id": "rw2", "wrapper": None,
                                             "skill": "nosuch", "perk": "nosuch"}, str(tmp_path))
    assert open(run_sh2).read() == ""


def test_perk_sandbox_tier_requires_both_names():
    """A missing skill OR a missing perk short-circuits to None (undeclared -> operator floor) — neither may
    reach the registry path join (a None name would raise, not refuse). Pins the `not skill or not perk` guard."""
    from infra.govern.delegate import perk_sandbox_tier
    assert perk_sandbox_tier(None, "read") is None
    assert perk_sandbox_tier("cws-fs", None) is None
    assert perk_sandbox_tier(None, None) is None


def test_materialize_workspace_stages_exactly_the_pinned_closure_set(tmp_path, monkeypatch):
    """Staging must reproduce EXACTLY the set skill_index pins into snippet_shas (recursive, same excludes),
    because exod's closure_decision refuses BOTH a pinned member missing from snip AND a staged member the
    pin never covered. So: subdir files ARE staged (a flat copy fail-closed a bundled example tree), and the
    same members skill_index drops — __pycache__/*.pyc, .DS_Store — are NOT staged (stale bytecode / an
    unpinned smuggled sibling). Cross-checked against infra.tool.skill_index._index_files on the same tree."""
    from infra.govern import delegate as d
    from infra.tool import skill_index as si
    src = tmp_path / "chip" / "uni" / "perks" / "extract" / "src"
    (src / "example_src").mkdir(parents=True)
    (src / "__pycache__").mkdir()
    (src / "tool.py").write_text("print('x')\n")
    (src / "example_src" / "service.py").write_text("def f(): pass\n")
    (src / "example_src" / "README.md").write_text("demo\n")
    (src / "__pycache__" / "tool.cpython-39.pyc").write_bytes(b"\x00stale")
    (src / ".DS_Store").write_bytes(b"\x00")
    monkeypatch.setattr(d._reg, "skill_dir", lambda skill, registry=None: str(tmp_path / "chip" / "uni"))
    ws, env, _ = d.materialize_workspace({"run_id": "rec1", "wrapper": "", "skill": "uni",
                                          "perk": "extract"}, str(tmp_path / "work"))
    snip = env["SNIP"]
    staged = {os.path.relpath(os.path.join(b, f), snip)
              for b, _dd, ff in os.walk(snip) for f in ff}
    pinned = {os.path.relpath(ap, str(src)) for ap in si.skill_files(str(src)).values()}
    assert staged == pinned, (staged, pinned)
    assert "example_src/service.py" in staged and "tool.py" in staged
    assert not any(".pyc" in s or "__pycache__" in s or ".DS_Store" in s for s in staged)
