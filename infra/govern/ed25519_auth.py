#!/usr/bin/env python3
"""infra/govern/ed25519_auth.py — offline, issuer-free identity for the auth seam.

A verifier for `principals.register_verifier` that authenticates a PERSON (or an agent) by an Ed25519
signature instead of a bearer secret. It exists because the fleet is tailnet-scoped and deliberately
dependency-free: an OIDC/OAuth verifier can check a token offline, but *obtaining* one needs the internet
and the IdP up, and shortening token lifetimes to tighten revocation makes that dependency worse. This has
neither problem — no issuer, no JWKS, no network, in either direction.

THE SHAPE. The bearer is a self-contained, short-lived ASSERTION: a DSSE envelope (the same
`infra.cwp.sign` surface that signs grants and exod results — no new crypto) over

    {"pub": "<hex raw ed25519 public key>", "iat": <unix>, "exp": <unix>, "nonce": "<random>"}

base64url-encoded so it fits an `Authorization: Bearer` header. Verification is self-contained: the
assertion carries the public key, the signature is checked AGAINST THAT KEY, and the verifier returns
`sign.keyid(pub)` — `"ed25519:<16 hex>"` — as the SUBJECT.

That is not circular, and the distinction matters: anyone can mint a well-formed assertion with a key they
generated, and it will verify. What they cannot do is make it resolve to a principal — `resolve_principal`
maps a subject to a principal only if some entry in the registry DECLARES that exact subject:

    "alice": {"subject": "ed25519:9f2c…", "acl": {...}}

So the signature proves possession of a key, and the mounted registry decides whether that key is anybody.
Revocation is deleting the line — instant, offline, on a file already bind-mounted read-only into every node,
with no expiry window to wait out and no issuer to consult.

REPLAY. An assertion is bearer-shaped: whoever holds it can present it until `exp`. Two bounded defences —
a short TTL, and a nonce cache that refuses any nonce seen twice inside its own validity window. The cache is
per-process and self-pruning; it does not need to persist, because an entry can only be replayed while the
assertion is still valid, and a restart shortens rather than extends that window.

CLOCK SKEW is a fail-closed input, not an afterthought: an assertion from the future is refused beyond
`_SKEW`, so a client with a wildly wrong clock cannot mint a long-lived credential by post-dating `exp`.
"""
from __future__ import annotations

import base64
import json
import secrets
import time

from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey, Ed25519PublicKey

from infra.cwp import sign as _sign

PAYLOAD_TYPE = "application/cwp-auth+json"

_SKEW = 60                 # seconds of tolerated clock skew, both directions
_MAX_TTL = 15 * 60         # ceiling on an assertion's own claimed lifetime — a client cannot mint a long one
_DEFAULT_TTL = 300
_NONCE_CACHE_MAX = 4096    # bounded; entries self-expire at their assertion's exp


def _b64u(b: bytes) -> str:
    return base64.urlsafe_b64encode(b).decode().rstrip("=")


def _unb64u(s: str) -> bytes:
    return base64.urlsafe_b64decode(s + "=" * (-len(s) % 4))


def mint_assertion(private_key: Ed25519PrivateKey, *, ttl: int = _DEFAULT_TTL, now: int = None) -> str:
    """Produce a bearer assertion for `private_key`. Client-side helper — govd never calls this."""
    now = int(now if now is not None else time.time())
    ttl = max(1, min(int(ttl), _MAX_TTL))
    body = {"pub": _sign.public_raw(private_key).hex(), "iat": now, "exp": now + ttl,
            "nonce": secrets.token_urlsafe(12)}
    env = _sign.sign(body, private_key, payload_type=PAYLOAD_TYPE)
    return _b64u(json.dumps(env, separators=(",", ":"), sort_keys=True).encode())


class Verifier:
    """A `bearer -> subject|None` callable for principals.register_verifier.

    EVERY failure path returns None. It never raises and never distinguishes *why* to the caller: a caller
    that could tell "bad signature" from "expired" from "replayed" would leak an oracle, and govd's answer
    is 401 either way.
    """

    def __init__(self, *, skew: int = _SKEW, max_ttl: int = _MAX_TTL, cache_max: int = _NONCE_CACHE_MAX):
        self.skew, self.max_ttl, self.cache_max = int(skew), int(max_ttl), int(cache_max)
        self._seen: dict = {}                                    # nonce -> exp

    def _replayed(self, nonce: str, exp: int, now: int) -> bool:
        """True iff this nonce was already spent inside its own validity window. Prunes as it goes."""
        if len(self._seen) >= self.cache_max:                    # prune expired first; only then refuse
            for k, e in [(k, e) for k, e in self._seen.items() if e <= now]:
                self._seen.pop(k, None)
            if len(self._seen) >= self.cache_max:
                return True                                      # cache full of LIVE nonces -> fail CLOSED
        if self._seen.get(nonce, 0) > now:
            return True
        self._seen[nonce] = exp
        return False

    def __call__(self, bearer: str, *, now: int = None):
        now = int(now if now is not None else time.time())
        try:
            env = json.loads(_unb64u(str(bearer)).decode())
            if not isinstance(env, dict):
                return None
            body = json.loads(_unb64u(env["payload"]).decode()) if isinstance(env.get("payload"), str) \
                else env.get("payload")
            if not isinstance(body, dict):
                return None
            pub_hex, iat, exp = body.get("pub"), int(body.get("iat", 0)), int(body.get("exp", 0))
            nonce = str(body.get("nonce") or "")
            if not pub_hex or not nonce:
                return None
            pub_raw = bytes.fromhex(str(pub_hex))
            if len(pub_raw) != 32:                               # not an ed25519 public key
                return None
            if exp <= now or exp - iat > self.max_ttl:           # expired, or claims a lifetime past the ceiling
                return None
            if iat > now + self.skew:                            # minted in the future -> refuse
                return None
            if not _sign.verify(env, Ed25519PublicKey.from_public_bytes(pub_raw)):
                return None
            if self._replayed(nonce, exp, now):
                return None
            return _sign.keyid(pub_raw)                          # "ed25519:<16 hex>" == the declared `subject`
        except Exception:
            return None                                          # malformed / undecodable / anything at all


def install(name: str = "ed25519", **kw) -> Verifier:
    """Register a verifier under `name` and return it (so a caller can inspect or reset it in tests)."""
    from infra.govern import principals
    v = Verifier(**kw)
    principals.register_verifier(name, v)
    return v


def subject_for(public_raw: bytes) -> str:
    """The `subject` string to put in principals.json for this public key."""
    return _sign.keyid(public_raw)
