#!/usr/bin/env python3
"""infra/exec/bench.py — the channel/sandbox overhead meter (P2-T09 cws-bench, over P2-T07's attested meters).

Drives N benign steps through exod into the bwrap SandboxProfile and reads exod's OWN signed meter for each
(never the agent's stopwatch), then reports the per-step wall-time distribution against the plan's budget.

  * the bwrap budget (p95 <= 100 ms/step) is measurable wherever bwrap runs;
  * the microVM budgets (cold <= 1500 ms, warm <= 250 ms) need /dev/kvm + a microVM backend. On a host
    without nested virtualization there is none, so `bench_microvm` reports `skipped` — the budget is left
    HONESTLY unmet, never faked. Where /dev/kvm IS present, it times a REAL Firecracker boot + snapshot
    resume and reads a per-run random marker off the guest serial console (unfakeable by a process spawn).
"""
from __future__ import annotations
import hashlib
import json
import os
import select
import socket
import subprocess
import time
import urllib.request

from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

from infra.exec.exod import Exod, meter_of
from infra.exec.exodverify import result_body, verify_step_result
from infra.exec.grants import mint_grant
from infra.exec.sandbox import is_available

BWRAP_P95_BUDGET_MS = 100
MICROVM_COLD_BUDGET_MS = 1500
MICROVM_WARM_BUDGET_MS = 250


def _percentile(xs, q):
    s = sorted(xs)
    if not s:
        return None
    i = min(len(s) - 1, max(0, round((q / 100.0) * (len(s) - 1))))
    return s[i]


def bench_bwrap(n: int = 30, workspace: str | None = None) -> dict:
    """Run `n` benign steps through exod+sandbox, collecting exod's ATTESTED wall_ms per step. Returns the
    distribution + whether p95 is within budget. `within` is None when the boundary is unavailable."""
    if not is_available():
        return {"backend": "bwrap", "skipped": "kernel sandbox unavailable (need Linux + bwrap)",
                "within": None}
    import tempfile
    ws = workspace or tempfile.mkdtemp()
    os.chmod(ws, 0o777)
    issuer = Ed25519PrivateKey.generate()
    exod = Exod(Ed25519PrivateKey.generate(), grant_issuer_pub=issuer.public_key())
    samples = []
    for i in range(n):
        grant = mint_grant(issuer, run_id="bench", plan_sha="bench", nbf=0, exp=10**12,
                           nonce=f"g{i}", capabilities=["run"])
        req = {"run_id": "bench", "plan_sha": "bench", "step": str(i),
               "argv": ["bash", "-lc", "true"], "workspace": ws, "nonce": f"r{i}", "grant": grant}
        env = exod.run_step(req, now=1000)
        ok, _ = verify_step_result(exod.public_key, env, expect_run_id="bench")
        assert ok and result_body(env)["status"] == "ok"
        samples.append(meter_of(env)["wall_ms"])          # exod-attested, not measured by us
    p95 = _percentile(samples, 95)
    return {"backend": "bwrap", "n": n, "p50": _percentile(samples, 50), "p95": p95,
            "max": max(samples), "budget_ms": BWRAP_P95_BUDGET_MS, "within": p95 <= BWRAP_P95_BUDGET_MS}


def has_kvm() -> bool:
    return os.path.exists("/dev/kvm")


# --- microVM (Firecracker) overhead meter -----------------------------------------------------
# We time a REAL boot through /dev/kvm and read a deterministic, per-run-RANDOM guest-alive marker off the
# guest serial console (Firecracker mirrors ttyS0 -> its own stdout). No login-prompt parsing.
#
# Artifacts are PINNED by sha256 to the Firecracker CI S3 bucket (stable, dated-by-release path):
#   kernel  : firecracker-ci/v1.12/x86_64/vmlinux-5.10.233        (verified 200, 38499448 B, 2026-06-21)
#   firecracker binary: GH release v1.12.1 tgz                    (verified 200, 2026-06-21)
# The guest rootfs is BUILT AT RUNTIME (a tiny ext4 holding a static busybox /init that echoes a unique
# marker to the console), so the cold ready-signal is fully under our control — it does not depend on a
# distro init system. `init=/init` is set explicitly because the kernel only auto-runs /init for an
# initramfs; for a disk root it would otherwise try /sbin/init and panic.
FC_KERNEL_URL = "https://s3.amazonaws.com/spec.ccfc.min/firecracker-ci/v1.12/x86_64/vmlinux-5.10.233"
FC_KERNEL_SHA256 = "3a30d91f3bf475e3950b9825d047c6839bc64249f383f6173912fe8afe89b5c3"  # verified 2026-06-21
FC_BIN_URL = ("https://github.com/firecracker-microvm/firecracker/releases/download/"
              "v1.12.1/firecracker-v1.12.1-x86_64.tgz")

