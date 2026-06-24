"""P2-T04 — the SandboxProfile community tier: gVisor (runsc) behind the SAME value-free driver as bwrap, and
the community no-secrets floor. The gVisor backend must enforce the SAME confinement as bwrap (it may never
weaken it); the community tier may never request secrets. The LIVE corpus under each backend is host-gated
(bwrap=is_available, runsc=runsc_available); these tests prove the PURE seam + the tier everywhere."""
from infra.exec import capmanifest as cm
from infra.exec import sandbox


def test_seam_selftest_all_pass():
    r = sandbox.community_tier_selftest()
    # bwrap_live / runsc_live are informational host gates (False off Linux); `ok` covers the real properties
    assert r["ok"] is True, r
    assert r["seam_parity"] and r["gvisor_no_weaken"] and r["network_grant_tracks"] and r["no_secrets_tier"]


def test_gvisor_renders_the_same_confinement_as_bwrap():
    """The two backends are seam-equivalent: identical capability binds, net isolation, uid/gid, dropped caps,
    no-new-privs, masked proc, readonly rootfs — for several profiles."""
    for p in (sandbox.core_profile("/ws"), sandbox.core_profile("/ws", network=True),
              sandbox.SandboxProfile(workspace="/ws", ro_binds=("/usr", "/etc"))):
        assert sandbox.confinement(p, "bwrap") == sandbox.confinement(p, "runsc")


def test_gvisor_oci_spec_does_not_weaken_the_boundary():
    spec = sandbox.oci_config(sandbox.core_profile("/ws"), ["true"])
    assert spec["root"]["readonly"] is True
    assert spec["process"]["capabilities"]["bounding"] == []            # all caps dropped
    assert spec["process"]["noNewPrivileges"] is True
    assert spec["process"]["user"]["uid"] == 65534 and spec["process"]["user"]["gid"] == 65534
    assert any(n["type"] == "network" for n in spec["linux"]["namespaces"])   # net unshared (no grant)
    # no raw block device is mounted
    assert not any(m.get("destination", "").startswith("/dev/") and m.get("destination") != "/dev/null"
                   for m in spec["mounts"] if m.get("type") == "bind")


def test_network_grant_tracks_in_both_backends():
    netp = sandbox.core_profile("/ws", network=True)
    assert sandbox.confinement(netp, "bwrap")["net_isolated"] is False
    assert sandbox.confinement(netp, "runsc")["net_isolated"] is False
    nop = sandbox.core_profile("/ws")
    assert sandbox.confinement(nop, "bwrap")["net_isolated"] is True
    assert sandbox.confinement(nop, "runsc")["net_isolated"] is True


def test_capability_mounts_parity_lets_one_check_verify_either_backend(tmp_path):
    """The same exact-match manifest check works for the gVisor backend — it grants precisely the manifest."""
    ws = str(tmp_path)
    man = cm.CapabilityManifest(workspace=ws, ro_binds=("/usr", "/etc"))
    prof = cm.materialize(man)
    assert sandbox.capability_mounts(prof, "bwrap") == sandbox.capability_mounts(prof, "runsc")
    assert sandbox.capability_mounts(prof, "runsc") == cm.declared_mounts(man)


def test_community_tier_cannot_request_secrets(tmp_path):
    ws = str(tmp_path)
    assert cm.community_no_secrets(cm.CapabilityManifest(workspace=ws))[0] is True
    ok, reason = cm.community_no_secrets(cm.CapabilityManifest(workspace=ws, credentials=("api_key",)))
    assert ok is False and reason == "community_tier_cannot_request_secrets"
    # trusted tier may name secrets
    assert cm.community_no_secrets(cm.CapabilityManifest(workspace=ws, tier="trusted",
                                                         credentials=("api_key",)))[0] is True


def test_community_no_secrets_is_a_schema_property_too(tmp_path):
    ws = str(tmp_path)
    assert cm.validate_manifest_schema({"workspace": ws})[0] is True
    ok, reason = cm.validate_manifest_schema({"workspace": ws, "tier": "community", "credentials": ["k"]})
    assert ok is False and reason == "community_tier_cannot_request_secrets"
    assert cm.validate_manifest_schema({"workspace": ws, "tier": "bogus"})[0] is False


def test_materialize_checked_refuses_a_community_secret_request(tmp_path):
    import pytest
    with pytest.raises(ValueError, match="tier policy"):
        cm.materialize_checked(cm.CapabilityManifest(workspace=str(tmp_path), credentials=("api_key",)))


def test_run_confined_refuses_runsc_when_unavailable(tmp_path):
    """Off a runsc host, the gVisor backend REFUSES rather than running unconfined (never silent)."""
    import pytest
    if sandbox.runsc_available():
        pytest.skip("runsc present — the refusal path is for hosts without it")
    with pytest.raises(RuntimeError, match="gVisor sandbox unavailable"):
        sandbox.run_confined(sandbox.core_profile(str(tmp_path)), ["true"], backend="runsc")
