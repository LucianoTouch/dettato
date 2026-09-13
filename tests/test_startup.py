from unittest.mock import patch, MagicMock
from dictation_tool import startup


def test_is_startup_enabled_false_when_key_missing():
    with patch("dictation_tool.startup.winreg") as mock_winreg:
        mock_winreg.OpenKey.side_effect = FileNotFoundError()
        assert startup.is_startup_enabled() is False


def test_is_startup_enabled_true_when_value_present():
    with patch("dictation_tool.startup.winreg") as mock_winreg:
        mock_key = MagicMock()
        mock_winreg.OpenKey.return_value.__enter__.return_value = mock_key
        mock_winreg.QueryValueEx.return_value = ("some command", 1)
        assert startup.is_startup_enabled() is True


def test_enable_startup_sets_registry_value():
    with patch("dictation_tool.startup.winreg") as mock_winreg:
        mock_key = MagicMock()
        mock_winreg.OpenKey.return_value.__enter__.return_value = mock_key
        startup.enable_startup()
        mock_winreg.SetValueEx.assert_called_once()
        args = mock_winreg.SetValueEx.call_args[0]
        assert args[1] == "DictationTool"


def test_disable_startup_deletes_value_without_error_when_missing():
    with patch("dictation_tool.startup.winreg") as mock_winreg:
        mock_key = MagicMock()
        mock_winreg.OpenKey.return_value.__enter__.return_value = mock_key
        mock_winreg.DeleteValue.side_effect = FileNotFoundError()
        startup.disable_startup()
