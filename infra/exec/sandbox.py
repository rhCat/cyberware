#!/usr/bin/env python3
"""infra/exec/sandbox.py — the SandboxProfile driver (P2-T03): the bwrap core profile that is the
spine's KERNEL-enforced execution boundary.

A SandboxProfile is a value-free description of a confinement: which host paths are visible (read-only),
the single workspace that is writable, whether the network is reachable, and which namespaces are
unshared. `run_confined(profile, argv)` renders that into a `bwrap` (bubblewrap) command line and execs
it. There is deliberately NO in-process inspection of argv, of the script, or of what the step does — the
confinement is enforced entirely by the Linux kernel (user / pid / net / ipc / uts / cgroup namespaces plus
the bind mounts). That is the SV-3 promise made literal: turn every software scan OFF and the boundary
still holds, because the boundary IS the kernel. The cws-redteam corpus proves exactly this — each attack
is refused with the in-process scan disabled.

bwrap is Linux-only. `is_available()` reports whether the boundary can actually be enforced on this host;
`run_confined` REFUSES (raises) rather than ever running a step unconfined when it cannot. On a bare-metal
Linux host the unprivileged-userns path needs no elevated privilege; inside a container the host process
needs the namespace privileges the kernel would otherwise mask (see docker/Dockerfile.exec).
"""
from __future__ import annotations
import dataclasses
import os
import shutil
import subprocess
from typing import Mapping, Sequence

BWRAP = "bwrap"

# the read-only system tree the core profile exposes — the minimum a typical step needs to exec a program
# and load its shared libraries, with nothing of it writable. Only the entries that exist are bound.
_CORE_RO = ("/usr", "/bin", "/sbin", "/lib", "/lib32", "/lib64", "/libx32", "/etc")


def is_available() -> bool:
    """True only where the kernel boundary can actually be enforced: a Linux host with bwrap present.
    Everywhere else the sandbox is unavailable and a caller must refuse rather than run unconfined."""
    return os.uname().sysname == "Linux" and shutil.which(BWRAP) is not None


