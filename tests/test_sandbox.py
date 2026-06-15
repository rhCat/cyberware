"""The kernel-enforced refusal corpus for the SandboxProfile driver (P2-T03 / the cws-redteam spine).

Each behaviour is proven against its SPECIFIC kernel signature, not a bare nonzero exit. A sandbox that
fails to *start* (a `bwrap:` setup error) is raised as a harness error by `_box` — it can never be mistaken
for a refusal, which is the false-green a security corpus must never have. Where it adds confidence a test
also runs an ORACLE: the same command UNCONFINED succeeds / the resource is visible, so the delta is
demonstrably the kernel boundary and not an inert attack.

There is NO software scan anywhere in this path — `run_confined` inspects nothing about the command. So a
green run here is the literal SV-3 acceptance: ">=12 behaviours refused, refusals hold with the in-process
scan disabled." The step runs as `nobody`, so the workspace exod hands it must be enterable + writable by
that uid; the `ws` fixture models that. The module SKIPS where the boundary cannot exist (no Linux / no
bwrap), so it is a strict no-op on the macOS dev box and runs for real inside docker/Dockerfile.exec.
"""
from __future__ import annotations
import os
import shlex
import subprocess
import sys

import pytest

from infra.exec.sandbox import core_profile, is_available, run_confined

pytestmark = pytest.mark.skipif(not is_available(), reason="kernel sandbox needs a Linux host with bwrap")


@pytest.fixture
def ws(tmp_path):
    """A workspace as exod would hand it to an unprivileged step: enterable + writable by `nobody`."""
    os.chmod(tmp_path, 0o777)
    return tmp_path


def _raw(cmd: str) -> subprocess.CompletedProcess:
    """The control: run a shell command with NO confinement at all."""
    return subprocess.run(["bash", "-lc", cmd], capture_output=True, text=True)


def _box(ws, cmd: str, *, network: bool = False) -> subprocess.CompletedProcess:
    """The treatment: run the same shell command inside the spine core sandbox. If bwrap fails to SET UP
    the sandbox (a `bwrap:`-prefixed error), that is a harness fault — raise, so it is never counted as a
    refusal."""
    r = run_confined(core_profile(str(ws), network=network), ["bash", "-lc", cmd])
    if r.returncode != 0 and r.stderr.lstrip().startswith("bwrap:"):
        raise RuntimeError(f"sandbox failed to start (not a refusal): {r.stderr.strip()}")
    return r


def _blob(text: str) -> str:
    return f"python3 -c {shlex.quote(text)}"


# ── refusals 1–4: the filesystem boundary ──────────────────────────────────────────────────────────

def test_01_host_secret_outside_binds_is_invisible(ws):
    secret = "/sandbox_probe_secret_DO_NOT_LEAK"
    with open(secret, "w") as f:
        f.write("TOPSECRET")
    try:
        assert _raw(f"cat {secret}").returncode == 0                      # control: the file is real
        r = _box(ws, f"cat {secret}")                                     # confined: not in the view
        assert r.returncode != 0
        assert "no such file" in r.stderr.lower()
    finally:
        os.remove(secret)


def test_02_write_to_readonly_system_is_refused(ws):
    assert _raw("touch /usr/_CONTROL && rm -f /usr/_CONTROL").returncode == 0   # control: root can write /usr
    r = _box(ws, "touch /usr/PWNED")
    assert r.returncode != 0
    assert "read-only file system" in (r.stderr + r.stdout).lower()             # the ro-bind, kernel EROFS


def test_03_write_outside_the_workspace_is_refused(ws):
    r = _box(ws, "touch /opt/PWNED")                                            # /opt is not bound at all
    assert r.returncode != 0
    assert "no such file" in (r.stderr + r.stdout).lower()


def test_04_proc_sys_kernel_knob_is_not_writable(ws):
    # /proc/sys is masked read-only, so a global kernel knob cannot be rewritten even if a capability leaks
    r = _box(ws, "echo 0 > /proc/sys/kernel/randomize_va_space")
    assert r.returncode != 0
    assert "read-only file system" in (r.stderr + r.stdout).lower()
    assert _box(ws, "cat /proc/sys/kernel/randomize_va_space").returncode == 0  # reads still work


# ── refusals 5–6: the network boundary ─────────────────────────────────────────────────────────────

