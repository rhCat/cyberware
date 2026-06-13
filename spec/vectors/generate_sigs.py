#!/usr/bin/env python3
"""Generate spec/vectors/signatures.json — the DSSE/Ed25519 signature vectors (the "signatures" coverage
of P0-T07). Produced with infra/cwp/sign.py over a DETERMINISTIC key, so the cross-language harness can
confirm the Go verifier reproduces every sig verdict (Ed25519 is deterministic — same key + payload →
same signature in any conformant impl).

Each vector: {name, pubkey (b64 raw), envelope, expect_valid}. Includes valid signatures, a
tampered-payload, a tampered-signature, and a wrong-key case — so the verdict must DISCRIMINATE.

  python3 spec/vectors/generate_sigs.py        # writes spec/vectors/signatures.json
"""
from __future__ import annotations
import base64
import json
import os

from infra.cwp import sign

HERE = os.path.dirname(os.path.abspath(__file__))
PRIV = sign.keygen_from_seed(bytes(range(32)))
OTHER = sign.keygen_from_seed(bytes(range(1, 33)))
PUB_B64 = base64.b64encode(sign.public_raw(PRIV)).decode()
OTHER_PUB_B64 = base64.b64encode(sign.public_raw(OTHER)).decode()


def _flip_first_sig(env):
    env = json.loads(json.dumps(env))
    raw = bytearray(base64.b64decode(env["signatures"][0]["sig"]))
    raw[0] ^= 0xFF
    env["signatures"][0]["sig"] = base64.b64encode(bytes(raw)).decode()
    return env


def vectors():
    v = []
    for name, body in [("obj", {"a": 1, "b": 2}), ("array", [1, 2, 3]), ("unicode", {"€": "✓"}),
                       ("record", {"seq": 1, "task_id": "P0-T12", "verdict": "pass"}),
                       ("nested", {"k": [True, None, {"z": 1}]})]:
        v.append({"name": f"sig_{name}", "pubkey": PUB_B64, "envelope": sign.sign(body, PRIV), "expect_valid": True})
    # negatives — the verdict must say False
    v.append({"name": "sig_tampered_payload", "pubkey": PUB_B64,
              "envelope": {**sign.sign({"x": 1}, PRIV), "payload": base64.b64encode(b'{"x":2}').decode()},
              "expect_valid": False})
    v.append({"name": "sig_tampered_signature", "pubkey": PUB_B64,
              "envelope": _flip_first_sig(sign.sign({"y": 1}, PRIV)), "expect_valid": False})
    v.append({"name": "sig_wrong_key", "pubkey": OTHER_PUB_B64,
              "envelope": sign.sign({"z": 1}, PRIV), "expect_valid": False})
    return v


def main():
    out = os.path.join(HERE, "signatures.json")
    with open(out, "w") as f:
        json.dump(vectors(), f, ensure_ascii=False, indent=2)
        f.write("\n")
    print(f"wrote {len(vectors())} signature vectors → {out}")


if __name__ == "__main__":
    main()