@dataclasses.dataclass(frozen=True)
class SandboxProfile:
    """A value-free confinement description. `workspace` is the one host dir mounted read-write (and the
    step's cwd); everything in `ro_binds` is mounted read-only; the network namespace is unshared unless
    `network` is True. The defaults ARE the spine core profile."""
    workspace: str
    ro_binds: tuple = _CORE_RO
    network: bool = False
    proc: bool = True
    dev: bool = True
    tmpfs: tuple = ("/tmp",)
    clearenv: bool = True
    env: Mapping[str, str] = dataclasses.field(default_factory=lambda:
        {"PATH": "/usr/local/bin:/usr/bin:/bin:/usr/sbin:/sbin"})   # /usr/local/bin FIRST: the slim-image python3 lives there
    hostname: str = "sandbox"
    uid: int = 65534          # bwrap sets up the namespaces as userns-root, then drops the STEP to this
    gid: int = 65534          # unprivileged id ("nobody") before exec — an empty capability set + DAC
    mask_proc: bool = True    # mask the dangerous /proc paths read-only (the runc maskedPaths doctrine)
    cargo: str | None = None  # the ACL-GRANTED shared-cargo bind mode ("ro"|"rw"|None). exod sets this ONLY after
    cargo_path: str = "/cyberware_cargo"   # re-enforcing the cargo axis off-node; None => the dir is NOT bound.

    def bwrap_argv(self, argv: Sequence[str]) -> list[str]:
        """Render this profile + the step's argv into a complete bwrap command line. Pure: it builds the
        list, it does not run anything and it does not look at what `argv` intends to do.

        Mount order matters — bwrap applies operations left to right. The read-only system tree and the
        tmpfs scratch are mounted FIRST, then the writable workspace is bound LAST so that a workspace
        nested under a tmpfs target (e.g. a /tmp/... path) is never shadowed by it."""
        cmd = [BWRAP,
               "--die-with-parent",          # the step dies if the supervising daemon does
               "--new-session",              # detach the controlling tty (blocks TIOCSTI injection)
               "--unshare-user",             # a fresh user namespace: host capabilities do not reach in
               "--unshare-pid",              # the step cannot see or signal host processes
               "--unshare-ipc",              # no shared SysV / POSIX IPC with the host
               "--unshare-uts",              # its own hostname namespace
               "--unshare-cgroup-try",       # its own cgroup view where the kernel supports it
               "--uid", str(self.uid), "--gid", str(self.gid),   # the step runs as nobody, never as root
               "--hostname", self.hostname]
        if not self.network:
            cmd += ["--unshare-net"]          # no network namespace egress: only an isolated loopback
        for p in self.ro_binds:
            if os.path.exists(p):
                cmd += ["--ro-bind", p, p]
        for t in self.tmpfs:
            cmd += ["--tmpfs", t]
        cmd += ["--bind", self.workspace, self.workspace]   # the one writable path — bound LAST
        if self.cargo in ("ro", "rw") and os.path.exists(self.cargo_path):
            # the ACL-granted shared cargo dir: rw => --bind, ro => --ro-bind. Bound only when exod set the mode
            # (after off-node re-enforcement) AND the dir is actually mounted into the body container; absent =>
            # the step simply doesn't see it (fail-safe: no silent widening of what a step can touch).
            cmd += (["--bind", self.cargo_path, self.cargo_path] if self.cargo == "rw"
                    else ["--ro-bind", self.cargo_path, self.cargo_path])
        if self.proc:
            cmd += ["--proc", "/proc"]        # a fresh /proc bound to the new pid namespace
            if self.mask_proc:
                # global kernel knobs are not namespaced: a privileged host (or a --privileged container)
                # could otherwise let even a capability-less step write them. Mask them like a container
                # runtime does — /proc/sys read-only (writes → EROFS), the live-kernel files shadowed by
                # /dev/null — so the refusal is the mount, independent of who holds which capability.
                cmd += ["--ro-bind-try", "/proc/sys", "/proc/sys"]
                # shadow the live-kernel files with /dev/null — but only those this kernel actually exposes
                # (a fresh procfs has exactly what the host procfs has), else bwrap cannot create the target.
                for f in ("/proc/sysrq-trigger", "/proc/kcore", "/proc/kallsyms", "/proc/keys",
                          "/proc/timer_list", "/proc/sched_debug"):
                    if os.path.exists(f):
                        cmd += ["--ro-bind", "/dev/null", f]
        if self.dev:
            cmd += ["--dev", "/dev"]          # a minimal /dev (null/zero/random/...), no raw block devices
        if self.clearenv:
            cmd += ["--clearenv"]
        for k, v in self.env.items():
            cmd += ["--setenv", k, v]
        cmd += ["--chdir", self.workspace, "--"]
        cmd += list(argv)
        return cmd


def core_profile(workspace: str, *, network: bool = False) -> SandboxProfile:
    """The spine sandbox: a read-only system, a single writable workspace, no network, every namespace
    unshared. This is the profile the governed channel drops an untrusted step into."""
    return SandboxProfile(workspace=workspace, network=network)


# ── P2-T04: the community tier — a SECOND backend behind the SAME value-free SandboxProfile ──────────────
# gVisor (runsc) renders the same confinement as an OCI runtime spec (readonly rootfs, all caps dropped,
# no-new-privileges, the network namespace unshared unless granted, the masked /proc paths, ro system binds +
# the one rw workspace). The SandboxProfile is the single source of truth; each backend realizes it. `runsc`
# needs Linux + the runsc binary, so the live corpus under gVisor is gated exactly like bwrap is — the
# rendering is a PURE function provable everywhere; only the exec is host-gated.