def test_05_container_interface_is_gone(ws):
    # a fresh net namespace keeps loopback + the kernel's (down) tunnel pseudo-devices, but the container's
    # real NIC is absent — there is no interface that could carry egress
    r = _box(ws, "cat /proc/net/dev")
    assert r.returncode == 0
    ifaces = [ln.split(":")[0].strip() for ln in r.stdout.splitlines() if ":" in ln]
    assert "eth0" not in ifaces and "lo" in ifaces, f"unexpected interfaces: {ifaces}"
    assert "eth0" in _raw("cat /proc/net/dev").stdout                          # control: the NIC really exists


def test_06_tcp_egress_is_unreachable(ws):
    probe = ("import socket,sys\n"
             "try:\n"
             "    socket.create_connection(('8.8.8.8',53),2); print('CONNECTED'); sys.exit(0)\n"
             "except OSError as e:\n"
             "    print('ERRNO', e.errno); sys.exit(7)\n")
    off = _box(ws, _blob(probe), network=False)
    assert off.returncode == 7 and "ERRNO" in off.stdout            # a kernel errno, not a python crash
    # oracle: the SAME sandbox WITH a network namespace is not ENETUNREACH — the flag is load-bearing
    on = _box(ws, _blob(probe), network=True)
    assert "Network is unreachable" not in (on.stdout + on.stderr)


# ── refusals 7–9: the process / pid boundary ───────────────────────────────────────────────────────

def test_07_host_processes_are_invisible(ws):
    r = _box(ws, "ls /proc | grep -E '^[0-9]+$' | wc -l")
    assert r.returncode == 0
    assert int(r.stdout.strip()) <= 5, f"too many PIDs visible: {r.stdout!r}"
    assert _box(ws, f"test -d /proc/{os.getpid()}").returncode != 0            # this pytest PID is hidden


def test_08_cannot_signal_a_host_process(ws):
    victim = subprocess.Popen(["sleep", "120"])                     # a real process in the host pid ns
    try:
        r = _box(ws, f"kill -9 {victim.pid}")
        assert r.returncode != 0                                    # ESRCH: not in the sandbox pid ns
        assert "no such process" in (r.stderr + r.stdout).lower()
        assert victim.poll() is None                                # and it is demonstrably still alive
    finally:
        victim.kill()
        victim.wait()


def test_09_no_new_privs_is_set(ws):
    r = _box(ws, "grep NoNewPrivs /proc/self/status")
    assert r.returncode == 0 and r.stdout.strip().split()[-1] == "1"           # setuid can never elevate
    assert _raw("grep NoNewPrivs /proc/self/status").stdout.strip().split()[-1] == "0"   # control


# ── refusals 10–13: capability / namespace boundary ────────────────────────────────────────────────

def test_10_mount_is_refused(ws):
    r = _box(ws, "mount -t tmpfs none /tmp")                         # an existing mountpoint
    assert r.returncode != 0                                        # no CAP_SYS_ADMIN over the host
    assert any(s in (r.stderr + r.stdout).lower()
               for s in ("permission denied", "operation not permitted", "must be superuser", "only root"))


def test_11_sysfs_is_not_present(ws):
    assert _box(ws, "test -e /sys/kernel").returncode != 0                     # /sys is never bound


def test_12_uts_namespace_is_isolated(ws):
    r = _box(ws, "hostname")
    assert r.returncode == 0 and r.stdout.strip() == "sandbox"                 # our namespace, not host's
    assert _raw("hostname").stdout.strip() != "sandbox"                        # control


def test_13_cannot_reboot_host_via_sysrq(ws):
    # /proc/sysrq-trigger would reboot/panic the host; it is masked by /dev/null + the step is unprivileged.
    # NO unconfined control here — that would actually reboot the machine.
    r = _box(ws, "echo b > /proc/sysrq-trigger")
    assert r.returncode != 0
    assert any(s in (r.stderr + r.stdout).lower()
               for s in ("read-only", "permission denied", "no such file", "operation not permitted"))


# ── positive controls: the sandbox is NOT "deny everything" ────────────────────────────────────────

def test_14_legitimate_workspace_write_is_accepted(ws):
    r = _box(ws, "echo done > result.txt")
    assert r.returncode == 0
    assert (ws / "result.txt").read_text().strip() == "done"                   # and it persists to the host ws


def test_15_a_normal_program_runs(ws):
    r = _box(ws, "python3 --version")
    assert r.returncode == 0 and r.stdout.lower().startswith("python")


if __name__ == "__main__":                       # allow `python3 tests/test_sandbox.py` as a smoke run
    sys.exit(pytest.main([__file__, "-v"]))
