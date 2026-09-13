import logging
import keyboard

logger = logging.getLogger(__name__)


class HotkeyListener:
    def __init__(self, hotkey: str, on_toggle):
        self.hotkey = hotkey
        self.on_toggle = on_toggle
        self._handle = None

    def start(self) -> bool:
        try:
            self._handle = keyboard.add_hotkey(self.hotkey, self.on_toggle)
            return True
        except Exception as e:
            logger.error(f"Impossibile registrare l'hotkey '{self.hotkey}': {e}")
            return False

    def stop(self) -> None:
        if self._handle is not None:
            try:
                keyboard.remove_hotkey(self._handle)
            except Exception as e:
                logger.warning(f"Impossibile rimuovere l'hotkey: {e}")
            finally:
                self._handle = None
