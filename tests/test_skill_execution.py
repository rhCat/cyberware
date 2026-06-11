"""Per-skill END-TO-END execution through the governed channel, on hermetic fixtures.

Each test compiles a perk and runs it through executor.py (--all), then asserts exit 0 + the declared
output. Skills needing external services (postgres, docker, network) are skipif-guarded; repo-mutating
internals (cws-create/scaffold, cws-addperk/apply) are covered by the contract tests, not run live.
"""
import json
import os
import shutil
import subprocess

import pytest

NET = pytest.mark.skip(reason="network-dependent — not run in CI to avoid flakiness")


def _ok(result, run, output):
    assert result.returncode == 0, result.stdout + result.stderr
    assert os.path.isfile(os.path.join(run, output)), f"missing output {output}"


# ── pure / filesystem skills ───────────────────────────────────────────────
def test_codebaseqc_audit(run_skill, sample_repo):
    r, run = run_skill("codebaseqc", "audit",
                       {"PROJECT_DIR": str(sample_repo), "SRC_DIR": "src", "TEST_DIR": "tests"})
    _ok(r, run, "coverage_gaps.json")
    assert isinstance(json.load(open(f"{run}/usage_gaps.json")), (dict, list))


def test_codebaseqc_setup_installs_landing_script(run_skill, tmp_path):
    target = tmp_path / "tools"
    r, _ = run_skill("codebaseqc", "setup", {"TARGET_DIR": str(target)})
    assert r.returncode == 0, r.stdout + r.stderr
    assert (target / "codebaseqc.sh").is_file()
    assert (target / "cbqc_usage.py").is_file()


def test_search_grep(run_skill, sample_repo):
    r, run = run_skill("search", "grep", {"PATTERN": "def", "SEARCH_DIR": str(sample_repo)})
    _ok(r, run, "matches.txt")


def test_search_loc(run_skill, sample_repo):
    r, run = run_skill("search", "loc", {"SEARCH_DIR": str(sample_repo)})
    _ok(r, run, "loc.txt")


def test_fs_archive(run_skill, sample_repo):
    r, run = run_skill("fs", "archive", {"SOURCE_DIR": str(sample_repo)})
    _ok(r, run, "archive.tar.gz")
    assert os.path.getsize(f"{run}/archive.tar.gz") > 0


def test_fs_find_large(run_skill, sample_repo):
    r, run = run_skill("fs", "find_large", {"SEARCH_DIR": str(sample_repo), "MIN_SIZE": "1c"})
    _ok(r, run, "large_files.txt")


def test_data_csv2json(run_skill, tmp_path):
    csv = tmp_path / "d.csv"
    csv.write_text("id,name\n1,alice\n2,bob\n")
    r, run = run_skill("data", "csv2json", {"CSV_FILE": str(csv)})
    _ok(r, run, "data.json")
    rows = json.load(open(f"{run}/data.json"))
    assert len(rows) == 2 and rows[0]["name"] == "alice"


@pytest.mark.skipif(not shutil.which("jq"), reason="jq not installed")
def test_data_jq(run_skill, tmp_path):
    js = tmp_path / "in.json"
    js.write_text('{"items":[1,2,3]}')
    r, run = run_skill("data", "jq", {"JSON_FILE": str(js), "QUERY": ".items | length"})
    _ok(r, run, "jq_result.json")


# ── git skills (git is present in CI) ──────────────────────────────────────
def test_git_ops_status(run_skill, git_repo):
    r, run = run_skill("git_ops", "status", {"REPO_DIR": str(git_repo)})
    _ok(r, run, "git_status.txt")


def test_git_ops_snapshot_commits_when_dirty(run_skill, git_repo):
    (git_repo / "new.txt").write_text("change\n")
    r, run = run_skill("git_ops", "snapshot", {"REPO_DIR": str(git_repo), "MESSAGE": "test snap"})
    assert r.returncode == 0, r.stdout + r.stderr
    snap = json.load(open(f"{run}/git_snapshot.json"))
    assert snap["status"] == "ok" and "sha" in snap


def test_release_tag(run_skill, git_repo):
    r, run = run_skill("release", "tag", {"REPO_DIR": str(git_repo), "VERSION": "v0.0.1"})
    _ok(r, run, "release_tag.json")
    tags = subprocess.run(["git", "tag"], cwd=git_repo, capture_output=True, text=True).stdout
    assert "v0.0.1" in tags


# ── CI-workflow generators (deliverable lands in PROJECT_DIR) ───────────────
def test_ci_codeqc_generates_workflow(run_skill, tmp_path):
    proj = tmp_path / "proj"
    proj.mkdir()
    r, _ = run_skill("ci-codeqc", "github_actions", {"PROJECT_DIR": str(proj), "SRC_DIR": "src"})
    assert r.returncode == 0, r.stdout + r.stderr
    assert (proj / ".github" / "workflows" / "codeqc.yml").is_file()


def test_datadog_generates_workflow(run_skill, tmp_path):
    proj = tmp_path / "proj"
    proj.mkdir()
    r, _ = run_skill("datadog", "github_ci",
                     {"PROJECT_DIR": str(proj), "SERVICE": "app", "TEST_CMD": "pytest"})
    assert r.returncode == 0, r.stdout + r.stderr
    assert (proj / ".github" / "workflows" / "datadog-ci.yml").is_file()


# ── python QC ──────────────────────────────────────────────────────────────
def test_py_qc_test(run_skill, sample_repo):
    r, run = run_skill("py_qc", "test", {"PROJECT_DIR": str(sample_repo), "TEST_DIR": "tests"})
    _ok(r, run, "pytest.out")


@pytest.mark.skipif(not (shutil.which("ruff") or shutil.which("flake8")),
                    reason="no python linter installed")
def test_py_qc_lint(run_skill, sample_repo):
    r, run = run_skill("py_qc", "lint", {"PROJECT_DIR": str(sample_repo), "LINT_TARGET": "src"})
    _ok(r, run, "lint.out")


# ── cws internals: read-only evaluators run; mutating perks are contract-only ──
def test_cws_create_evaluate(run_skill):
    r, run = run_skill("cws-create", "evaluate",
                       {"SKILL_NAME": "pg-backup", "SKILL_DESC": "run pg_dump to back up a database"})
    _ok(r, run, "evaluation.json")


def test_cws_addperk_evaluate(run_skill):
    r, run = run_skill("cws-addperk", "evaluate",
                       {"SKILL": "git_ops", "PERK": "push", "PERK_DESC": "push the branch to a remote"})
    _ok(r, run, "perk_eval.json")


# ── network / service skills: skipped to keep CI hermetic (contract tests still cover them) ──
@NET
def test_http_get(run_skill):
    run_skill("http", "get", {"URL": "https://example.com"})


@NET
def test_net_healthcheck(run_skill):
    run_skill("net", "healthcheck", {"URL": "https://example.com/health"})


@pytest.mark.skipif(not shutil.which("psql"), reason="psql not installed")
@pytest.mark.skip(reason="needs a live Postgres — contract test covers compilation")
def test_pg_ops_select():
    pass


@pytest.mark.skipif(shutil.which("docker") is None, reason="docker not installed")
@pytest.mark.skip(reason="needs a docker daemon — contract test covers compilation")
def test_docker_ps():
    pass
