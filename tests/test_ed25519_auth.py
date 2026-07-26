#!/usr/bin/env python3
"""Tests for infra/govern/ed25519_auth.py — the offline, issuer-free identity verifier.

Every case here is an IDENTITY decision, so each asserts a fail-CLOSED outcome explicitly. The property
that matters most is the last one: a cryptographically VALID assertion from a key nobody declared must
resolve to nobody. Possession of a key proves possession of a key; the mounted registry decides whether
that key is anyone.
"""
from __future__ import annotations

import json
import time

import pytest
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

from infra.govern import ed25519_auth as EA
from infra.govern import principals as P


@pytest.fixture()
def key():
    return Ed25519PrivateKey.generate()


@pytest.fixture()
def verifier():
    return EA.Verifier()


def _reg(key, name="alice"):
    return {name: {"subject": EA.subject_for(EA._sign.public_raw(key)), "acl": {}},
            "bot": {"token_sha": P.token_sha("s3cret")}}


# ───────────────────────── the happy path ─────────────────────────

def test_valid_assertion_resolves_to_the_declaring_principal(key):
    EA.install("t_ed", )
    assert P.resolve_principal(EA.mint_assertion(key), _reg(key), "t_ed") == "alice"


def test_subject_is_the_stable_keyid(key):
    pub = EA._sign.public_raw(key)
    assert EA.subject_for(pub) == EA._sign.keyid(pub)
    assert EA.subject_for(pub).startswith("ed25519:")


# ───────────────────────── fail-closed ─────────────────────────

def test_valid_signature_from_an_UNDECLARED_key_is_nobody(key, verifier):
    """THE property. A stranger can mint a perfectly valid assertion with their own key — and it must
    resolve to no principal, because the registry never declared that subject."""
    stranger = Ed25519PrivateKey.generate()
    a = EA.mint_assertion(stranger)
    # the assertion verifies on its own terms — the signature IS valid
    assert verifier(a) == EA.subject_for(EA._sign.public_raw(stranger))
    # …and resolves to NO principal, because the registry declares only alice's key
    EA.install("t_ed2")
    assert P.resolve_principal(a, _reg(key), "t_ed2") is None


def test_undeclared_key_resolves_to_nobody_through_the_seam(key):
    EA.install("t_ed3")
    stranger = Ed25519PrivateKey.generate()
    assert P.resolve_principal(EA.mint_assertion(stranger), _reg(key), "t_ed3") is None


@pytest.mark.parametrize("bearer", ["", "garbage", "!!!not-base64!!!", "e30", "null"])
def test_malformed_bearers_are_refused(verifier, bearer):
    assert verifier(bearer) is None


def test_expired_assertion_refused(key, verifier):
    assert verifier(EA.mint_assertion(key, ttl=1, now=int(time.time()) - 100)) is None


def test_future_dated_assertion_refused(key, verifier):
    # a client with a wrong (or lying) clock must not be able to post-date its way to a long credential
    assert verifier(EA.mint_assertion(key, now=int(time.time()) + 9999)) is None


def test_minter_clamps_ttl_to_the_ceiling(key, verifier):
    a = EA.mint_assertion(key, ttl=99999)
    env = json.loads(EA._unb64u(a).decode())
    body = json.loads(EA._unb64u(env["payload"]).decode())
    assert body["exp"] - body["iat"] <= EA._MAX_TTL
    assert verifier(a) is not None


def test_oversized_ttl_in_a_HAND_ROLLED_assertion_refused(key, verifier):
    """The minter clamps, but the verifier must not TRUST the minter — a hand-rolled assertion claiming a
    year-long lifetime is refused on its own terms."""
    now = int(time.time())
    body = {"pub": EA._sign.public_raw(key).hex(), "iat": now, "exp": now + 365 * 24 * 3600, "nonce": "x1"}
    env = EA._sign.sign(body, key, payload_type=EA.PAYLOAD_TYPE)
    assert verifier(EA._b64u(json.dumps(env, separators=(",", ":"), sort_keys=True).encode())) is None


def test_tampered_payload_refused(key, verifier):
    """Swapping the embedded pubkey invalidates the signature — the assertion is self-verifying."""
    other = Ed25519PrivateKey.generate()
    env = json.loads(EA._unb64u(EA.mint_assertion(key)).decode())
    body = json.loads(EA._unb64u(env["payload"]).decode())
    body["pub"] = EA._sign.public_raw(other).hex()
    env["payload"] = EA._b64u(json.dumps(body, separators=(",", ":"), sort_keys=True).encode())
    assert verifier(EA._b64u(json.dumps(env, separators=(",", ":"), sort_keys=True).encode())) is None


def test_non_ed25519_pubkey_length_refused(key, verifier):
    now = int(time.time())
    body = {"pub": "aa" * 16, "iat": now, "exp": now + 60, "nonce": "n"}   # 16 bytes, not 32
    env = EA._sign.sign(body, key, payload_type=EA.PAYLOAD_TYPE)
    assert verifier(EA._b64u(json.dumps(env, separators=(",", ":"), sort_keys=True).encode())) is None


# ───────────────────────── replay ─────────────────────────

def test_replay_within_the_validity_window_refused(key, verifier):
    a = EA.mint_assertion(key)
    assert verifier(a) is not None
    assert verifier(a) is None, "a spent nonce must not be reusable while still unexpired"


def test_distinct_assertions_both_accepted(key, verifier):
    assert verifier(EA.mint_assertion(key)) is not None
    assert verifier(EA.mint_assertion(key)) is not None   # different nonce


def test_nonce_cache_prunes_expired_and_stays_bounded(key):
    v = EA.Verifier(cache_max=8)
    now = int(time.time())
    for _ in range(20):                                    # far more than cache_max, all short-lived
        assert v(EA.mint_assertion(key, ttl=1, now=now), now=now) is not None
        now += 2                                           # each expires before the next
    assert len(v._seen) <= 8


def test_cache_full_of_LIVE_nonces_fails_closed(key):
    v = EA.Verifier(cache_max=2)
    now = int(time.time())
    assert v(EA.mint_assertion(key, ttl=600, now=now), now=now) is not None
    assert v(EA.mint_assertion(key, ttl=600, now=now), now=now) is not None
    # cache is full and nothing is prunable — refuse rather than evict a live nonce and permit a replay
    assert v(EA.mint_assertion(key, ttl=600, now=now), now=now) is None


# ───────────────────────── the seam contract ─────────────────────────

def test_verifier_never_raises(verifier):
    for junk in (None, 123, b"bytes", {"a": 1}, "\x00\xff"):
        assert verifier(junk) is None


def test_bearer_secret_does_not_authenticate_under_this_scheme(key):
    EA.install("t_ed4")
    assert P.resolve_principal("s3cret", _reg(key), "t_ed4") is None