RUNSC = "runsc"
_MASKED_PROC = ("/proc/sysrq-trigger", "/proc/kcore", "/proc/kallsyms", "/proc/keys",
                "/proc/timer_list", "/proc/sched_debug")


def runsc_available() -> bool:
    """True only where gVisor can actually confine: a Linux host with the runsc binary present."""
    return os.uname().sysname == "Linux" and shutil.which(RUNSC) is not None


def oci_config(profile: SandboxProfile, argv: Sequence[str]) -> dict:
    """Render this profile + argv into an OCI runtime spec (the gVisor/runc representation of the SAME
    confinement). Pure: it builds the dict, runs nothing. The security invariants mirror bwrap_argv exactly —
    readonly rootfs, every capability dropped, no-new-privileges, the network namespace unshared unless
    granted, the masked /proc paths, the ro system binds + the one rw workspace, the step dropped to nobody."""
    ns = [{"type": "pid"}, {"type": "ipc"}, {"type": "uts"}, {"type": "mount"}, {"type": "user"},
          {"type": "cgroup"}]
    if not profile.network:
        ns.append({"type": "network"})                       # unshare net: no egress (mirrors --unshare-net)
    mounts = []
    for t in profile.tmpfs:
        mounts.append({"destination": t, "type": "tmpfs", "source": "tmpfs",
                       "options": ["nosuid", "nodev", "noexec"]})
    if profile.proc:
        mounts.append({"destination": "/proc", "type": "proc", "source": "proc"})
    for p in profile.ro_binds:
        if os.path.exists(p):
            mounts.append({"destination": p, "type": "bind", "source": p, "options": ["ro", "rbind", "nosuid"]})
    mounts.append({"destination": profile.workspace, "type": "bind", "source": profile.workspace,
                   "options": ["rw", "rbind", "nosuid"]})      # the one writable path
    if profile.cargo in ("ro", "rw") and os.path.exists(profile.cargo_path):
        mounts.append({"destination": profile.cargo_path, "type": "bind", "source": profile.cargo_path,
                       "options": [profile.cargo, "rbind", "nosuid"]})   # ACL-granted shared cargo (mirrors bwrap)
    masked = [f for f in _MASKED_PROC if os.path.exists(f)]
    return {
        "ociVersion": "1.0.2",
        "hostname": profile.hostname,
        "root": {"path": "rootfs", "readonly": True},          # readonly rootfs (the ro system tree)
        "process": {
            "terminal": False,
            "user": {"uid": profile.uid, "gid": profile.gid}, # the step runs as nobody, never root
            "args": list(argv),
            "env": [f"{k}={v}" for k, v in profile.env.items()],
            "cwd": profile.workspace,
            "noNewPrivileges": True,
            "capabilities": {"bounding": [], "effective": [], "permitted": [], "inheritable": [],
                             "ambient": []},                   # drop ALL capabilities
        },
        "mounts": mounts,
        "linux": {
            "namespaces": ns,
            "maskedPaths": masked,
            "readonlyPaths": ["/proc/sys"],                    # writes -> EROFS (mirrors --ro-bind /proc/sys)
            "uidMappings": [{"containerID": profile.uid, "hostID": os.getuid() if hasattr(os, "getuid") else 0,
                             "size": 1}],
            "gidMappings": [{"containerID": profile.gid, "hostID": os.getgid() if hasattr(os, "getgid") else 0,
                             "size": 1}],
        },
    }


