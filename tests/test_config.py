import json
from dettato.config import load_config, save_config, Config


def test_load_config_creates_default_when_missing(tmp_path):
    config_path = tmp_path / "config.json"
    config = load_config(config_path)
    assert config.hotkey == "ctrl+space"
    assert config.model_size == "auto"
    assert config.device == "auto"
    assert config.auto_paste is True
    assert config.run_on_startup is False
    assert config_path.exists()


def test_load_config_merges_partial_file(tmp_path):
    config_path = tmp_path / "config.json"
    config_path.write_text(json.dumps({"hotkey": "ctrl+alt+space"}), encoding="utf-8")
    config = load_config(config_path)
    assert config.hotkey == "ctrl+alt+space"
    assert config.model_size == "auto"


def test_load_config_ignores_unknown_keys_instead_of_resetting_to_defaults(tmp_path):
    config_path = tmp_path / "config.json"
    config_path.write_text(
        json.dumps({"hotkey": "ctrl+alt+space", "some_removed_field": "legacy value"}),
        encoding="utf-8",
    )
    config = load_config(config_path)
    assert config.hotkey == "ctrl+alt+space"
    assert not hasattr(config, "some_removed_field")


def test_save_config_roundtrip(tmp_path):
    config_path = tmp_path / "config.json"
    original = Config(hotkey="ctrl+shift+space", auto_paste=False)
    save_config(original, config_path)
    loaded = load_config(config_path)
    assert loaded.hotkey == "ctrl+shift+space"
    assert loaded.auto_paste is False


def test_old_config_without_new_fields_gets_empty_vocabulary_and_replacements(tmp_path):
    config_path = tmp_path / "config.json"
    config_path.write_text(json.dumps({"hotkey": "ctrl+space", "auto_paste": True}), encoding="utf-8")
    config = load_config(config_path)
    assert config.vocabulary == []
    assert config.replacements == {}
    config.vocabulary.append("x")
    assert load_config(config_path).vocabulary == []


def test_vocabulary_and_replacements_roundtrip(tmp_path):
    config_path = tmp_path / "config.json"
    save_config(Config(vocabulary=["Meta Ads"], replacements={"meta ed": "Meta Ads"}), config_path)
    loaded = load_config(config_path)
    assert loaded.vocabulary == ["Meta Ads"]
    assert loaded.replacements == {"meta ed": "Meta Ads"}
