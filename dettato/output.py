import time
import logging
import pyperclip
import keyboard

logger = logging.getLogger(__name__)


class OutputHandler:
    def __init__(self, paste_delay: float = 0.5):
        self.paste_delay = paste_delay

    def paste(self, text: str, auto_paste: bool = True) -> None:
        if not text:
            return

        if not auto_paste:
            # Nothing to restore: the point of this mode is to leave the
            # transcribed text sitting on the clipboard for the user to
            # paste manually whenever they're ready.
            pyperclip.copy(text)
            return

        original_clipboard = None
        try:
            original_clipboard = pyperclip.paste()
        except Exception as e:
            logger.warning(f"Impossibile leggere la clipboard corrente: {e}")

        pyperclip.copy(text)
        keyboard.send("ctrl+v")
        time.sleep(self.paste_delay)

        if original_clipboard:
            try:
                pyperclip.copy(original_clipboard)
            except Exception as e:
                logger.warning(f"Impossibile ripristinare la clipboard originale: {e}")
