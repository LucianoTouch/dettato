from unittest.mock import patch, MagicMock
from dettato import startup


def test_is_startup_enabled_false_when_key_missing():
    with patch("dettato.startup.winreg") as mock_winreg:
        mock_winreg.OpenKey.side_effect = FileNotFoundError()
        assert startup.is_startup_enabled() is False


def test_is_startup_enabled_true_when_value_present():
    with patch("dettato.startup.winreg") as mock_winreg:
        mock_key = MagicMock()
        mock_winreg.OpenKey.return_value.__enter__.return_value = mock_key
        mock_winreg.QueryValueEx.return_value = ("some command", 1)
        assert startup.is_startup_enabled() is True


def test_enable_startup_sets_registry_value():
    with patch("dettato.startup.winreg") as mock_winreg:
        mock_key = MagicMock()
        mock_winreg.OpenKey.return_value.__enter__.return_value = mock_key
        startup.enable_startup()
        mock_winreg.SetValueEx.assert_called_once()
        args = mock_winreg.SetValueEx.call_args[0]
        assert args[1] == "Dettato"


def test_disable_startup_deletes_value_without_error_when_missing():
    with patch("dettato.startup.winreg") as mock_winreg:
        mock_key = MagicMock()
        mock_winreg.OpenKey.return_value.__enter__.return_value = mock_key
        mock_winreg.DeleteValue.side_effect = FileNotFoundError()
        startup.disable_startup()


def test_enable_startup_quotes_exe_path_with_spaces_and_drops_legacy_value():
    with patch("dettato.startup.winreg") as mock_winreg, patch(
        "dettato.paths.launch_command", return_value=[r"C:\My Programs\Dettato\Dettato.exe"]
    ):
        startup.enable_startup()
        args = mock_winreg.SetValueEx.call_args[0]
        assert args[4] == r'"C:\My Programs\Dettato\Dettato.exe"'
        deleted = [c[0][1] for c in mock_winreg.DeleteValue.call_args_list]
        assert deleted == ["DictationTool"]
