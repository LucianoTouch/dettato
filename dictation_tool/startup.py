import sys
import winreg
from pathlib import Path

RUN_KEY_PATH = r"Software\Microsoft\Windows\CurrentVersion\Run"
APP_NAME = "DictationTool"


def _run_key(access):
    return winreg.OpenKey(winreg.HKEY_CURRENT_USER, RUN_KEY_PATH, 0, access)


def _startup_command() -> str:
    pythonw = sys.executable.replace("python.exe", "pythonw.exe")
    main_script = str(Path(__file__).resolve().parent.parent / "main.py")
    return f'"{pythonw}" "{main_script}"'


def enable_startup() -> None:
    with _run_key(winreg.KEY_SET_VALUE) as key:
        winreg.SetValueEx(key, APP_NAME, 0, winreg.REG_SZ, _startup_command())


def disable_startup() -> None:
    try:
        with _run_key(winreg.KEY_SET_VALUE) as key:
            winreg.DeleteValue(key, APP_NAME)
    except FileNotFoundError:
        pass


def is_startup_enabled() -> bool:
    try:
        with _run_key(winreg.KEY_READ) as key:
            winreg.QueryValueEx(key, APP_NAME)
            return True
    except FileNotFoundError:
        return False
