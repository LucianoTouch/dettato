import logging
from enum import Enum, auto

from dictation_tool.config import Config
from dictation_tool.audio import AudioRecorder, NoAudioCapturedError
from dictation_tool.stt import SttEngine
from dictation_tool.postprocess import clean_transcript
from dictation_tool.output import OutputHandler
from dictation_tool.hotkey import HotkeyListener
from dictation_tool.tray import TrayIcon
from dictation_tool import startup

logger = logging.getLogger(__name__)


class State(Enum):
    IDLE = auto()
    RECORDING = auto()
    TRANSCRIBING = auto()


class App:
    def __init__(self, config: Config):
        self.config = config
        self.state = State.IDLE

        self.recorder = AudioRecorder()
        self.stt_engine = SttEngine(model_size=config.model_size, device=config.device)
        self.output_handler = OutputHandler()
        self.hotkey_listener = HotkeyListener(config.hotkey, self._on_hotkey_toggle)
        self.tray = TrayIcon(
            on_exit=self._on_exit,
            on_toggle_startup=self._on_toggle_startup,
            startup_enabled=startup.is_startup_enabled(),
        )

    def _on_hotkey_toggle(self):
        if self.state == State.IDLE:
            self._start_recording()
        elif self.state == State.RECORDING:
            self._stop_recording_and_transcribe()

    def _start_recording(self):
        self.state = State.RECORDING
        self.tray.set_state("recording")
        self.recorder.start()

    def _stop_recording_and_transcribe(self):
        self.state = State.TRANSCRIBING
        self.tray.set_state("transcribing")

        try:
            audio = self.recorder.stop()
        except NoAudioCapturedError:
            logger.info("Nessun audio catturato, torno idle")
            self.state = State.IDLE
            self.tray.set_state("idle")
            return

        raw_text = self.stt_engine.transcribe(audio)
        clean_text = clean_transcript(raw_text, self.config.filler_words)

        if clean_text:
            self.output_handler.paste(clean_text, auto_paste=self.config.auto_paste)

        self.state = State.IDLE
        self.tray.set_state("idle")

    def _on_toggle_startup(self, enabled: bool):
        if enabled:
            startup.enable_startup()
        else:
            startup.disable_startup()
        self.config.run_on_startup = enabled

    def _on_exit(self):
        self.hotkey_listener.stop()

    def run(self):
        ok = self.hotkey_listener.start()
        if not ok:
            logger.error("Impossibile avviare: hotkey non registrabile (probabilmente già in uso)")
            return
        logger.info(f"Dictation tool avviato. Premi '{self.config.hotkey}' per iniziare a dettare.")
        self.tray.run()