def capability_mounts(profile: SandboxProfile, backend: str = "bwrap") -> set:
    """The (path, mode) CAPABILITY binds a backend's rendering actually materializes — source==destination,
    excluding the fixed /proc-hardening masks. Lets the same EXACT-match check (capmanifest) verify either
    backend grants precisely the manifest, no more, no fewer — proving the seam doesn't widen reach."""
    if backend == "runsc":
        out = set()
        for m in oci_config(profile, ["true"])["mounts"]:
            src, dst, opts = m.get("source"), m.get("destination"), m.get("options", [])
            if m.get("type") == "bind" and src == dst and not dst.startswith("/proc"):
                out.add((dst, "ro" if "ro" in opts else "rw"))
        return out
    # bwrap: parse the rendered argv (same logic as capmanifest.materialized_mounts, kept here for both backends)
    argv, out, i = profile.bwrap_argv(["true"]), set(), 0
    while i < len(argv) - 2:
        if argv[i] in ("--ro-bind", "--ro-bind-try", "--bind"):
            src, dst = argv[i + 1], argv[i + 2]
            if src == dst and not dst.startswith("/proc") and src != "/dev/null":
                out.add((dst, "rw" if argv[i] == "--bind" else "ro"))
            i += 3
        else:
            i += 1
    return out


def _namespaces(profile: SandboxProfile, backend: str) -> frozenset:
    """The normalized set of isolation namespaces a backend's rendering establishes — every one bwrap unshares
    plus the implicit mount namespace, and `network` iff the network is NOT granted. Extracted from the
    rendered output so a backend that DROPS a namespace (e.g. pid → host processes visible) fails parity."""
    if backend == "runsc":
        return frozenset(n["type"] for n in oci_config(profile, ["true"])["linux"]["namespaces"])
    argv = profile.bwrap_argv(["true"])
    ns = {"mount"}                                            # bwrap always creates a mount namespace to bind
    for flag, name in (("--unshare-user", "user"), ("--unshare-pid", "pid"), ("--unshare-ipc", "ipc"),
                       ("--unshare-uts", "uts"), ("--unshare-cgroup-try", "cgroup"), ("--unshare-net", "network")):
        if flag in argv:
            ns.add(name)
    return frozenset(ns)


def _masked_proc(profile: SandboxProfile, backend: str) -> frozenset:
    """The set of dangerous /proc surfaces a backend neutralizes: the live-kernel files shadowed + /proc/sys
    made read-only. Extracted from the rendering so a backend that leaves a file writable fails parity."""
    if backend == "runsc":
        spec = oci_config(profile, ["true"])
        masked = {f for f in spec["linux"]["maskedPaths"] if f in _MASKED_PROC}
        if "/proc/sys" in spec["linux"]["readonlyPaths"]:
            masked.add("/proc/sys")
        return frozenset(masked)
    argv = profile.bwrap_argv(["true"])
    masked = set()
    for i in range(len(argv) - 2):
        if argv[i] == "--ro-bind" and argv[i + 1] == "/dev/null" and argv[i + 2] in _MASKED_PROC:
            masked.add(argv[i + 2])
    if "/proc/sys" in argv:                                   # --ro-bind-try /proc/sys /proc/sys
        masked.add("/proc/sys")
    return frozenset(masked)


def confinement(profile: SandboxProfile, backend: str = "bwrap") -> dict:
    """The backend-independent SECURITY confinement a backend's rendering enforces — extracted from the ACTUAL
    rendered output (argv / OCI spec), NOT re-derived from the profile. Two backends are seam-equivalent iff
    their confinement() dicts are EQUAL. The dict is TOTAL over the boundary's properties — the capability
    binds, the FULL namespace set (pid/ipc/uts/cgroup/user/mount + network), nobody uid/gid, dropped caps,
    no-new-privileges, the readonly rootfs, AND the masked /proc surfaces — so a backend that drops ANY of them
    fails parity. This is how P2-T04 proves gVisor never WEAKENS the bwrap boundary (a coarser check would be
    vacuous: a dropped pid namespace or an un-masked /proc file would slip through)."""
    mounts = capability_mounts(profile, backend)
    nss = _namespaces(profile, backend)
    common = {"mounts": mounts,
              "namespaces": nss,
              "net_isolated": "network" in nss,
              "readonly_root": {p for p, m in mounts if m == "rw"} == {profile.workspace},  # only workspace rw
              "masked_proc": _masked_proc(profile, backend)}
    if backend == "runsc":
        spec = oci_config(profile, ["true"])
        return {**common,
                "uid": spec["process"]["user"]["uid"], "gid": spec["process"]["user"]["gid"],
                "no_new_privs": spec["process"]["noNewPrivileges"],
                "caps_dropped": spec["process"]["capabilities"]["bounding"] == []}
    argv = profile.bwrap_argv(["true"])
    return {**common,
            "uid": int(argv[argv.index("--uid") + 1]), "gid": int(argv[argv.index("--gid") + 1]),
            "no_new_privs": "--unshare-user" in argv,          # a fresh userns + nobody == no privilege escalation
            "caps_dropped": "--unshare-user" in argv}          # host caps do not reach into the new userns