_BOOT_ARGS = "console=ttyS0 reboot=k panic=-1 pci=off i8042.noaux i8042.nomux i8042.dumbkbd init=/init"


def _fetch(url: str, dest: str, sha256: str = "") -> None:
    """Download url -> dest, verifying sha256 if pinned. Raises (loud) on mismatch/non-200."""
    with urllib.request.urlopen(url, timeout=120) as r:                              # noqa: S310 (pinned host)
        if r.status != 200:
            raise RuntimeError(f"artifact fetch failed {r.status}: {url}")
        data = r.read()
    if sha256:
        got = hashlib.sha256(data).hexdigest()
        if got != sha256:
            raise RuntimeError(f"artifact sha256 mismatch for {url}: got {got} want {sha256}")
    with open(dest, "wb") as f:
        f.write(data)


def _busybox() -> str:
    """Locate a STATIC busybox (a dynamic one cannot exec inside the bare rootfs). Prefer /bin/busybox
    (the ubuntu busybox-static package location); raise loudly if none is found."""
    import shutil
    for cand in ("/bin/busybox", "/usr/bin/busybox", shutil.which("busybox")):
        if cand and os.path.exists(cand):
            return cand
    raise RuntimeError("busybox not found (CI must `apt-get install -y busybox-static`)")


def _mkext4_with_init(path: str, init_script: str) -> None:
    """Build a tiny ext4 image whose /init is `init_script` (run by a static busybox), using host tools
    (mke2fs -d, present on ubuntu-latest). Raises loudly if a tool is missing."""
    import shutil
    import tempfile
    bb = _busybox()
    root = tempfile.mkdtemp()
    os.makedirs(os.path.join(root, "bin"), exist_ok=True)
    shutil.copy(bb, os.path.join(root, "bin", "busybox"))
    init = os.path.join(root, "init")
    with open(init, "w") as f:
        f.write(init_script)
    os.chmod(init, 0o755)
    # mke2fs -d stages a directory tree into a fresh ext4 image (e2fsprogs >= 1.43; ubuntu-latest has it).
    subprocess.run(["mke2fs", "-q", "-t", "ext4", "-d", root, "-b", "1024", path, "16384"],
                   check=True, capture_output=True)


def _build_marker_rootfs(path: str, marker: str) -> None:
    """Guest /init prints `marker` once to the console, then halts — the cold boot signal."""
    _mkext4_with_init(path, "#!/bin/busybox sh\n"
                            f"/bin/busybox echo {marker}\n"
                            "/bin/busybox sync\n"
                            "/bin/busybox poweroff -f\n")


def _build_loop_marker_rootfs(path: str, marker: str) -> None:
    """Guest /init re-prints `marker` every ~10 ms so the VM stays alive to be paused+snapshotted and
    re-emits the marker promptly after resume — the warm signal."""
    _mkext4_with_init(path, "#!/bin/busybox sh\n"
                            f"while true; do /bin/busybox echo {marker}; /bin/busybox usleep 10000; done\n")


def _wait_marker(proc: "subprocess.Popen[bytes]", marker: str, deadline: float) -> bool:
    """Read proc.stdout (FC's mirror of guest ttyS0) until `marker` bytes appear or the deadline passes.
    Non-blocking via select so a silent/hung guest cannot block us past the deadline."""
    needle = marker.encode()
    buf = b""
    fd = proc.stdout.fileno()
    while time.monotonic() < deadline:
        r, _, _ = select.select([fd], [], [], min(0.25, max(0.0, deadline - time.monotonic())))
        if r:
            chunk = os.read(fd, 65536)
            if chunk:
                buf += chunk
                if needle in buf:
                    return True
                buf = buf[-4096:]                          # bound memory; the marker is ~28 bytes
                continue
        if proc.poll() is not None:                        # process exited — final drain
            try:
                tail = os.read(fd, 65536)
            except OSError:
                tail = b""
            return bool(tail) and needle in (buf + tail)
    return False


def _console_tail(proc: "subprocess.Popen[bytes]", max_bytes: int = 512) -> str:
    """Best-effort non-blocking read of whatever guest console output is still buffered — for a diagnostic
    tail on a boot/resume FAILURE (e.g. a kernel panic loop), so a burned CI run is actionable."""
    out = b""
    try:
        fd = proc.stdout.fileno()
        while len(out) < max_bytes:
            r, _, _ = select.select([fd], [], [], 0.2)
            if not r:
                break
            chunk = os.read(fd, max_bytes)
            if not chunk:
                break
            out += chunk
    except Exception:
        pass
    return out[-max_bytes:].decode("utf-8", "replace")


