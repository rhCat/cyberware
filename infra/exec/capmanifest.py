#!/usr/bin/env python3
"""infra/exec/capmanifest.py — capability manifest enforcement (P2-T06).

A CapabilityManifest is the DECLARED grant of a sandbox: exactly which host paths are readable, the one
writable workspace, and whether the network is reachable. `materialize` turns a manifest into a
SandboxProfile; `verify_materialized` proves the profile the sandbox will actually run matches the manifest
EXACTLY — the bwrap command mounts the declared binds, no more and no fewer. A divergence (an extra bind the
manifest never granted, a declared bind the sandbox dropped, a network flag flip) is REFUSED, so a tampered
or buggy profile can never silently widen a step's reach beyond what was authorized.

The fixed hardening of the core profile (the masked /proc paths, the fresh /proc + /dev, the unshared
namespaces) is NOT a capability — it is applied to every sandbox and is excluded from the comparison; only
the granted binds + the network are matched against the manifest.
"""
from __future__ import annotations
import dataclasses
import os

from infra.exec.sandbox import SandboxProfile, _CORE_RO


@dataclasses.dataclass(frozen=True)
class CapabilityManifest:
    """The declared capabilities of a sandbox: the readable system tree, the writable workspace, the
    network. The defaults ARE the spine core grant (read-only system, no network)."""
    workspace: str
    ro_binds: tuple = _CORE_RO
    network: bool = False


def materialize(manifest: CapabilityManifest) -> SandboxProfile:
    """Build the SandboxProfile that grants EXACTLY this manifest — only the declared binds + network."""
    return SandboxProfile(workspace=manifest.workspace, ro_binds=manifest.ro_binds, network=manifest.network)


def declared_mounts(manifest: CapabilityManifest) -> set:
    """The (path, mode) capability set the manifest grants — the existing ro binds + the rw workspace."""
    mounts = {(manifest.workspace, "rw")}
    for p in manifest.ro_binds:
        if os.path.exists(p):
            mounts.add((p, "ro"))
    return mounts


def materialized_mounts(profile: SandboxProfile) -> set:
    """The (path, mode) CAPABILITY binds the profile's bwrap command actually materializes — the binds where
    source == destination, excluding the fixed /proc hardening masks (which are not capabilities)."""
    argv = profile.bwrap_argv(["true"])
    out, i = set(), 0
    while i < len(argv) - 2:
        flag = argv[i]
        if flag in ("--ro-bind", "--ro-bind-try", "--bind"):
            src, dst = argv[i + 1], argv[i + 2]
            if src == dst and not dst.startswith("/proc") and src != "/dev/null":
                out.add((dst, "rw" if flag == "--bind" else "ro"))
            i += 3
        else:
            i += 1
    return out


def verify_materialized(profile: SandboxProfile, manifest: CapabilityManifest):
    """Returns (ok, reason). The sandbox's materialized capability binds must EXACTLY equal the manifest's
    declared grant, and the network flag must match. Any divergence refuses."""
    declared, actual = declared_mounts(manifest), materialized_mounts(profile)
    extra = actual - declared
    missing = declared - actual
    if extra:
        return False, "ungranted_bind"          # the sandbox mounts something the manifest never granted
    if missing:
        return False, "dropped_bind"             # the sandbox dropped a bind the manifest declared
    if profile.network != manifest.network:
        return False, "network_mismatch"
    return True, "ok"


def materialize_checked(manifest: CapabilityManifest) -> SandboxProfile:
    """Materialize a manifest and self-verify the result matches it exactly. Raises if the materialization
    diverges from the declared grant — a sandbox is never run unless it provably equals its manifest."""
    profile = materialize(manifest)
    ok, reason = verify_materialized(profile, manifest)
    if not ok:
        raise ValueError(f"sandbox does not match its capability manifest: {reason}")
    return profile