def run_confined(profile: SandboxProfile, argv: Sequence[str], *, timeout: int = 600,
                 stdin: str | None = None, backend: str = "bwrap") -> subprocess.CompletedProcess:
    """Run `argv` inside the profile's sandbox via `backend` ("bwrap" default | "runsc" gVisor) and return the
    CompletedProcess. REFUSES (raises RuntimeError) when the chosen backend cannot enforce the boundary on this
    host — it never silently runs the step unconfined."""
    if backend == "runsc":
        if not runsc_available():
            raise RuntimeError("gVisor sandbox unavailable (need Linux + runsc) — refusing to run unconfined")
        return _run_runsc(profile, argv, timeout=timeout, stdin=stdin)
    if not is_available():
        raise RuntimeError("kernel sandbox unavailable (need Linux + bwrap) — refusing to run unconfined")
    return subprocess.run(profile.bwrap_argv(argv), capture_output=True, text=True,
                          timeout=timeout, input=stdin)


# ── P3-T11: the grant's sandbox TIER selects the P2 confinement backend ───────────────────────────────────
SANDBOX_TIERS = ("core", "verified", "community")          # the catalog tiers a perk may DECLARE
_TIER_BACKEND = {"core": "bwrap", "verified": "bwrap", "trusted": "bwrap", "community": "runsc"}
_BACKEND_STRENGTH = {"bwrap": 1, "runsc": 2}               # runsc (the gVisor Sentry) is the STRONGER isolation


def backend_for_tier(tier) -> str:
    """The confinement backend a grant's sandbox tier REQUIRES (P3-T11): the trusted family (core/verified, plus
    the secret-bearing `trusted`) runs in bwrap; an untrusted `community` perk DEMANDS the gVisor (runsc) box.
    An UNDECLARED tier (None) maps to bwrap — the floor-neutral element, so the operator's --backend floor
    governs and nothing regresses. An unknown/garbage declared tier maps to runsc (FAIL-SAFE: the strongest box
    for a provenance we cannot vouch for)."""
    if tier is None:
        return "bwrap"
    return _TIER_BACKEND.get(tier, "runsc")


def strongest(a: str, b: str) -> str:
    """The stronger of two backends (runsc > bwrap). Backend selection is MONOTONE: a tier may only RATCHET the
    operator's floor UP (community forces runsc even under a bwrap floor), never weaken it (a core grant on a
    runsc-floored host still gets runsc). So an untrusted perk is never silently downgraded to a weaker box."""
    return a if _BACKEND_STRENGTH.get(a, 0) >= _BACKEND_STRENGTH.get(b, 0) else b


def backend_enforceable(backend: str) -> bool:
    """Whether `backend` can actually confine on THIS host (runsc needs Linux + gVisor; bwrap needs Linux +
    bwrap). A selected backend that is not enforceable makes the step REFUSE (fail-closed) — the runner raises
    rather than running unconfined."""
    return runsc_available() if backend == "runsc" else is_available()


