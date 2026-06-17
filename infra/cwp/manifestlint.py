#!/usr/bin/env python3
"""infra/cwp/manifestlint.py — publish-time manifest lint (P3-T10, SV-4).

Before a skill is published, what it ACTUALLY does must match what it DECLARES. A perk declares its binary
dependencies (`requires`), its network egress (an `egress` allowlist), and its sandbox capabilities (the
capability manifest). This lint extracts what the perk's porter scripts and capability manifest actually use
and refuses to publish on any of three drifts:

  * **undeclared binary** — a command invoked in a porter script that is not in `requires`,
  * **undeclared egress** — a network destination reached that is not in the egress allowlist,
  * **capability mismatch** — a sandbox mount/capability the manifest does not grant.

A perk whose observed behaviour exceeds its declaration is exactly how a benign-looking skill smuggles in a
binary, a callback host, or a writable path — so the gate must catch 100% of these at publish time.
"""
from __future__ import annotations
import os
import re

# shell builtins / harness words that are not a perk's own binary dependency surface
_HARNESS_BINS = {"bash", "sh", "set", "cd", "pwd", "dirname", "source", ".", "echo", "then", "else", "fi",
                 "do", "done", "if", "for", "while", "return", "local", "export", "true", "false"}
# wrapper words that PRECEDE the real binary — the token after them is what actually runs
_WRAPPERS = {"exec", "command", "sudo", "env", "nohup", "time", "xargs"}
_NET_BINS = ("curl", "wget", "nc", "ncat", "ssh", "scp", "rsync")
# a command at the start of a line or after a pipe/and/semicolon (best-effort static extraction)
_CMD_RE = re.compile(r"(?:^|[|;&]|\$\()\s*((?:[a-zA-Z_][\w./-]*\s+)*[a-zA-Z_][\w./-]*)", re.MULTILINE)
_URL_RE = re.compile(r"https?://([A-Za-z0-9.\-]+)")


def _resolve_binary(tokens) -> str:
    """Given the leading tokens of a command, skip wrapper words (exec/sudo/env/…) and return the real
    binary name (basename), or '' if there isn't one."""
    for tok in tokens:
        name = tok.split("/")[-1]
        if name in _WRAPPERS:
            continue
        return name
    return ""


def observed_binaries(script_text: str) -> set:
    """Best-effort set of binaries a porter script invokes (skipping wrapper words like `exec` and harness
    builtins). `exec python3 …` resolves to `python3`, not `exec`."""
    bins = set()
    for m in _CMD_RE.finditer(script_text):
        name = _resolve_binary(m.group(1).split())
        if name and name not in _HARNESS_BINS and not name.isupper():
            bins.add(name)
    return bins


def observed_egress(script_text: str) -> set:
    """Network destinations the script reaches: hosts behind http(s):// and hosts passed to net binaries
    (parsing the host out of a URL argument, and ignoring flags / the URL scheme itself)."""
    hosts = set(_URL_RE.findall(script_text))
    for nb in _NET_BINS:
        for m in re.finditer(rf"\b{nb}\b\s+(\S+)", script_text):
            arg = m.group(1)
            if arg.startswith("-"):
                continue
            url_hosts = _URL_RE.findall(arg)
            if url_hosts:
                hosts.update(url_hosts)
            elif "//" not in arg:                              # a bare host:port / host, not a scheme token
                hosts.add(arg.split(":")[0])
    return hosts


def lint_manifest(declared: dict, observed: dict) -> dict:
    """Compare declared vs observed across the three surfaces. Returns {defects:[{type,item}], clean}.
    `declared`/`observed` carry sets under keys `binaries`, `egress`, `capabilities`."""
    defects = []
    for surface, dtype in (("binaries", "undeclared_binary"), ("egress", "undeclared_egress"),
                           ("capabilities", "capability_mismatch")):
        extra = set(observed.get(surface, set())) - set(declared.get(surface, set()))
        for item in sorted(extra):
            defects.append({"type": dtype, "item": item})
    return {"defects": defects, "clean": not defects}


def extract_observed(perk_dir: str) -> dict:
    """Extract the observed surfaces from a perk on disk: binaries + egress from its porter scripts, and the
    capability set from a capability manifest if one is present (`capmanifest.json`)."""
    import json
    bins, egress, caps = set(), set(), set()
    src = os.path.join(perk_dir, "src")
    if os.path.isdir(src):
        for fn in os.listdir(src):
            if fn.endswith(".sh"):
                txt = open(os.path.join(src, fn)).read()
                bins |= observed_binaries(txt)
                egress |= observed_egress(txt)
    capf = os.path.join(perk_dir, "capmanifest.json")
    if os.path.isfile(capf):
        caps = set(json.load(open(capf)).get("capabilities", []))
    return {"binaries": bins, "egress": egress, "capabilities": caps}


def manifest_selftest() -> dict:
    """A hermetic P3-T10 demonstration: a clean perk (observed ⊆ declared) passes with zero defects; then
    seed EACH of the three defect classes — an undeclared binary, an undeclared egress host, a capability
    the manifest does not grant — and confirm 100% are caught (one defect each, of the right type). `ok` iff
    the clean case is clean and all three seeded defects are detected."""
    declared = {"binaries": {"python3", "openssl"}, "egress": {"rekor.example"},
                "capabilities": {"ro:/usr", "rw:/work"}}

    clean = lint_manifest(declared, {"binaries": {"python3"}, "egress": set(),
                                     "capabilities": {"ro:/usr"}})
    clean_ok = clean["clean"]

    seeds = {
        "undeclared_binary": {**{k: set(v) for k, v in declared.items()}, "binaries": {"python3", "nc"}},
        "undeclared_egress": {**{k: set(v) for k, v in declared.items()}, "egress": {"evil.example"}},
        "capability_mismatch": {**{k: set(v) for k, v in declared.items()},
                                "capabilities": {"ro:/usr", "rw:/work", "rw:/etc"}},
    }
    caught = {}
    for dtype, observed in seeds.items():
        rep = lint_manifest(declared, observed)
        caught[dtype] = (not rep["clean"]) and any(d["type"] == dtype for d in rep["defects"])

    detection_rate = sum(caught.values()) / len(caught)
    return {"clean_perk_passes": clean_ok, "caught": caught, "seeded_defects_caught_pct": detection_rate,
            "ok": clean_ok and detection_rate == 1.0}
