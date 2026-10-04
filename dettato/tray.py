import logging
import threading
from typing import Callable, Literal

import pystray

from dettato import __version__
from dettato.icons import state_icon

logger = logging.getLogger(__name__)

State = Literal["loading", "idle", "recording", "transcribing"]

_STATE_LABELS = {
    "loading": "caricamento del modello…",
    "idle": "pronto",
    "recording": "sto registrando…",
    "transcribing": "sto trascrivendo…",
}


class TrayIcon:
    def __init__(
        self,
        on_exit: Callable[[], None],
        on_toggle_startup: Callable[[bool], None],
        startup_enabled: bool,
        on_toggle_dictation: Callable[[], None] = lambda: None,
        on_open_settings: Callable[[], None] = lambda: None,
        on_open_log: Callable[[], None] = lambda: None,
        hotkey: str = "",
        update_version: Callable[[], object] = lambda: None,
        on_update: Callable[[], None] = lambda: None,
    ):
        self._update_version = update_version
        self._on_update = on_update
        self._startup_enabled = startup_enabled
        self._on_exit = on_exit
        self._on_toggle_startup = on_toggle_startup
        self._on_toggle_dictation = on_toggle_dictation
        self._on_open_settings = on_open_settings
        self._on_open_log = on_open_log
        self._state: State = "loading"
        self.hotkey = hotkey
        self._icon = pystray.Icon(
            "dettato",
            state_icon("loading"),
            self._tooltip(),
            menu=pystray.Menu(
                pystray.MenuItem(
                    lambda item: "Ferma dettatura" if self._state == "recording" else "Avvia dettatura",
                    lambda icon, item: self._on_toggle_dictation(),
                    enabled=lambda item: self._state in ("idle", "recording"),
                ),
                pystray.Menu.SEPARATOR,
                # default=True: a left click on the tray icon opens the window.
                pystray.MenuItem("Apri Dettato…", lambda icon, item: self._on_open_settings(), default=True),
                pystray.MenuItem("Apri il log", lambda icon, item: self._on_open_log()),
                pystray.MenuItem(
                    "Avvio automatico con Windows",
                    self._handle_toggle_startup,
                    checked=lambda item: self._startup_enabled,
                ),
                pystray.MenuItem(
                    lambda item: f"Aggiorna a Dettato {self._update_version()}…",
                    lambda icon, item: self._on_update(),
                    visible=lambda item: self._update_version() is not None,
                ),
                pystray.Menu.SEPARATOR,
                pystray.MenuItem("Esci", self._handle_exit),
            ),
        )

    @property
    def state(self) -> State:
        return self._state

    def _tooltip(self) -> str:
        text = f"Dettato {__version__} — {_STATE_LABELS[self._state]}"
        if self._state == "idle" and self.hotkey:
            text += f" ({self.hotkey})"
        return text

    def _handle_toggle_startup(self, icon, item):
        self.set_startup_enabled(not self._startup_enabled)
        self._on_toggle_startup(self._startup_enabled)

    def set_startup_enabled(self, enabled: bool) -> None:
        self._startup_enabled = enabled
        self._icon.update_menu()

    def _handle_exit(self, icon, item):
        try:
            self._on_exit()
        finally:
            icon.stop()

    def set_state(self, state: State) -> None:
        self._state = state
        self._icon.icon = state_icon(state)
        self.refresh()

    def refresh(self) -> None:
        self._icon.title = self._tooltip()
        self._icon.update_menu()

    def notify(self, message: str) -> None:
        try:
            self._icon.notify(message, "Dettato")
        except Exception as e:
            logger.warning(f"Notifica non mostrata: {e}")

    def stop(self) -> None:
        self._icon.stop()

    def run(self, setup: Callable[[], None] = None) -> None:
        if setup is None:
            self._icon.run()
            return

        def _setup(icon):
            icon.visible = True
            setup()

        self._icon.run(setup=_setup)

    def run_detached(self) -> None:
        thread = threading.Thread(target=self.run, daemon=True)
        thread.start()