def tier_backend_selftest() -> dict:
    """P3-T11 — the grant's sandbox tier selects the confinement backend, as a MONOTONE floor over the operator's
    --backend. Hermetic, no host backend needed (pure selection logic; the end-to-end exod threading is proven
    in tests/test_exod.py + the cws-release perk):
      (1) tier_maps — community → runsc; core/verified/trusted → bwrap; an UNDECLARED tier (None) → bwrap; an
          unknown/garbage tier → runsc (fail-safe, strongest).
      (2) monotone_floor — strongest() only ratchets UP: a bwrap floor + community → runsc; a runsc floor + core
          → runsc (a trusted perk on a hardened host is NOT downgraded); a bwrap floor + core/None → bwrap.
      (3) enforceable_gate — backend_enforceable mirrors the live host backends (bwrap=is_available,
          runsc=runsc_available); a non-enforceable selected backend is the fail-closed refusal point."""
    tier_maps = (backend_for_tier("community") == "runsc"
                 and backend_for_tier("core") == "bwrap"
                 and backend_for_tier("verified") == "bwrap"
                 and backend_for_tier("trusted") == "bwrap"
                 and backend_for_tier(None) == "bwrap"
                 and backend_for_tier("nonsense-tier") == "runsc")
    monotone_floor = (strongest("bwrap", backend_for_tier("community")) == "runsc"   # community ratchets up
                      and strongest("runsc", backend_for_tier("core")) == "runsc"    # core NOT downgraded
                      and strongest("bwrap", backend_for_tier("core")) == "bwrap"
                      and strongest("bwrap", backend_for_tier(None)) == "bwrap")
    enforceable_gate = (backend_enforceable("bwrap") == is_available()
                        and backend_enforceable("runsc") == runsc_available())
    ok = bool(tier_maps and monotone_floor and enforceable_gate)
    return {"tier_maps": tier_maps, "monotone_floor": monotone_floor, "enforceable_gate": enforceable_gate,
            "bwrap_live": is_available(), "runsc_live": runsc_available(), "ok": ok}


