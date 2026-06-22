"""P3-T16 — the SECURITY.md doorbell (infra/govern/doorbell.py): contact + key + ack SLA must all be present.

Pins each field so the live SECURITY.md satisfies the doorbell and any missing field fails it."""
from __future__ import annotations

from infra.govern import doorbell


def test_live_security_md_passes_the_doorbell():
    r = doorbell.doorbell_selftest()
    assert r["exists"] and r["ok"], r              # the committed SECURITY.md is a real doorbell


def test_all_three_fields_required():
    full = ("Email security@example.com. Use our age public key or PGP. "
            "We acknowledge within 72 hours.")
    assert doorbell.check_doorbell(full)["ok"] is True
    assert doorbell.check_doorbell("age public key; acknowledge within 24 hours")["contact"] is False   # no addr
    assert doorbell.check_doorbell("Email a@b.co; acknowledge within 24 hours")["key"] is False          # no key
    assert doorbell.check_doorbell("Email a@b.co; PGP key")["ack_sla"] is False                          # no SLA window


def test_sla_needs_both_a_window_and_a_commitment():
    assert doorbell.check_doorbell("a@b.co PGP; we respond within 48 hours")["ack_sla"] is True
    assert doorbell.check_doorbell("a@b.co PGP; 48 hours of fun")["ack_sla"] is False    # window, no commitment
    assert doorbell.check_doorbell("a@b.co PGP; we acknowledge promptly")["ack_sla"] is False  # commitment, no window


def test_github_private_reporting_counts_as_contact():
    text = "Use GitHub Security → Report a vulnerability (encrypted). We acknowledge within 72 hours."
    r = doorbell.check_doorbell(text)
    assert r["contact"] and r["key"] and r["ack_sla"] and r["ok"]


def test_missing_file_is_not_ok(tmp_path):
    r = doorbell.doorbell_selftest(root=str(tmp_path))   # no SECURITY.md here
    assert r["exists"] is False and r["ok"] is False
