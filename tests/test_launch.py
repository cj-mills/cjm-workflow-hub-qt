"""launch.py contract: the core-env resolution ladder (resolve_stage_tui
carried, Qt command map) and the donor's launch argv."""

import os
import stat

from cjm_workflow_hub_qt.launch import build_stage_cmd, resolve_stage_app, STAGE_APPS


def _fake_exe(path):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("#!/bin/sh\n")
    path.chmod(path.stat().st_mode | stat.S_IEXEC)
    return path


def test_resolves_from_the_sibling_core_env(tmp_path, monkeypatch):
    monkeypatch.setenv("PATH", str(tmp_path / "empty"))
    exe = _fake_exe(tmp_path / "cjm-transcript-decomp-core" / "bin"
                    / "cjm-transcript-decomp-qt")
    assert resolve_stage_app("decomp", envs_root=str(tmp_path)) == str(exe)


def test_path_wins_over_the_sibling_env(tmp_path, monkeypatch):
    on_path = _fake_exe(tmp_path / "pathbin" / "cjm-transcription-qt")
    _fake_exe(tmp_path / "cjm-transcription-core" / "bin" / "cjm-transcription-qt")
    monkeypatch.setenv("PATH", str(tmp_path / "pathbin"))
    assert resolve_stage_app("transcription",
                             envs_root=str(tmp_path)) == str(on_path)


def test_missing_everywhere_resolves_none(tmp_path, monkeypatch):
    monkeypatch.setenv("PATH", str(tmp_path / "empty"))
    assert resolve_stage_app("correction", envs_root=str(tmp_path)) is None


def test_stage_app_map_covers_the_three_stages_with_core_env_names():
    assert set(STAGE_APPS) == {"transcription", "decomp", "correction"}
    for cmd, env in STAGE_APPS.values():
        assert cmd.endswith("-qt")
        assert env.endswith("-core")


def test_build_stage_cmd_carries_the_explicit_db_guardrail():
    assert build_stage_cmd("/bin/x", "decomp", "/tmp/g.db") == \
        ["/bin/x", "--graph-db-path", "/tmp/g.db"]
    assert build_stage_cmd("/bin/x", "decomp", None) == ["/bin/x"]


def test_build_stage_cmd_correction_opens_on_a_source():
    assert build_stage_cmd("/bin/x", "correction", "/tmp/g.db", "src-1") == \
        ["/bin/x", "--graph-db-path", "/tmp/g.db", "--source", "src-1"]
