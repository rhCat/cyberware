"""Unit + integration: chipfetch — the chip acquisition + validation gate in front of govd.

Local mode resolves the baked chip; CLOUD_MODE clones the feed-stock repo at a ref and validates it the
same way. Either way a drifted chip refuses to serve. The token is never persisted or echoed.
"""
import json
import os
import shutil
import subprocess

import pytest

from infra import registry
from infra.govern import chipfetch
from infra.tool import skill_index


# ── a miniature feed-stock repo: 2 real skills + indexes + manifest, git-tagged ──

def _git(repo, *args):
    subprocess.run(["git", "-C", str(repo), *args], check=True, capture_output=True)


@pytest.fixture
def chip_repo(tmp_path):
    """A git repo that IS a skillChip: two skills copied from the real chip, manifest written, tag v1;
    then one more commit on main (an extra skill) so main != v1."""
    repo = tmp_path / "feedstock"
    for s in ("search", "fs"):
        shutil.copytree(os.path.join(registry.SKILLCHIP, s), repo / s)
    skill_index.write_manifest(str(repo))
    subprocess.run(["git", "init", "-q", "-b", "main", str(repo)], check=True, capture_output=True)
    _git(repo, "config", "user.email", "t@t")
    _git(repo, "config", "user.name", "t")
    _git(repo, "config", "commit.gpgsign", "false")
    _git(repo, "config", "tag.gpgsign", "false")               # a global signing config must not break the fixture
    _git(repo, "add", "-A")
    _git(repo, "commit", "-q", "-m", "chip v1")
    _git(repo, "tag", "v1")
    shutil.copytree(os.path.join(registry.SKILLCHIP, "data"), repo / "data")   # main grows a 3rd skill
    skill_index.write_manifest(str(repo))
    _git(repo, "add", "-A")
    _git(repo, "commit", "-q", "-m", "chip v2: +data")
    return repo


def test_local_mode_resolves_the_baked_chip_and_validates(monkeypatch):
    monkeypatch.delenv("CLOUD_MODE", raising=False)
    chip, prov = chipfetch.resolve()
    assert chip == registry.SKILLCHIP and prov["mode"] == "local"
    assert chipfetch.validate(chip) == []                       # the bundled chip must always pass its own gate
    assert chipfetch.chip_sha(chip) == json.load(open(registry.manifest_path()))["chip_sha"]


def test_cloud_mode_clones_at_the_tag_and_validates(chip_repo, tmp_path, monkeypatch):
    monkeypatch.setenv("CLOUD_MODE", "1")
    monkeypatch.setenv("CLOUD_SOURCE", str(chip_repo))
    monkeypatch.setenv("CLOUD_SOURCE_TAG", "v1")
    monkeypatch.setenv("CLOUD_CHIP_DIR", str(tmp_path / "clone"))
    chip, prov = chipfetch.resolve()
    assert prov["mode"] == "cloud" and prov["ref"] == "v1" and len(prov["commit"]) == 40
    assert chipfetch.validate(chip) == []                       # the SAME gate as local
    assert sorted(skill_index.all_skills(chip)) == ["fs", "search"]   # v1 content, not main's 3 skills


def test_cloud_mode_follows_a_branch_and_a_raw_sha(chip_repo, tmp_path, monkeypatch):
    monkeypatch.setenv("CLOUD_MODE", "1")
    monkeypatch.setenv("CLOUD_SOURCE", str(chip_repo))
    monkeypatch.setenv("CLOUD_CHIP_DIR", str(tmp_path / "clone"))
    monkeypatch.setenv("CLOUD_SOURCE_TAG", "main")              # a branch ref
    chip, _ = chipfetch.resolve()
    assert sorted(skill_index.all_skills(chip)) == ["data", "fs", "search"]
    sha_v1 = subprocess.run(["git", "-C", str(chip_repo), "rev-parse", "v1"],
                            capture_output=True, text=True, check=True).stdout.strip()
    monkeypatch.setenv("CLOUD_SOURCE_TAG", sha_v1)              # a raw commit sha (the --branch fallback path)
    chip, prov = chipfetch.resolve()
    assert prov["commit"] == sha_v1
    assert sorted(skill_index.all_skills(chip)) == ["fs", "search"]


def test_a_drifted_cloud_chip_refuses(chip_repo, tmp_path, monkeypatch):
    # commit a TAMPERED state: change a pinned file without regenerating the index
    p = chip_repo / "fs" / "SKILL.md"
    p.write_text(p.read_text() + "\n# tampered\n")
    _git(chip_repo, "add", "-A")
    _git(chip_repo, "commit", "-q", "-m", "tamper")
    monkeypatch.setenv("CLOUD_MODE", "1")
    monkeypatch.setenv("CLOUD_SOURCE", str(chip_repo))
    monkeypatch.setenv("CLOUD_SOURCE_TAG", "main")
    monkeypatch.setenv("CLOUD_CHIP_DIR", str(tmp_path / "clone"))
    chip, _ = chipfetch.resolve()
    problems = chipfetch.validate(chip)
    assert problems and any("fs" in p for p in problems)        # the gate catches it — govd never starts


