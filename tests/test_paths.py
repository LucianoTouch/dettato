import json
import sys
from pathlib import Path
from unittest.mock import patch

from dettato import paths


def test_data_dir_is_named_dettato(monkeypatch, tmp_path):
    monkeypatch.setenv("APPDATA", str(tmp_path))
    assert paths.data_dir() == tmp_path / "Dettato"
    assert paths.log_file_path().parent == tmp_path / "Dettato"


def test_migrate_moves_legacy_config_and_removes_old_folder(tmp_path):
    legacy = tmp_path / "dictation-tool"
    legacy.mkdir()
    (legacy / "config.json").write_text(json.dumps({"hotkey": "ctrl+alt+d"}), encoding="utf-8")
    (legacy / "dictation.log").write_text("old log", encoding="utf-8")

    paths.migrate_legacy_data(tmp_path)

    new_config = tmp_path / "Dettato" / "config.json"
    assert json.loads(new_config.read_text(encoding="utf-8")) == {"hotkey": "ctrl+alt+d"}
    assert not legacy.exists()


def test_migrate_never_overwrites_existing_dettato_data(tmp_path):
    legacy = tmp_path / "dictation-tool"
    legacy.mkdir()
    (legacy / "config.json").write_text('{"hotkey": "old"}', encoding="utf-8")
    new = tmp_path / "Dettato"
    new.mkdir()
    (new / "config.json").write_text('{"hotkey": "new"}', encoding="utf-8")

    paths.migrate_legacy_data(tmp_path)

    assert (new / "config.json").read_text(encoding="utf-8") == '{"hotkey": "new"}'


def test_migrate_is_noop_without_legacy_folder(tmp_path):
    paths.migrate_legacy_data(tmp_path)
    assert not (tmp_path / "Dettato").exists()


def test_resource_path_points_at_repo_assets_from_source():
    assert paths.resource_path("bip.mp3").exists()
    assert paths.resource_path("dettato.ico").exists()


def test_resource_path_uses_bundle_dir_when_frozen(tmp_path):
    with patch.object(sys, "_MEIPASS", str(tmp_path), create=True):
        assert paths.resource_path("bip.mp3") == tmp_path / "assets" / "bip.mp3"


def test_launch_command_from_source_uses_pythonw_and_main_py():
    with patch.object(sys, "executable", r"C:\Py\python.exe"):
        cmd = paths.launch_command()
    assert cmd[0] == r"C:\Py\pythonw.exe"
    assert Path(cmd[1]).name == "main.py"


def test_launch_command_when_frozen_is_just_the_exe():
    with patch.object(sys, "frozen", True, create=True), patch.object(
        sys, "executable", r"C:\Programs\Dettato\Dettato.exe"
    ):
        assert paths.launch_command() == [r"C:\Programs\Dettato\Dettato.exe"]