def community_tier_selftest() -> dict:
    """Hermetic, no-network, no host backend needed (PURE rendering). The P2-T04 seam proof:
      (1) seam_parity — gVisor (runsc) renders the SAME confinement as bwrap for the core, a network-granted,
          and a custom-bind profile: identical capability binds, net isolation, nobody uid/gid, dropped caps,
          no-new-privileges, masked /proc, readonly rootfs. The community backend never WEAKENS the boundary.
      (2) gvisor_no_weaken — the OCI spec's hard invariants hold on their own: readonly rootfs, ALL caps
          dropped, no-new-privileges, the network namespace unshared when network is not granted, no raw block
          device, the masked /proc paths.
      (3) network_grant_tracks — a network-granted profile drops net isolation in BOTH backends together (the
          grant is honoured identically), never in one but not the other.
      (4) no_secrets_tier — the community tier is the no-secrets floor: a community manifest requesting a
          credential is refused at BOTH the schema and the runtime (materialize_checked), while a trusted-tier
          grant may name secrets. (The LIVE corpus under each backend is gated on the host: bwrap=is_available,
          runsc=runsc_available — exercised on a Linux node, a documented stub elsewhere.)"""
    from infra.exec import capmanifest as cm

    profiles = [core_profile("/ws"), core_profile("/ws", network=True),
                SandboxProfile(workspace="/ws", ro_binds=("/usr", "/etc"))]
    seam_parity = all(confinement(p, "bwrap") == confinement(p, "runsc") for p in profiles)

    cp = core_profile("/ws")
    spec = oci_config(cp, ["true"])
    # a HOST device exposed to the step (the exact dir /dev OR any /dev/* except /dev/null) would be a weakening
    host_dev = any(m.get("type") == "bind"
                   and (m.get("destination") == "/dev"
                        or (m.get("destination", "").startswith("/dev/") and m.get("destination") != "/dev/null"))
                   for m in spec["mounts"])
    # every bind carries nosuid (a setuid binary can't escalate); tmpfs is nosuid+nodev+noexec
    binds_nosuid = all("nosuid" in m.get("options", []) for m in spec["mounts"] if m.get("type") == "bind")
    tmpfs_hardened = all({"nosuid", "nodev", "noexec"} <= set(m.get("options", []))
                         for m in spec["mounts"] if m.get("type") == "tmpfs")
    # --clearenv equivalent: the step env is EXACTLY the profile's (no injected LD_PRELOAD/LD_LIBRARY_PATH/etc.)
    spec_env = dict(kv.split("=", 1) for kv in spec["process"]["env"])
    env_is_clean = spec_env == dict(cp.env)
    full_ns = _namespaces(cp, "runsc") >= {"pid", "ipc", "uts", "cgroup", "user", "mount", "network"}
    full_masked = _masked_proc(cp, "runsc") >= ({f for f in _MASKED_PROC if os.path.exists(f)} | {"/proc/sys"})
    gvisor_no_weaken = bool(
        spec["root"]["readonly"]
        and spec["process"]["capabilities"]["bounding"] == []
        and spec["process"]["noNewPrivileges"] is True
        and spec["process"]["user"]["uid"] == 65534 and spec["process"]["user"]["gid"] == 65534
        and full_ns and full_masked and binds_nosuid and tmpfs_hardened and env_is_clean
        and not host_dev)

    netp = core_profile("/ws", network=True)
    network_grant_tracks = (confinement(netp, "bwrap")["net_isolated"] is False
                            and confinement(netp, "runsc")["net_isolated"] is False)

    ws = "/ws"
    community_clean = cm.community_no_secrets(cm.CapabilityManifest(workspace=ws))[0] is True
    community_secret_refused = cm.community_no_secrets(
        cm.CapabilityManifest(workspace=ws, credentials=("api_key",)))[0] is False
    schema_refuses = cm.validate_manifest_schema(
        {"workspace": ws, "tier": "community", "credentials": ["api_key"]})[0] is False
    trusted_may = cm.community_no_secrets(
        cm.CapabilityManifest(workspace=ws, tier="trusted", credentials=("api_key",)))[0] is True
    runtime_refuses = False
    try:
        cm.materialize_checked(cm.CapabilityManifest(workspace=ws, credentials=("api_key",)))
    except ValueError:
        runtime_refuses = True
    no_secrets_tier = bool(community_clean and community_secret_refused and schema_refuses
                           and trusted_may and runtime_refuses)

    ok = bool(seam_parity and gvisor_no_weaken and network_grant_tracks and no_secrets_tier)
    return {"seam_parity": seam_parity, "gvisor_no_weaken": gvisor_no_weaken,
            "network_grant_tracks": network_grant_tracks, "no_secrets_tier": no_secrets_tier,
            "bwrap_live": is_available(), "runsc_live": runsc_available(), "ok": ok}


def _run_runsc(profile: SandboxProfile, argv: Sequence[str], *, timeout: int,
               stdin: str | None) -> subprocess.CompletedProcess:
    """Write the OCI bundle (config.json + a rootfs view) and run it under `runsc run`. Linux+runsc only
    (gated by run_confined). The bundle's rootfs is the host's readonly system tree exposed via the spec
    mounts; runsc applies the same confinement the OCI spec declares."""
    import json
    import tempfile
    bundle = tempfile.mkdtemp(prefix="runsc-bundle-")
    os.makedirs(os.path.join(bundle, "rootfs"), exist_ok=True)
    with open(os.path.join(bundle, "config.json"), "w") as f:
        json.dump(oci_config(profile, argv), f)
    cid = "cw-" + os.path.basename(bundle)
    return subprocess.run([RUNSC, "--network=none" if not profile.network else "--network=sandbox",
                           "run", "--bundle", bundle, cid],
                          capture_output=True, text=True, timeout=timeout, input=stdin)
