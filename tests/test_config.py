import json
from dictation_tool.config import load_config, save_config, Config


def test_load_config_creates_default_when_missing(tmp_path):
    config_path = tmp_path / "config.json"
    config = load_config(config_path)
    assert config.hotkey == "ctrl+space"
    assert config.model_size == "large-v3"
    assert config.device == "auto"
    assert config.auto_paste is True
    assert config.run_on_startup is False
    assert config_path.exists()


def test_load_config_merges_partial_file(tmp_path):
    config_path = tmp_path / "config.json"
    config_path.write_text(json.dumps({"hotkey": "ctrl+alt+space"}), encoding="utf-8")
    config = load_config(config_path)
    assert config.hotkey == "ctrl+alt+space"
    assert config.model_size == "large-v3"


def test_save_config_roundtrip(tmp_path):
    config_path = tmp_path / "config.json"
    original = Config(hotkey="ctrl+shift+space", auto_paste=False)
    save_config(original, config_path)
    loaded = load_config(config_path)
    assert loaded.hotkey == "ctrl+shift+space"
    assert loaded.auto_paste is False
