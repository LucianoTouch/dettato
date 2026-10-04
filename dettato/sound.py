import ctypes
import logging
from pathlib import Path

logger = logging.getLogger(__name__)

_winmm = ctypes.windll.winmm
_ALIAS = "dettato_beep"


def _mci(command: str) -> bool:
    return _winmm.mciSendStringW(command, None, 0, None) == 0


def play(path: Path, wait: bool = False) -> None:
    """Play an audio file (mp3 included) via the Windows MCI.

    Uses winmm directly instead of adding a playback dependency: MCI's
    generic file-extension mapping already knows how to decode mp3 on
    Windows. `close` first in case a previous non-waiting playback of
    the same alias is still open.
    """
    _mci(f"close {_ALIAS}")
    if not _mci(f'open "{path}" alias {_ALIAS}'):
        logger.warning(f"Impossibile aprire il suono '{path}'")
        return
    if not _mci(f"play {_ALIAS}" + (" wait" if wait else "")):
        logger.warning(f"Impossibile riprodurre il suono '{path}'")
    if wait:
        _mci(f"close {_ALIAS}")
