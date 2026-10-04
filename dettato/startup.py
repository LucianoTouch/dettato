import subprocess
import winreg

from dettato import paths

RUN_KEY_PATH = r"Software\Microsoft\Windows\CurrentVersion\Run"
APP_NAME = "Dettato"
# Pre-rename value name: removed whenever autostart is touched so the old
# install doesn't launch alongside Dettato at login.
_LEGACY_APP_NAME = "DictationTool"


def _run_key(access):
    return winreg.OpenKey(winreg.HKEY_CURRENT_USER, RUN_KEY_PATH, 0, access)


def _startup_command() -> str:
    return subprocess.list2cmdline(paths.launch_command())


def _delete_value(name: str) -> None:
    try:
        with _run_key(winreg.KEY_SET_VALUE) as key:
            winreg.DeleteValue(key, name)
    except FileNotFoundError:
        pass


def enable_startup() -> None:
    with _run_key(winreg.KEY_SET_VALUE) as key:
        winreg.SetValueEx(key, APP_NAME, 0, winreg.REG_SZ, _startup_command())
    _delete_value(_LEGACY_APP_NAME)


def disable_startup() -> None:
    _delete_value(APP_NAME)
    _delete_value(_LEGACY_APP_NAME)


def is_startup_enabled() -> bool:
    try:
        with _run_key(winreg.KEY_READ) as key:
            winreg.QueryValueEx(key, APP_NAME)
            return True
    except FileNotFoundError:
        return False
