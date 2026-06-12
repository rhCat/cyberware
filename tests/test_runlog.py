"""Unit: runlog.run_dir / is_default — where a run's artifacts are grouped."""
import os

import pytest
from infra.govern import runlog


@pytest.mark.parametrize("val", ["", "   ", "<default>", "${record_store}", None, 5])
def test_is_default_true_for_placeholders(val):
    assert runlog.is_default(val) is True


@pytest.mark.parametrize("val", ["/abs/path", "~/x", "relative/dir"])
def test_is_default_false_for_real_paths(val):
    assert runlog.is_default(val) is False


def test_explicit_record_store_is_used_verbatim(tmp_path):
    L = {"skill": "s", "perk": "p", "record_store": str(tmp_path / "x"), "vars": {}}
    assert runlog.run_dir(L) == str(tmp_path / "x")


def test_explicit_record_store_expands_user_and_absolutizes():
    L = {"skill": "s", "perk": "p", "record_store": "~/cw_x", "vars": {}}
    assert runlog.run_dir(L) == os.path.expanduser("~/cw_x")


def test_placeholder_falls_back_to_grouped_default(monkeypatch, tmp_path):
    monkeypatch.setattr(runlog, "DEFAULT_ROOT", str(tmp_path / "logs"))
    L = {"skill": "search", "perk": "loc", "record_store": "<default>", "vars": {"A": "1"}}
    d = runlog.run_dir(L)
    assert d.startswith(str(tmp_path / "logs"))
    assert "search__loc__" in d


def test_run_dir_deterministic_and_var_sensitive(monkeypatch, tmp_path):
    monkeypatch.setattr(runlog, "DEFAULT_ROOT", str(tmp_path))
    a = runlog.run_dir({"skill": "s", "perk": "p", "vars": {"A": "1"}})
    a2 = runlog.run_dir({"skill": "s", "perk": "p", "vars": {"A": "1"}})
    b = runlog.run_dir({"skill": "s", "perk": "p", "vars": {"A": "2"}})
    assert a == a2          # same vars → same dir
    assert a != b           # different vars → different dir
