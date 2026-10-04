from unittest.mock import MagicMock, patch

import pytest

from dettato import app as app_module
from dettato.app import App, State
from dettato.config import Config


def _bare_app(config=None):
    """An App without its real tray/window/audio, for testing logic only."""
    app = App.__new__(App)
    app.config = config or Config()
    app.state = State.LOADING
    app.stt_engine = None
    app._load_error = None
    app.tray = MagicMock()
    app.window = MagicMock()
    app.hotkey_listener = MagicMock()
    app.hotkey_listener.start.return_value = True
    app._download_text = None
    app.update = None
    app.update_status = None
    app._updating = False
    app._notified_version = None
    return app


@pytest.fixture(autouse=True)
def _model_already_downloaded():
    with patch("dettato.stt.is_model_cached", return_value=True):
        yield


def test_load_retries_after_a_transient_model_error():
    app = _bare_app()
    engine = MagicMock(device="cuda", model_size="large-v3")
    with patch("dettato.stt.SttEngine", side_effect=[RuntimeError("Unable to open file"), engine]), patch.object(
        app_module, "_LOAD_RETRY_DELAY", 0
    ):
        app._load()
    assert app.stt_engine is engine
    assert app.state == State.IDLE
    assert app._load_error is None


def test_load_gives_up_and_reports_after_all_attempts():
    app = _bare_app()
    with patch("dettato.stt.SttEngine", side_effect=RuntimeError("boom")), patch.object(
        app_module, "_LOAD_RETRY_DELAY", 0
    ):
        app._load()
    assert app.state == State.LOADING
    assert "boom" in app.status_text()
    app.tray.notify.assert_called_once()


def test_apply_settings_rejects_unregistrable_hotkey_and_keeps_old_one(tmp_path):
    app = _bare_app()
    app.state = State.IDLE
    old_listener = app.hotkey_listener
    failing = MagicMock()
    failing.start.return_value = False
    with patch("dettato.app.HotkeyListener", return_value=failing), patch("dettato.app.save_config") as save:
        ok = app.apply_settings(Config(hotkey="ctrl+alt+x"), needs_restart=False)
    assert ok is False
    assert app.config.hotkey == "ctrl+space"
    assert app.hotkey_listener is old_listener
    old_listener.start.assert_called_once()
    save.assert_not_called()


def test_apply_settings_saves_and_switches_hotkey():
    app = _bare_app()
    app.state = State.IDLE
    new_listener = MagicMock()
    new_listener.start.return_value = True
    with patch("dettato.app.HotkeyListener", return_value=new_listener), patch(
        "dettato.app.save_config"
    ) as save, patch("dettato.app.startup.is_startup_enabled", return_value=False):
        ok = app.apply_settings(Config(hotkey="ctrl+alt+x", auto_paste=False), needs_restart=False)
    assert ok is True
    assert app.hotkey_listener is new_listener
    assert app.config.auto_paste is False
    assert app.tray.hotkey == "ctrl+alt+x"
    save.assert_called_once()


def test_status_shows_model_download_progress_while_loading():
    app = _bare_app()
    app._download_text = "Download del modello: 1,2 / 3,1 GB (solo la prima volta)…"
    assert "1,2 / 3,1 GB" in app.status_text()


def _release(version="1.2.0"):
    from dettato.updater import Asset, Release

    return Release(version, "note", "rid", Asset("Dettato-Setup.exe", "u", "0" * 64, 1), None)


def test_check_for_updates_notifies_once_per_version():
    app = _bare_app()
    with patch("dettato.app.updater.runtime_id", return_value="rid"), patch(
        "dettato.app.updater.check", return_value=_release()
    ):
        app.check_for_updates()
        app.check_for_updates()
    assert app.update.version == "1.2.0"
    assert app.tray.notify.call_count == 1


def test_check_for_updates_is_silent_when_offline():
    app = _bare_app()
    with patch("dettato.app.updater.runtime_id", return_value="rid"), patch(
        "dettato.app.updater.check", side_effect=OSError("offline")
    ):
        app.check_for_updates()
    assert app.update is None
    app.tray.notify.assert_not_called()


def test_failed_update_is_reported_and_can_be_retried():
    app = _bare_app()
    app.update = _release()
    app._updating = True
    with patch("dettato.app.updater.runtime_id", return_value="rid"), patch(
        "dettato.app.updater.download", side_effect=OSError("rete")
    ):
        app._run_update(app.update)
    assert app._updating is False
    assert "non riuscito" in app.update_status
