"""The dispute lifecycle for SV-6 (P6-T12): bond → m-of-n WebAuthn resolution → clawback/forfeit + reputation,
all ledgered and zero-sum. Fewer than m distinct valid approvals does not resolve; a tampered approval does
not count. Pure Python (Ed25519 via cryptography)."""
from __future__ import annotations

from infra.settle import disputes as D


def test_selftest():
    r = D.dispute_selftest()
    assert r["ok"], r


def test_m_of_n_and_clawback():
    r = D.dispute_selftest()
    assert r["bond_posted_and_upheld_clawback"] and r["insufficient_approvals_blocked"]
    assert r["tampered_approval_ignored"] and r["rejected_forfeits_bond"]


def test_quorum_is_not_forgeable_without_registered_keys():
    """The m-of-n arbiter quorum binds to the operator-REGISTERED credential keys: approvals over the correct
    doc signed by throwaway keys (whether reusing real arb_ids or inventing new ones) count ZERO, so a party
    able to submit approvals cannot self-mint a quorum."""
    r = D.dispute_selftest()
    assert r["forged_quorum_blocked"] is True


def _pub(k):
    from cryptography.hazmat.primitives import serialization
    return k.public_key().public_bytes(serialization.Encoding.Raw, serialization.PublicFormat.Raw)


def test_one_key_under_two_ids_counts_once():
    """One physical credential registered under two arb_ids yields ONE vote (dedup by key, not just id), so a
    single signer cannot satisfy a 2-of-n quorum via id aliases."""
    from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
    from infra.cwp import webauthn as W
    k = Ed25519PrivateKey.generate()
    pub = _pub(k)
    arbiters = {"arbA": pub, "arbB": pub}                       # SAME physical key, two registered ids
    doc = {"quote_sha": "q" * 32, "outcome": "upheld", "currency": "USD"}
    a = W.make_assertion(doc, k, D.ORIGIN, D.RP_ID)
    assert D.count_approvals(doc, [("arbA", a), ("arbB", a)], arbiters) == 1


def test_resolve_refuses_a_quorum_doc_with_no_valid_outcome():
    """A genuinely quorum-approved resolution_doc that lacks a valid outcome returns a clean refusal, not a
    KeyError."""
    from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
    from infra.cwp import webauthn as W
    from infra.settle import reward_ledger
    keys = {f"arb{i}": Ed25519PrivateKey.generate() for i in range(2)}
    arbiters = {aid: _pub(k) for aid, k in keys.items()}
    doc = {"quote_sha": "q" * 32, "currency": "USD"}           # 2-of-2 signed, but NO outcome key
    appr = [(aid, W.make_assertion(doc, k, D.ORIGIN, D.RP_ID)) for aid, k in keys.items()]
    r = D.resolve(reward_ledger.open_ledger(), doc, appr, 2, "payee", "disputer", "q" * 32, {}, arbiters)
    assert r == {"resolved": False, "reason": "invalid_outcome", "approvals": 2}
