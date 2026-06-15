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
    env: Mapping[str, str] = dataclasses.field(default_factory=lambda: {"PATH": "/usr/bin:/bin:/usr/sbin:/sbin"})
    hostname: str = "sandbox"
    uid: int = 65534          # bwrap sets up the namespaces as userns-root, then drops the STEP to this
    gid: int = 65534          # unprivileged id ("nobody") before exec — an empty capability set + DAC
    mask_proc: bool = True    # mask the dangerous /proc paths read-only (the runc maskedPaths doctrine)

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


def run_confined(profile: SandboxProfile, argv: Sequence[str], *, timeout: int = 600,
                 stdin: str | None = None) -> subprocess.CompletedProcess:
    """Run `argv` inside the profile's bwrap sandbox and return the CompletedProcess. REFUSES (raises
    RuntimeError) when the kernel boundary is unavailable — it never silently runs the step unconfined."""
    if not is_available():
        raise RuntimeError("kernel sandbox unavailable (need Linux + bwrap) — refusing to run unconfined")
    return subprocess.run(profile.bwrap_argv(argv), capture_output=True, text=True,
                          timeout=timeout, input=stdin)
