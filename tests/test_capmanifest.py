"""Capability manifest enforcement (P2-T06): the sandbox must materialize its manifest EXACTLY, and any
divergence (an ungranted bind, a dropped bind, a flipped network) must refuse. Pure argv/set logic — runs
everywhere (the bwrap RUN of a materialized manifest is covered by the sandbox/redteam suites)."""
from __future__ import annotations

from infra.exec.capmanifest import (CapabilityManifest, materialize, materialize_checked,
                                     materialized_mounts, verify_materialized)


def test_materialized_exactly_is_accepted(tmp_path):
    m = CapabilityManifest(workspace=str(tmp_path), ro_binds=("/usr", "/bin"))
    assert verify_materialized(materialize(m), m) == (True, "ok")


def test_an_ungranted_bind_is_refused(tmp_path):
    granted = CapabilityManifest(workspace=str(tmp_path), ro_binds=("/usr", "/bin"))
    wider = materialize(CapabilityManifest(workspace=str(tmp_path), ro_binds=("/usr", "/bin", "/etc")))
    assert verify_materialized(wider, granted) == (False, "ungranted_bind")   # /etc was never granted


def test_a_dropped_bind_is_refused(tmp_path):
    granted = CapabilityManifest(workspace=str(tmp_path), ro_binds=("/usr", "/bin", "/etc"))
    narrower = materialize(CapabilityManifest(workspace=str(tmp_path), ro_binds=("/usr", "/bin")))
    assert verify_materialized(narrower, granted) == (False, "dropped_bind")


def test_a_network_flip_is_refused(tmp_path):
    m = CapabilityManifest(workspace=str(tmp_path), ro_binds=("/usr",), network=False)
    opened = materialize(CapabilityManifest(workspace=str(tmp_path), ro_binds=("/usr",), network=True))
    assert verify_materialized(opened, m) == (False, "network_mismatch")


def test_the_workspace_is_the_only_writable_mount(tmp_path):
    m = CapabilityManifest(workspace=str(tmp_path), ro_binds=("/usr", "/bin"))
    rw = [p for p, mode in materialized_mounts(materialize(m)) if mode == "rw"]
    assert rw == [str(tmp_path)]


def test_materialize_checked_returns_a_faithful_profile(tmp_path):
    m = CapabilityManifest(workspace=str(tmp_path), ro_binds=("/usr",))
    p = materialize_checked(m)                                  # faithful materialization never raises
    assert p.workspace == str(tmp_path) and p.ro_binds == ("/usr",)


def test_redteam_cap_mismatch_attack_holds():
    # the cws-redteam cap-mismatch behaviour (P2-T06 evidence) — pure logic, runs everywhere
    from infra.exec import redteam
    out = redteam.run_attack("cap-mismatch")
    assert out.held and out.family == "capability", out.detail