def test_url_is_sanitized_and_creds_are_extracted_not_embedded():
    # inline creds are pulled OUT of the url and never re-embedded; the token rides askpass, not the url
    clean, tok = chipfetch._split_creds("https://x-access-token:ghp_AAA@github.com/o/c.git", None)
    assert clean == "https://github.com/o/c.git" and tok == "ghp_AAA"
    assert chipfetch._sanitize("https://u:p@host:22/x") == "https://host:22/x"
    assert chipfetch._split_creds("/local/path", "tok") == ("/local/path", "tok")   # nothing to strip
    env, helper = chipfetch._askpass_env("tok123", base_env={})
    body = open(helper).read(); os.unlink(helper)
    assert "tok123" not in body and env["GIT_TOKEN"] == "tok123" and env["GIT_TERMINAL_PROMPT"] == "0"


def test_token_never_persists_in_the_clone(chip_repo, tmp_path):
    """Even with a token set, the token is never written to disk — not in .git/config, not anywhere."""
    dest = tmp_path / "clone"
    chip, _ = chipfetch.fetch_cloud(str(chip_repo), "v1", token="sekret", dest=str(dest))
    blob = subprocess.run(["grep", "-rIa", "sekret", str(dest / ".git")], capture_output=True, text=True)
    assert blob.returncode != 0 and "sekret" not in (dest / ".git" / "config").read_text()


def test_a_bad_ref_with_a_token_leaves_NOTHING_on_disk(chip_repo, tmp_path):
    """The P1 path: clone ok, checkout fails — the dest (and any token) must be gone, not left behind."""
    dest = tmp_path / "clone"
    with pytest.raises(SystemExit):
        chipfetch.fetch_cloud(str(chip_repo), "no-such-ref", token="sekret", dest=str(dest))
    assert not dest.exists()                                    # no half-clone, no .git/config, no token


def test_inline_creds_in_source_are_sanitized_from_provenance(chip_repo, tmp_path, monkeypatch):
    monkeypatch.setenv("CLOUD_MODE", "1")
    monkeypatch.setenv("CLOUD_SOURCE", f"file://x-access-token:ghp_SECRET@{chip_repo}")  # creds inline (no separate token)
    monkeypatch.setenv("CLOUD_SOURCE_TAG", "v1")
    monkeypatch.setenv("CLOUD_CHIP_DIR", str(tmp_path / "clone"))
    chip, prov = chipfetch.resolve()
    assert "ghp_SECRET" not in prov["source"] and "x-access-token" not in prov["source"]


def test_exec_hands_govd_the_validated_chip(chip_repo, tmp_path, monkeypatch, capsys):
    monkeypatch.setenv("CLOUD_MODE", "1")
    monkeypatch.setenv("CLOUD_SOURCE", str(chip_repo))
    monkeypatch.setenv("CLOUD_SOURCE_TAG", "v1")
    monkeypatch.setenv("CLOUD_CHIP_DIR", str(tmp_path / "clone"))
    seen = {}
    monkeypatch.setattr(os, "execvpe", lambda f, argv, env: seen.update(f=f, argv=argv, env=env))
    monkeypatch.setattr("sys.argv", ["chipfetch", "--exec", "python3", "-m", "infra.govern.govd"])
    monkeypatch.setenv("CLOUD_SOURCE_TOKEN", "sekret")          # a boot secret that must NOT reach govd
    chipfetch.main()
    assert seen["env"]["CYBERWARE_SKILLCHIP"] == str(tmp_path / "clone")
    prov = json.loads(seen["env"]["GOVD_CHIP_PROVENANCE"])
    assert prov["mode"] == "cloud" and prov["chip_sha"] and prov["skills"] == 2
    # the secret (and the other boot-only vars) are dropped from govd's environment — no /proc leak, no TLC-child inherit
    for k in ("CLOUD_SOURCE_TOKEN", "CLOUD_MODE", "CLOUD_SOURCE", "CLOUD_SOURCE_TAG"):
        assert k not in seen["env"], f"{k} leaked into govd's env"
    assert "chip VALID" in capsys.readouterr().out


def test_main_exits_nonzero_on_a_drifted_chip(chip_repo, tmp_path, monkeypatch):
    p = chip_repo / "search" / "perks.json"
    p.write_text(p.read_text().replace("grep", "grpe"))         # tamper without re-indexing
    _git(chip_repo, "add", "-A")
    _git(chip_repo, "commit", "-q", "-m", "tamper")
    monkeypatch.setenv("CLOUD_MODE", "1")
    monkeypatch.setenv("CLOUD_SOURCE", str(chip_repo))
    monkeypatch.setenv("CLOUD_SOURCE_TAG", "main")
    monkeypatch.setenv("CLOUD_CHIP_DIR", str(tmp_path / "clone"))
    monkeypatch.setattr("sys.argv", ["chipfetch"])
    with pytest.raises(SystemExit) as e:
        chipfetch.main()
    assert e.value.code == 1
