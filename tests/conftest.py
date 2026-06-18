"""Shared fixtures + helpers for the cyberware test suite.

Puts infra/ on sys.path so the modules import as the agent runs them (`python3 infra/<x>.py`),
and provides fixtures for run dirs, sample repos, ledgers, and the compile→execute round-trip.
"""
from __future__ import annotations
import json
import shlex
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))   # so `from infra.govern import …` / `from infra.tool import …` resolve

from infra import registry  # noqa: E402
from infra.govern import runlog  # noqa: E402
from infra.tool import skill_index  # noqa: E402

TOOL_MODULES = {"scaffold", "visualize", "skill_index"}   # everything else lives under infra.govern


def run_cli(module: str, *args, **kw):
    """Invoke an infra CLI exactly as the agent does: python3 -m infra.<pkg>.<module> ..."""
    pkg = "tool" if module in TOOL_MODULES else "govern"
    kw.setdefault("cwd", str(ROOT))
    return subprocess.run([sys.executable, "-m", f"infra.{pkg}.{module}", *map(str, args)],
                          capture_output=True, text=True, **kw)


def all_perks():
    """Every (skill, perk) pair in the registry — the parametrize source for per-perk tests. Enumerated from
    the PERMITTED roster (the manifest), not a directory glob, so a stray dir scaffolded into the chip during
    a run is never collected (no phantom parametrize ids)."""
    out = []
    for sk in skill_index.all_skills(str(registry.SKILLCHIP)):
        pj = Path(registry.skill_dir(sk)) / "perks.json"
        if not pj.is_file():
            continue
        for p in json.loads(pj.read_text())["perks"]:
            out.append((sk, p["id"]))
    return out


def compiler_shaped_script(path: Path, store: Path, steps):
    """Write a run.sh in the EXACT shape compiler.py emits — for testing the executor channel.

    `steps` is a list of bash bodies (one per step); the wrapper provides --list/--step/--all.
    """
    lines = ["#!/usr/bin/env bash", "set -uo pipefail",
             f"export RECORD_STORE={shlex.quote(str(store))}", 'mkdir -p "$RECORD_STORE"', ""]
    for i, body in enumerate(steps, 1):
        lines += [f"step{i}() {{", f'  echo "[step {i}]"', f"  {body}", "}", ""]
    listing = "\\n".join(f"{i}\\ts{i}" for i in range(1, len(steps) + 1))
    allsteps = " && ".join(f"step{i}" for i in range(1, len(steps) + 1))
    lines += ['case "${1:-}" in', f'  --list) printf "{listing}\\n" ;;',
              '  --step) shift; "step${1:?}" ;;', f'  --all) {allsteps} ;;',
              '  *) echo usage >&2; exit 2 ;;', "esac", ""]
    path.write_text("\n".join(lines))
    path.chmod(0o755)
    return path


@pytest.fixture
def store(tmp_path):
    """A fresh record_store path (the pipeline creates it)."""
    return tmp_path / "out"


@pytest.fixture
def make_ledger(tmp_path):
    """Factory: write a task-ledger to disk, return (path, dict)."""
    def _make(skill, perk, store, vars):
        L = {"skill": skill, "perk": perk, "record_store": str(store), "vars": dict(vars)}
        p = tmp_path / f"{skill}__{perk}.ledger.json"
        p.write_text(json.dumps(L))
        return p, L
    return _make


@pytest.fixture
def run_skill(tmp_path, make_ledger):
    """Compile a perk and run it through the governed executor; return (CompletedProcess, run_dir)."""
    def _run(skill, perk, vars, store=None, approve=()):
        store = Path(store) if store else (tmp_path / f"out_{skill}_{perk}")
        lp, L = make_ledger(skill, perk, store, vars)
        c = run_cli("compiler", "--ledger", lp)
        assert c.returncode == 0, f"compile failed: {c.stderr}"
        run = Path(runlog.run_dir(L))
        approve_args = [x for a in approve for x in ("--approve", a)]
        x = run_cli("executor", "--script", run / "run.sh", "--all", *approve_args)
        return x, run
    return _run


@pytest.fixture
def sample_repo(tmp_path):
    """A tiny Python repo: src/a.py (used + unused fns) + tests/test_a.py (references `used`)."""
    repo = tmp_path / "repo"
    (repo / "src").mkdir(parents=True)
    (repo / "tests").mkdir()
    (repo / "src" / "a.py").write_text(
        "def used():\n    return 1\n\n\ndef unused():\n    return 2\n")
    (repo / "tests" / "test_a.py").write_text(
        "import os, sys\n"
        "sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))\n"
        "from a import used\n\n\n"
        "def test_used():\n    assert used() == 1\n")
    return repo


@pytest.fixture
def git_repo(tmp_path):
    """An initialized git repo with one commit (for git_ops / release).

    Sets *local* user config so commits/tags work even where git has no global identity (CI).
    """
    repo = tmp_path / "gitrepo"
    repo.mkdir()

    def g(*args):
        subprocess.run(["git", *args], cwd=repo, check=True, capture_output=True)

    g("init", "-q")
    g("config", "user.email", "t@t")
    g("config", "user.name", "t")
    g("config", "commit.gpgsign", "false")
    (repo / "f.txt").write_text("hello\n")
    g("add", "-A")
    g("commit", "-q", "-m", "init")
    return repo
