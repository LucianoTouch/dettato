import logging
import os
import shutil
import sys
from pathlib import Path

logger = logging.getLogger(__name__)

APP_NAME = "Dettato"
_LEGACY_DATA_DIR_NAME = "dictation-tool"


def _appdata() -> Path:
    return Path(os.environ.get("APPDATA", str(Path.home())))


def is_frozen() -> bool:
    """True when running from the PyInstaller-built Dettato.exe."""
    return getattr(sys, "frozen", False)


def data_dir() -> Path:
    return _appdata() / APP_NAME


def log_file_path() -> Path:
    return data_dir() / "dettato.log"


def resource_path(name: str) -> Path:
    """Locate a bundled read-only file (beep, icon) in dev and in the exe.

    PyInstaller unpacks data files under sys._MEIPASS; from a source
    checkout they live next to main.py.
    """
    base = Path(getattr(sys, "_MEIPASS", Path(__file__).resolve().parent.parent))
    return base / "assets" / name


def launch_command() -> list:
    """The argv that starts Dettato again (for autostart and restart)."""
    if is_frozen():
        return [sys.executable]
    pythonw = sys.executable.replace("python.exe", "pythonw.exe")
    main_script = Path(__file__).resolve().parent.parent / "main.py"
    return [pythonw, str(main_script)]


def migrate_legacy_data(appdata: Path = None) -> None:
    """Move config/log from the pre-rename %APPDATA%\\dictation-tool folder.

    Only runs when the new folder doesn't exist yet, so it never
    overwrites settings saved by Dettato itself.
    """
    appdata = appdata or _appdata()
    legacy = appdata / _LEGACY_DATA_DIR_NAME
    new = appdata / APP_NAME
    if not legacy.is_dir() or new.exists():
        return
    try:
        new.mkdir(parents=True)
        legacy_config = legacy / "config.json"
        if legacy_config.exists():
            shutil.copy2(legacy_config, new / "config.json")
        shutil.rmtree(legacy, ignore_errors=True)
    except OSError as e:
        logger.warning(f"Migrazione dei vecchi dati da '{legacy}' non riuscita: {e}")
