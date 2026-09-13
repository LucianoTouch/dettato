import threading
from typing import Callable, Literal
from PIL import Image, ImageDraw
import pystray

State = Literal["idle", "recording", "transcribing"]

COLORS = {
    "idle": (128, 128, 128),
    "recording": (220, 30, 30),
    "transcribing": (230, 200, 30),
}


def _make_icon_image(color) -> Image.Image:
    size = 64
    image = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    draw = ImageDraw.Draw(image)
    draw.ellipse((4, 4, size - 4, size - 4), fill=color)
    return image


class TrayIcon:
    def __init__(
        self,
        on_exit: Callable[[], None],
        on_toggle_startup: Callable[[bool], None],
        startup_enabled: bool,
    ):
        self._startup_enabled = startup_enabled
        self._on_exit = on_exit
        self._on_toggle_startup = on_toggle_startup
        self._icon = pystray.Icon(
            "dictation-tool",
            _make_icon_image(COLORS["idle"]),
            "Dictation Tool",
            menu=pystray.Menu(
                pystray.MenuItem(
                    "Avvio automatico con Windows",
                    self._handle_toggle_startup,
                    checked=lambda item: self._startup_enabled,
                ),
                pystray.MenuItem("Esci", self._handle_exit),
            ),
        )

    def _handle_toggle_startup(self, icon, item):
        self._startup_enabled = not self._startup_enabled
        self._on_toggle_startup(self._startup_enabled)

    def _handle_exit(self, icon, item):
        self._on_exit()
        icon.stop()

    def set_state(self, state: State) -> None:
        self._icon.icon = _make_icon_image(COLORS[state])

    def run(self) -> None:
        self._icon.run()

    def run_detached(self) -> None:
        thread = threading.Thread(target=self.run, daemon=True)
        thread.start()