def _await_sock(path: str, timeout: float) -> None:
    end = time.monotonic() + timeout
    while time.monotonic() < end:
        if os.path.exists(path):
            return
        time.sleep(0.005)
    raise RuntimeError(f"firecracker API socket never appeared: {path}")


def _api(sock_path: str, method: str, route: str, body: dict | None) -> None:
    """Minimal HTTP-over-unix-socket call to the Firecracker API (no extra deps). Raises on non-2xx."""
    payload = b"" if body is None else json.dumps(body).encode()
    req = (f"{method} {route} HTTP/1.1\r\nHost: localhost\r\n"
           f"Content-Type: application/json\r\nContent-Length: {len(payload)}\r\n"
           f"Connection: close\r\n\r\n").encode() + payload
    s = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
    s.connect(sock_path)
    s.sendall(req)
    resp = b""
    while True:
        chunk = s.recv(4096)
        if not chunk:
            break
        resp += chunk
    s.close()
    status = resp.split(b"\r\n", 1)[0]
    if b" 200 " not in status and b" 204 " not in status:
        body = resp.split(b"\r\n\r\n", 1)[1][:300] if b"\r\n\r\n" in resp else b""
        raise RuntimeError(f"firecracker API {method} {route} -> {status!r} body={body!r}")


def bench_microvm(work: str | None = None) -> dict:
    """Time a REAL Firecracker microVM cold boot and a warm snapshot-resume through /dev/kvm.

    cold: a fresh firecracker process boots kernel+marker-rootfs from a config file; the timer starts just
          before exec and STOPS when the guest's /init prints its unique random marker on ttyS0 — so the
          interval covers FC start + KVM kernel boot + pid1 (an honest "cold microVM start").
    warm: a microVM is booted, paused and Full-snapshotted; then a FRESH firecracker process does
          PUT /snapshot/load {resume_vm:true}. The warm timer starts just before that load call (the
          canonical FC resume cost — the daemon is already running) and STOPS when the resumed guest
          re-emits its marker. Fresh-process is enforced by FC itself (a snapshot loads only on a virgin VM).

    within = (cold<=1500 AND warm<=250). Any failure RAISES so a CI job fails loud — never a faked pass.
    Without /dev/kvm or a backend, returns within:None + skipped (the budget left honestly unmet)."""
    if not has_kvm():
        return {"backend": "microvm", "skipped": "no /dev/kvm (no nested virtualization / microVM backend)",
                "cold_budget_ms": MICROVM_COLD_BUDGET_MS, "warm_budget_ms": MICROVM_WARM_BUDGET_MS,
                "within": None}
    import shutil
    import tempfile
    fc = shutil.which("firecracker")
    if not fc:
        raise RuntimeError("firecracker binary not on PATH (CI must fetch+chmod it before bench_microvm)")
    work = work or tempfile.mkdtemp()
    kernel = os.path.join(work, "vmlinux")
    _fetch(FC_KERNEL_URL, kernel, FC_KERNEL_SHA256)

    def _spawn(api_sock: str, *extra: str) -> "subprocess.Popen[bytes]":
        if os.path.exists(api_sock):
            os.unlink(api_sock)
        return subprocess.Popen([fc, "--api-sock", api_sock, *extra], cwd=work,
                                stdin=subprocess.DEVNULL, stdout=subprocess.PIPE,
                                stderr=subprocess.STDOUT, bufsize=0)

    def _drain(proc: "subprocess.Popen[bytes]") -> None:
        proc.kill()
        try:
            proc.wait(timeout=5)
        except Exception:
            pass

    # ---- COLD ---- boot from a config file (auto-starts); timer from exec to first marker.
    rootfs = os.path.join(work, "rootfs.ext4")
    marker = "CWS_BOOT_OK_" + hashlib.sha256(os.urandom(16)).hexdigest()[:16]
    _build_marker_rootfs(rootfs, marker)
    cfg = os.path.join(work, "vm.json")
    with open(cfg, "w") as f:
        json.dump({
            "boot-source": {"kernel_image_path": kernel, "boot_args": _BOOT_ARGS},
            "drives": [{"drive_id": "rootfs", "path_on_host": rootfs,
                        "is_root_device": True, "is_read_only": False}],
            "machine-config": {"vcpu_count": 1, "mem_size_mib": 128, "smt": False},
        }, f)
    t0 = time.monotonic()
    cold_proc = _spawn(os.path.join(work, "cold.sock"), "--config-file", cfg)
    cold_tail = ""
    try:
        cold_ok = _wait_marker(cold_proc, marker, t0 + 30.0)
        cold_ms = (time.monotonic() - t0) * 1000.0
        if not cold_ok:
            cold_tail = _console_tail(cold_proc)
    finally:
        _drain(cold_proc)
    if not cold_ok:
        raise RuntimeError("cold boot never emitted guest marker (boot failed / KVM unusable); "
                           f"console_tail={cold_tail!r}")

    # ---- WARM ---- snapshot a freshly-booted+paused VM, then resume it in a FRESH process.
    warm_marker = "CWS_WARM_OK_" + hashlib.sha256(os.urandom(16)).hexdigest()[:16]
    rootfs_w = os.path.join(work, "rootfs_w.ext4")
    _build_loop_marker_rootfs(rootfs_w, warm_marker)
    snap = os.path.join(work, "snapshot.file")
    mem = os.path.join(work, "mem.file")
    src = _spawn(os.path.join(work, "snap.sock"))
    apiS = os.path.join(work, "snap.sock")
    try:
        _await_sock(apiS, timeout=10.0)
        _api(apiS, "PUT", "/boot-source", {"kernel_image_path": kernel, "boot_args": _BOOT_ARGS})
        _api(apiS, "PUT", "/drives/rootfs", {"drive_id": "rootfs", "path_on_host": rootfs_w,
                                             "is_root_device": True, "is_read_only": False})
        _api(apiS, "PUT", "/machine-config", {"vcpu_count": 1, "mem_size_mib": 128, "smt": False})
        _api(apiS, "PUT", "/actions", {"action_type": "InstanceStart"})
        if not _wait_marker(src, warm_marker, time.monotonic() + 30.0):
            raise RuntimeError("warm-prep boot never emitted marker")
        _api(apiS, "PATCH", "/vm", {"state": "Paused"})
        _api(apiS, "PUT", "/snapshot/create",
             {"snapshot_type": "Full", "snapshot_path": snap, "mem_file_path": mem})
    finally:
        _drain(src)

    apiW = os.path.join(work, "warm.sock")
    spawn0 = time.monotonic()
    warm_proc = _spawn(apiW)
    warm_tail, warm_alive = "", None
    try:
        _await_sock(apiW, timeout=10.0)
        spawn_ms = (time.monotonic() - spawn0) * 1000.0
        w0 = time.monotonic()                              # canonical warm cost starts at the load call
        _api(apiW, "PUT", "/snapshot/load",
             {"snapshot_path": snap, "mem_backend": {"backend_path": mem, "backend_type": "File"},
              "enable_diff_snapshots": False, "resume_vm": True})
        warm_ok = _wait_marker(warm_proc, warm_marker, w0 + 15.0)
        warm_ms = (time.monotonic() - w0) * 1000.0
        if not warm_ok:                                    # distinguish 'resume errored' from 'silent console'
            warm_alive = warm_proc.poll() is None
            warm_tail = _console_tail(warm_proc)
    finally:
        _drain(warm_proc)
    if not warm_ok:
        raise RuntimeError("warm resume never re-emitted guest marker (snapshot resume failed); "
                           f"warm_proc_alive={warm_alive} console_tail={warm_tail!r}")

    within = (cold_ms <= MICROVM_COLD_BUDGET_MS) and (warm_ms <= MICROVM_WARM_BUDGET_MS)
    return {"backend": "microvm", "firecracker": "v1.12.1",
            "cold_ms": round(cold_ms, 1), "warm_ms": round(warm_ms, 1),
            "warm_spawn_ms": round(spawn_ms, 1),           # FC process spawn, EXCLUDED from warm_ms
            "cold_budget_ms": MICROVM_COLD_BUDGET_MS, "warm_budget_ms": MICROVM_WARM_BUDGET_MS,
            "ready_signal": "per-run-random guest-init serial marker", "within": within}


if __name__ == "__main__":
    import argparse
    import sys
    ap = argparse.ArgumentParser(description="cyberware exec overhead meter (P2-T09)")
    ap.add_argument("--microvm", action="store_true", help="time the microVM cold boot + warm resume")
    ap.add_argument("--bwrap", action="store_true", help="measure bwrap per-step overhead")
    a = ap.parse_args()
    if a.microvm:
        res = bench_microvm()
    elif a.bwrap:
        res = bench_bwrap()
    else:
        ap.error("choose --microvm or --bwrap")
    print(json.dumps(res, indent=2))
    sys.exit(0 if res.get("within") is True else 1)
