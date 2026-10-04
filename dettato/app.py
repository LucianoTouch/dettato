import logging
import os
import subprocess
import sys
import tempfile
import threading
import time
from enum import Enum, auto
from pathlib import Path

import keyboard

from dettato import __version__, updater
from dettato.config import Config, save_config
from dettato.audio import AudioRecorder, NoAudioCapturedError
from dettato.postprocess import clean_transcript
from dettato.output import OutputHandler
from dettato.hotkey import HotkeyListener
from dettato.tray import TrayIcon
from dettato.settings_window import SettingsWindow
from dettato import paths, startup, sound

logger = logging.getLogger(__name__)

BEEP_PATH = paths.resource_path("bip.mp3")


class State(Enum):
    LOADING = auto()
    IDLE = auto()
    RECORDING = auto()
    TRANSCRIBING = auto()


_DEVICE_LABELS = {"cuda": "GPU", "cpu": "CPU"}
_LOAD_ATTEMPTS = 3
_LOAD_RETRY_DELAY = 5
_FIRST_UPDATE_CHECK_DELAY = 60
_UPDATE_CHECK_INTERVAL = 24 * 3600


def _gb(n: int) -> str:
    return f"{n / 1e9:.1f}".replace(".", ",")


class App:
    def __init__(self, config: Config):
        self.config = config
        self.state = State.LOADING
        self.stt_engine = None
        self._load_error = None
        self._download_text = None
        # Latest newer release found, and the progress of installing it.
        self.update = None
        self.update_status = None
        self._updating = False
        self._notified_version = None

        # If autostart was enabled from an older location (e.g. the
        # pre-rename install or a moved exe), point it at this copy.
        if startup.is_startup_enabled():
            startup.enable_startup()

        self.recorder = AudioRecorder()
        self.output_handler = OutputHandler()
        self.hotkey_listener = HotkeyListener(config.hotkey, self._on_hotkey_toggle)
        self.tray = TrayIcon(
            on_exit=self._on_exit,
            on_toggle_startup=self._on_toggle_startup,
            startup_enabled=startup.is_startup_enabled(),
            on_toggle_dictation=self._toggle_from_menu,
            on_open_settings=self.show_window,
            on_open_log=self.open_log,
            hotkey=config.hotkey,
            update_version=lambda: self.update.version if self.update else None,
            on_update=self.start_update,
        )
        self.window = SettingsWindow(
            get_config=lambda: self.config,
            get_status=self.status_text,
            is_startup_enabled=startup.is_startup_enabled,
            on_save=self.apply_settings,
            capture_hotkey=self.capture_hotkey,
            on_open_log=self.open_log,
            on_restart=self.restart,
            on_quit=self.request_exit,
            version=__version__,
            get_update=lambda: (self.update, self.update_status, self._updating),
            on_update=self.start_update,
            on_check_updates=lambda: threading.Thread(
                target=self.check_for_updates, kwargs={"manual": True}, daemon=True
            ).start(),
        )

    # ----- startup ---------------------------------------------------------

    def _load(self):
        """Runs once the tray icon is visible, so the user sees Dettato
        start immediately instead of waiting for the model to load."""
        # Imported lazily: pulls in ctranslate2/CUDA, which is slow.
        from dettato import stt

        model = stt.resolve_model(self.config.model_size, stt.resolve_device(self.config.device))
        downloading = threading.Event()
        if not stt.is_model_cached(model):
            downloading.set()
            self.tray.notify(
                f"Primo avvio: scarico il modello di trascrizione ({model}). "
                "Serve solo la prima volta e può richiedere qualche minuto."
            )
            threading.Thread(target=self._watch_download, args=(model, downloading), daemon=True).start()

        try:
            self._load_engine(stt.SttEngine)
        finally:
            downloading.clear()
            self._download_text = None

    def _watch_download(self, model: str, downloading: threading.Event) -> None:
        from dettato import stt

        total = stt.model_download_size(model)
        while downloading.is_set():
            done = stt.model_download_progress(model)
            if total:
                self._download_text = f"Download del modello: {_gb(done)} / {_gb(total)} GB (solo la prima volta)…"
            else:
                self._download_text = f"Download del modello: {_gb(done)} GB scaricati (solo la prima volta)…"
            time.sleep(1)

    def _load_engine(self, SttEngine) -> None:
        for attempt in range(1, _LOAD_ATTEMPTS + 1):
            try:
                self.stt_engine = SttEngine(model_size=self.config.model_size, device=self.config.device)
                break
            except Exception as e:
                # Seen right after install, while the disk was busy/full:
                # the model cache was briefly unreadable, then fine.
                logger.exception(f"Impossibile caricare il modello (tentativo {attempt}/{_LOAD_ATTEMPTS})")
                if attempt == _LOAD_ATTEMPTS:
                    self._load_error = str(e)
                    self.tray.notify("Impossibile caricare il modello di trascrizione. Apri il log per i dettagli.")
                    return
                time.sleep(_LOAD_RETRY_DELAY)
        self._load_error = None
        logger.info(f"Motore STT caricato: modello {self.stt_engine.model_size} su {self.stt_engine.device}")

        if not self.hotkey_listener.start():
            logger.error("Impossibile avviare: hotkey non registrabile (probabilmente già in uso)")
            self._load_error = f"scorciatoia '{self.config.hotkey}' non disponibile"
            self.tray.notify(
                f"La scorciatoia '{self.config.hotkey}' è già usata da un altro programma. "
                "Cambiala dalla finestra di Dettato."
            )
        self.state = State.IDLE
        self.tray.set_state("idle")
        logger.info(f"Dettato avviato. Premi '{self.config.hotkey}' per iniziare a dettare.")
        if self._load_error is None:
            self.tray.notify(f"Pronto. Premi {self.config.hotkey} per dettare, di nuovo per finire.")

    def status_text(self) -> str:
        if self.state == State.LOADING:
            if self._load_error:
                return f"Errore: {self._load_error}"
            return self._download_text or "Caricamento del modello in corso…"
        device = _DEVICE_LABELS.get(self.stt_engine.device, self.stt_engine.device)
        if self.state == State.RECORDING:
            return f"Sto registrando… premi {self.config.hotkey} per finire."
        if self.state == State.TRANSCRIBING:
            return "Sto trascrivendo…"
        if self._load_error:
            return f"Attenzione: {self._load_error}"
        return f"Pronto · premi {self.config.hotkey} per dettare · modello {self.stt_engine.model_size} su {device}"

    # ----- dictation -------------------------------------------------------

    def _on_hotkey_toggle(self):
        if self.state == State.IDLE:
            self._start_recording()
        elif self.state == State.RECORDING:
            self._stop_recording_and_transcribe()

    def _toggle_from_menu(self):
        # Off the tray's thread: recording start waits on the beep and
        # transcription can take seconds.
        threading.Thread(target=self._on_hotkey_toggle, daemon=True).start()

    def _start_recording(self):
        self.state = State.RECORDING
        self.tray.set_state("recording")
        # Played before opening the mic, and waited on, so the beep itself
        # doesn't get captured as the first sound of the recording.
        sound.play(BEEP_PATH, wait=True)
        try:
            self.recorder.start()
        except Exception:
            logger.exception("Impossibile avviare la registrazione (microfono non trovato?)")
            self.tray.notify("Impossibile usare il microfono. Controlla che sia collegato.")
            self.state = State.IDLE
            self.tray.set_state("idle")

    def _stop_recording_and_transcribe(self):
        self.state = State.TRANSCRIBING
        self.tray.set_state("transcribing")

        try:
            try:
                audio = self.recorder.stop()
            except NoAudioCapturedError:
                logger.info("Nessun audio catturato, torno idle")
                return

            sound.play(BEEP_PATH)

            raw_text = self.stt_engine.transcribe(audio, vocabulary=self.config.vocabulary)
            clean_text = clean_transcript(raw_text, self.config.filler_words, self.config.replacements)

            if clean_text:
                self.output_handler.paste(clean_text, auto_paste=self.config.auto_paste)
        except Exception:
            logger.exception("Errore durante la trascrizione")
            self.tray.notify("Errore durante la trascrizione. Apri il log per i dettagli.")
        finally:
            self.state = State.IDLE
            self.tray.set_state("idle")

    # ----- settings --------------------------------------------------------

    def show_window(self):
        self.window.show()

    def open_log(self):
        log = paths.log_file_path()
        try:
            os.startfile(log if log.exists() else log.parent)
        except OSError:
            logger.exception("Impossibile aprire il log")

    def capture_hotkey(self) -> str:
        """Record the next key combination the user presses.

        The current hotkey is suspended meanwhile, otherwise pressing it
        again as part of the new combination would start a dictation.
        """
        listening = self.hotkey_listener.is_active
        self.hotkey_listener.stop()
        try:
            return keyboard.read_hotkey(suppress=False)
        finally:
            if listening:
                self.hotkey_listener.start()

    def apply_settings(self, new: Config, needs_restart: bool) -> bool:
        """Apply what can change live, persist everything. Returns False
        (and changes nothing) if the new hotkey can't be registered."""
        if new.hotkey != self.config.hotkey:
            candidate = HotkeyListener(new.hotkey, self._on_hotkey_toggle)
            self.hotkey_listener.stop()
            if not candidate.start():
                if self.state != State.LOADING:
                    self.hotkey_listener.start()
                return False
            if self.state == State.LOADING:
                # Not ready yet: _load() will start it.
                candidate.stop()
            self.hotkey_listener = candidate
            if self._load_error and "scorciatoia" in self._load_error:
                self._load_error = None
            self.tray.hotkey = new.hotkey

        if new.run_on_startup != startup.is_startup_enabled():
            self._on_toggle_startup(new.run_on_startup)
            self.tray.set_startup_enabled(new.run_on_startup)

        self.config = new
        save_config(self.config)
        self.tray.refresh()
        return True

    def _on_toggle_startup(self, enabled: bool):
        if enabled:
            startup.enable_startup()
        else:
            startup.disable_startup()
        self.config.run_on_startup = enabled
        save_config(self.config)

    # ----- updates ---------------------------------------------------------

    def _update_loop(self) -> None:
        time.sleep(_FIRST_UPDATE_CHECK_DELAY)
        while True:
            if self.config.check_updates:
                self.check_for_updates()
            time.sleep(_UPDATE_CHECK_INTERVAL)

    def check_for_updates(self, manual: bool = False) -> None:
        if updater.runtime_id() == "dev":
            if manual:
                self.tray.notify("Aggiornamenti disponibili solo nella versione installata.")
            return
        try:
            release = updater.check(__version__)
        except Exception as e:
            logger.warning(f"Controllo aggiornamenti non riuscito: {e}")
            if manual:
                self.tray.notify("Impossibile controllare gli aggiornamenti. Sei connesso a Internet?")
            return
        if release is None:
            logger.info(f"Nessun aggiornamento: {__version__} è l'ultima versione")
            if manual:
                self.tray.notify(f"Hai già l'ultima versione ({__version__}).")
            return
        self.update = release
        self.tray.refresh()
        if manual or self._notified_version != release.version:
            self._notified_version = release.version
            self.tray.notify(f"È disponibile Dettato {release.version}. Aprilo dal menu dell'icona per aggiornare.")

    def start_update(self) -> None:
        if self.update is None or self._updating:
            return
        self._updating = True
        threading.Thread(target=self._run_update, args=(self.update,), daemon=True).start()

    def _run_update(self, release) -> None:
        rid = updater.runtime_id()
        light = release.is_light_for(rid)
        asset = release.update if light else release.setup

        def progress(done, total):
            self.update_status = f"Scarico l'aggiornamento: {done * 100 // max(total, 1)}% ({_gb(total)} GB)"

        try:
            path = updater.download(asset, Path(tempfile.gettempdir()) / "Dettato-update", progress)
            if light:
                self.update_status = "Installo l'aggiornamento…"
                updater.install_light(path, Path(sys.executable).parent)
                logger.info(f"Aggiornato a {release.version} (solo Dettato.exe), riavvio")
                self.restart()
            else:
                self.update_status = "Avvio l'installazione…"
                logger.info(f"Aggiornamento completo a {release.version}: avvio l'installer")
                updater.launch_full(path)
        except Exception as e:
            logger.exception("Aggiornamento non riuscito")
            self.update_status = f"Aggiornamento non riuscito: {e}"
            self.tray.notify("Aggiornamento non riuscito. Riprova più tardi.")
            self._updating = False

    # ----- shutdown --------------------------------------------------------

    def _on_exit(self):
        self.hotkey_listener.stop()
        self.window.close()

    def request_exit(self) -> None:
        """Shut down cleanly when asked from outside (e.g. `--stop`)."""
        self._on_exit()
        self.tray.stop()

    def restart(self) -> None:
        subprocess.Popen(paths.launch_command() + ["--restart"], close_fds=True)
        self.request_exit()

    def run(self):
        threading.Thread(target=self._update_loop, daemon=True, name="updates").start()
        self.tray.run(setup=self._load)
