# Dictation Tool Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Windows background app that transcribes Italian speech to text via a global hotkey (`Ctrl+Space` toggle), using a local Whisper large-v3 model on GPU, and auto-pastes the cleaned transcript into the active field.

**Architecture:** A tray-resident Python app wires together six independently-testable modules (config, audio capture, STT engine, post-processor, output/paste handler, hotkey listener, tray icon) through a small state machine (`App` class in `dictation_tool/app.py`) with three states: IDLE → RECORDING → TRANSCRIBING → IDLE.

**Tech Stack:** Python 3.11+, `faster-whisper` (CTranslate2, CUDA), `sounddevice`, `pyperclip`, `keyboard`, `pystray` + `Pillow`, `pytest`.

**Spec:** `docs/superpowers/specs/2026-09-13-italian-dictation-tool-design.md`

## Global Constraints

- Language is always Italian: STT calls always pass `language="it"` — no language auto-detection, no multi-language support (spec: Non-goal).
- No cloud/LLM calls anywhere in the pipeline — post-processing is rule-based only (spec: Non-goal, Post-processor).
- No real-time/streaming transcription — audio is only transcribed after the hotkey stops recording (spec: Non-goal).
- Target platform is Windows only; target GPU is an NVIDIA card with CUDA (developed against RTX 3060 12GB) with automatic CPU fallback when CUDA is unavailable (spec: STT engine).
- No standalone installer/`.exe` packaging in this plan — the app runs from a local Python environment (spec: Non-goal).
- Config file lives at `%APPDATA%\dictation-tool\config.json` with defaults: `hotkey="ctrl+space"`, `model_size="large-v3"`, `device="auto"`, `auto_paste=true`, `run_on_startup=false` (spec: Config).

---

## Task 1: Project scaffolding and config module

**Files:**
- Create: `requirements.txt`
- Create: `dictation_tool/__init__.py`
- Create: `dictation_tool/config.py`
- Test: `tests/test_config.py`

**Interfaces:**
- Produces: `Config` dataclass (`hotkey: str`, `model_size: str`, `device: str`, `filler_words: list[str]`, `auto_paste: bool`, `run_on_startup: bool`), `default_config_path() -> Path`, `load_config(path: Path | None = None) -> Config`, `save_config(config: Config, path: Path | None = None) -> None`, `DEFAULT_CONFIG: dict`.

- [ ] **Step 1: Create the project skeleton**

```bash
mkdir dictation_tool tests scripts
```

Create `requirements.txt`:

```
faster-whisper
ctranslate2
sounddevice
numpy
soundfile
pyperclip
keyboard
pystray
Pillow
pytest
```

Create `dictation_tool/__init__.py` (empty file).

- [ ] **Step 2: Write the failing tests for config**

Create `tests/test_config.py`:

```python
import json
from dictation_tool.config import load_config, save_config, Config


def test_load_config_creates_default_when_missing(tmp_path):
    config_path = tmp_path / "config.json"
    config = load_config(config_path)
    assert config.hotkey == "ctrl+space"
    assert config.model_size == "large-v3"
    assert config.device == "auto"
    assert config.auto_paste is True
    assert config.run_on_startup is False
    assert config_path.exists()


def test_load_config_merges_partial_file(tmp_path):
    config_path = tmp_path / "config.json"
    config_path.write_text(json.dumps({"hotkey": "ctrl+alt+space"}), encoding="utf-8")
    config = load_config(config_path)
    assert config.hotkey == "ctrl+alt+space"
    assert config.model_size == "large-v3"


def test_save_config_roundtrip(tmp_path):
    config_path = tmp_path / "config.json"
    original = Config(hotkey="ctrl+shift+space", auto_paste=False)
    save_config(original, config_path)
    loaded = load_config(config_path)
    assert loaded.hotkey == "ctrl+shift+space"
    assert loaded.auto_paste is False
```

- [ ] **Step 3: Run tests to verify they fail**

Run: `pytest tests/test_config.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'dictation_tool.config'`

- [ ] **Step 4: Implement the config module**

Create `dictation_tool/config.py`:

```python
import json
import os
from dataclasses import dataclass, asdict, field
from pathlib import Path
from typing import List, Optional

DEFAULT_FILLER_WORDS = ["ehm", "uhm", "cioè cioè", "insomma insomma"]

DEFAULT_CONFIG = {
    "hotkey": "ctrl+space",
    "model_size": "large-v3",
    "device": "auto",
    "filler_words": DEFAULT_FILLER_WORDS,
    "auto_paste": True,
    "run_on_startup": False,
}


@dataclass
class Config:
    hotkey: str = "ctrl+space"
    model_size: str = "large-v3"
    device: str = "auto"
    filler_words: List[str] = field(default_factory=lambda: list(DEFAULT_FILLER_WORDS))
    auto_paste: bool = True
    run_on_startup: bool = False


def default_config_path() -> Path:
    appdata = os.environ.get("APPDATA", str(Path.home()))
    return Path(appdata) / "dictation-tool" / "config.json"


def load_config(path: Optional[Path] = None) -> Config:
    path = path or default_config_path()
    if not path.exists():
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(DEFAULT_CONFIG, indent=2, ensure_ascii=False), encoding="utf-8")
        return Config()

    data = json.loads(path.read_text(encoding="utf-8"))
    merged = {**DEFAULT_CONFIG, **data}
    return Config(**merged)


def save_config(config: Config, path: Optional[Path] = None) -> None:
    path = path or default_config_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(asdict(config), indent=2, ensure_ascii=False), encoding="utf-8")
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `pytest tests/test_config.py -v`
Expected: PASS (3 tests)

- [ ] **Step 6: Install dependencies and commit**

```bash
pip install -r requirements.txt
git add requirements.txt dictation_tool/__init__.py dictation_tool/config.py tests/test_config.py
git commit -m "feat: add project scaffolding and config module"
```

---

## Task 2: Post-processing module

**Files:**
- Create: `dictation_tool/postprocess.py`
- Test: `tests/test_postprocess.py`

**Interfaces:**
- Consumes: nothing (pure function, no dependency on Task 1)
- Produces: `clean_transcript(text: str, filler_words: list[str]) -> str`

- [ ] **Step 1: Write the failing tests**

Create `tests/test_postprocess.py`:

```python
from dictation_tool.postprocess import clean_transcript


def test_removes_simple_filler_word():
    result = clean_transcript("Allora ehm andiamo avanti", ["ehm"])
    assert result == "Allora andiamo avanti"


def test_removes_multiple_filler_occurrences():
    result = clean_transcript("ehm quindi ehm il punto è questo", ["ehm"])
    assert result == "quindi il punto è questo"


def test_case_insensitive_removal():
    result = clean_transcript("Ehm certo", ["ehm"])
    assert result == "certo"


def test_removes_repeated_phrase_filler():
    result = clean_transcript("Cioè cioè il punto è che funziona", ["cioè cioè"])
    assert result == "il punto è che funziona"


def test_normalizes_multiple_spaces():
    result = clean_transcript("ciao    come   va", [])
    assert result == "ciao come va"


def test_empty_string_returns_empty():
    assert clean_transcript("", ["ehm"]) == ""


def test_fixes_space_before_punctuation():
    result = clean_transcript("ciao , come va ?", [])
    assert result == "ciao, come va?"
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_postprocess.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'dictation_tool.postprocess'`

- [ ] **Step 3: Implement post-processing**

Create `dictation_tool/postprocess.py`:

```python
import re
from typing import List


def clean_transcript(text: str, filler_words: List[str]) -> str:
    if not text:
        return ""

    cleaned = text
    for filler in filler_words:
        pattern = re.compile(r'(?<!\w)' + re.escape(filler) + r'(?!\w)', re.IGNORECASE)
        cleaned = pattern.sub("", cleaned)

    cleaned = re.sub(r'\s+', ' ', cleaned).strip()
    cleaned = re.sub(r'\s+([,.!?])', r'\1', cleaned)
    return cleaned
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/test_postprocess.py -v`
Expected: PASS (7 tests)

- [ ] **Step 5: Commit**

```bash
git add dictation_tool/postprocess.py tests/test_postprocess.py
git commit -m "feat: add rule-based filler-word post-processing"
```

---

## Task 3: STT engine wrapper

**Files:**
- Create: `dictation_tool/stt.py`
- Create: `scripts/smoke_test_stt.py`

**Interfaces:**
- Consumes: nothing new
- Produces: `SttEngine` class with `__init__(self, model_size: str = "large-v3", device: str = "auto")`, `self.device: str` (resolved value, `"cuda"` or `"cpu"`), method `transcribe(self, audio: np.ndarray, sample_rate: int = 16000) -> str`. Also `resolve_device(requested: str) -> str` and `compute_type_for_device(device: str) -> str`.

This module wraps a real GPU-backed model and downloads ~3GB on first use, so it is validated with a manual smoke-test script rather than unit tests (per spec's Testing section).

- [ ] **Step 1: Implement the STT engine**

Create `dictation_tool/stt.py`:

```python
import ctranslate2
from faster_whisper import WhisperModel


def cuda_available() -> bool:
    try:
        return ctranslate2.get_cuda_device_count() > 0
    except Exception:
        return False


def resolve_device(requested: str) -> str:
    if requested == "auto":
        return "cuda" if cuda_available() else "cpu"
    return requested


def compute_type_for_device(device: str) -> str:
    return "float16" if device == "cuda" else "int8"


class SttEngine:
    def __init__(self, model_size: str = "large-v3", device: str = "auto"):
        resolved_device = resolve_device(device)
        compute_type = compute_type_for_device(resolved_device)
        try:
            self.model = WhisperModel(model_size, device=resolved_device, compute_type=compute_type)
            self.device = resolved_device
        except Exception:
            self.model = WhisperModel(model_size, device="cpu", compute_type="int8")
            self.device = "cpu"

    def transcribe(self, audio, sample_rate: int = 16000) -> str:
        segments, _ = self.model.transcribe(audio, language="it", vad_filter=True)
        return "".join(segment.text for segment in segments).strip()
```

- [ ] **Step 2: Write the manual smoke-test script**

Create `scripts/smoke_test_stt.py`:

```python
import sys
import soundfile as sf
from dictation_tool.stt import SttEngine


def main():
    if len(sys.argv) != 2:
        print("Uso: python scripts/smoke_test_stt.py <path_audio.wav>")
        sys.exit(1)

    audio_path = sys.argv[1]
    audio, sample_rate = sf.read(audio_path, dtype="float32")
    if audio.ndim > 1:
        audio = audio.mean(axis=1)

    print("Carico il modello (device=auto)...")
    engine = SttEngine(model_size="large-v3", device="auto")
    print(f"Device effettivo: {engine.device}")

    print("Trascrivo...")
    text = engine.transcribe(audio, sample_rate=sample_rate)
    print(f"Trascrizione: {text}")


if __name__ == "__main__":
    main()
```

- [ ] **Step 3: Record a sample and run the smoke test**

Registra un clip di ~10 secondi di parlato italiano (es. con l'app Registratore vocale di Windows, esporta come `.wav`), poi esegui:

Run: `python scripts/smoke_test_stt.py path/to/sample.wav`
Expected: stampa `Device effettivo: cuda` (sulla RTX 3060) e una trascrizione italiana leggibile del contenuto del clip. Il primo avvio scarica il modello (~3GB) da Hugging Face Hub — richiede internet solo questa volta.

- [ ] **Step 4: Commit**

```bash
git add dictation_tool/stt.py scripts/smoke_test_stt.py
git commit -m "feat: add faster-whisper STT engine with CUDA/CPU fallback"
```

---

## Task 4: Audio recorder

**Files:**
- Create: `dictation_tool/audio.py`
- Create: `scripts/manual_test_audio.py`

**Interfaces:**
- Consumes: nothing new
- Produces: `AudioRecorder` class with `SAMPLE_RATE = 16000` module constant, `__init__(self, sample_rate: int = 16000)`, `self.sample_rate: int`, `start(self) -> None`, `stop(self) -> np.ndarray` (raises `NoAudioCapturedError` if nothing was captured). `NoAudioCapturedError` exception class.

- [ ] **Step 1: Implement the audio recorder**

Create `dictation_tool/audio.py`:

```python
import numpy as np
import sounddevice as sd

SAMPLE_RATE = 16000


class NoAudioCapturedError(Exception):
    pass


class AudioRecorder:
    def __init__(self, sample_rate: int = SAMPLE_RATE):
        self.sample_rate = sample_rate
        self._frames = []
        self._stream = None

    def _callback(self, indata, frames, time_info, status):
        self._frames.append(indata.copy())

    def start(self) -> None:
        self._frames = []
        self._stream = sd.InputStream(
            samplerate=self.sample_rate,
            channels=1,
            dtype="float32",
            callback=self._callback,
        )
        self._stream.start()

    def stop(self) -> np.ndarray:
        if self._stream is None:
            raise NoAudioCapturedError("Registrazione non avviata")
        self._stream.stop()
        self._stream.close()
        self._stream = None
        if not self._frames:
            raise NoAudioCapturedError("Nessun audio catturato")
        audio = np.concatenate(self._frames, axis=0).flatten()
        return audio
```

- [ ] **Step 2: Write the manual test script**

Create `scripts/manual_test_audio.py`:

```python
import time
import soundfile as sf
from dictation_tool.audio import AudioRecorder


def main():
    recorder = AudioRecorder()
    print("Registrazione per 3 secondi... parla ora.")
    recorder.start()
    time.sleep(3)
    audio = recorder.stop()
    sf.write("test_recording.wav", audio, recorder.sample_rate)
    print(f"Salvato test_recording.wav, {len(audio)} campioni.")
    print("Riproduci il file per verificare che l'audio sia comprensibile.")


if __name__ == "__main__":
    main()
```

- [ ] **Step 3: Run the manual test**

Run: `python scripts/manual_test_audio.py`
Expected: viene creato `test_recording.wav`; riproducendolo si sente chiaramente ciò che hai detto nei 3 secondi, senza distorsioni o silenzio totale.

- [ ] **Step 4: Commit**

```bash
git add dictation_tool/audio.py scripts/manual_test_audio.py
git commit -m "feat: add audio recorder using sounddevice"
```

---

## Task 5: Output handler (clipboard + auto-paste)

**Files:**
- Create: `dictation_tool/output.py`
- Create: `scripts/manual_test_output.py`

**Interfaces:**
- Consumes: nothing new
- Produces: `OutputHandler` class with `__init__(self, paste_delay: float = 0.5)`, method `paste(self, text: str, auto_paste: bool = True) -> None`.

- [ ] **Step 1: Implement the output handler**

Create `dictation_tool/output.py`:

```python
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

        original_clipboard = None
        try:
            original_clipboard = pyperclip.paste()
        except Exception as e:
            logger.warning(f"Impossibile leggere la clipboard corrente: {e}")

        pyperclip.copy(text)

        if auto_paste:
            keyboard.send("ctrl+v")
            time.sleep(self.paste_delay)

        if original_clipboard is not None:
            try:
                pyperclip.copy(original_clipboard)
            except Exception as e:
                logger.warning(f"Impossibile ripristinare la clipboard originale: {e}")
```

- [ ] **Step 2: Write the manual test script**

Create `scripts/manual_test_output.py`:

```python
import time
import pyperclip
from dictation_tool.output import OutputHandler


def main():
    pyperclip.copy("contenuto clipboard originale di test")
    print("Clipboard impostata su testo di prova.")
    print("Apri il Blocco Note e clicca nel campo di testo. Hai 3 secondi.")
    time.sleep(3)

    handler = OutputHandler()
    handler.paste("Questo è un testo di prova dettato.", auto_paste=True)

    time.sleep(1)
    restored = pyperclip.paste()
    print(f"Clipboard dopo il ripristino: {restored!r}")
    assert restored == "contenuto clipboard originale di test", "Il ripristino della clipboard è fallito"
    print("OK: clipboard ripristinata correttamente.")


if __name__ == "__main__":
    main()
```

- [ ] **Step 3: Run the manual test**

Run: `python scripts/manual_test_output.py` (con il Blocco Note in focus quando richiesto)
Expected: il testo "Questo è un testo di prova dettato." appare nel Blocco Note; lo script stampa `OK: clipboard ripristinata correttamente.` senza `AssertionError`.

- [ ] **Step 4: Commit**

```bash
git add dictation_tool/output.py scripts/manual_test_output.py
git commit -m "feat: add clipboard paste handler with save/restore"
```

---

## Task 6: Hotkey listener

**Files:**
- Create: `dictation_tool/hotkey.py`
- Create: `scripts/manual_test_hotkey.py`

**Interfaces:**
- Consumes: nothing new
- Produces: `HotkeyListener` class with `__init__(self, hotkey: str, on_toggle: Callable[[], None])`, `start(self) -> bool` (returns `False` and logs on registration failure, e.g. hotkey already in use), `stop(self) -> None`.

- [ ] **Step 1: Implement the hotkey listener**

Create `dictation_tool/hotkey.py`:

```python
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
            keyboard.remove_hotkey(self._handle)
            self._handle = None
```

- [ ] **Step 2: Write the manual test script**

Create `scripts/manual_test_hotkey.py`:

```python
import time
from dictation_tool.hotkey import HotkeyListener


def main():
    count = {"n": 0}

    def on_toggle():
        count["n"] += 1
        print(f"Hotkey premuta! (volta numero {count['n']})")

    listener = HotkeyListener("ctrl+space", on_toggle)
    ok = listener.start()
    if not ok:
        print("Registrazione hotkey fallita.")
        return

    print("Premi Ctrl+Space alcune volte in qualsiasi finestra. Il test termina dopo 15 secondi.")
    time.sleep(15)
    listener.stop()
    print(f"Totale attivazioni: {count['n']}")


if __name__ == "__main__":
    main()
```

- [ ] **Step 3: Run the manual test**

Run: `python scripts/manual_test_hotkey.py`, poi premi `Ctrl+Space` 2-3 volte mentre un'altra finestra (es. browser) è in focus.
Expected: ogni pressione stampa `Hotkey premuta!` nel terminale anche se il terminale non ha il focus; il conteggio finale corrisponde al numero di pressioni.

- [ ] **Step 4: Commit**

```bash
git add dictation_tool/hotkey.py scripts/manual_test_hotkey.py
git commit -m "feat: add global hotkey listener"
```

---

## Task 7: Tray icon

**Files:**
- Create: `dictation_tool/tray.py`
- Create: `scripts/manual_test_tray.py`

**Interfaces:**
- Consumes: nothing new
- Produces: `TrayIcon` class with `__init__(self, on_exit: Callable[[], None], on_toggle_startup: Callable[[bool], None], startup_enabled: bool)`, `set_state(self, state: Literal["idle", "recording", "transcribing"]) -> None`, `run(self) -> None` (blocking), `run_detached(self) -> None` (runs `run` in a daemon thread).

- [ ] **Step 1: Implement the tray icon**

Create `dictation_tool/tray.py`:

```python
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
```

- [ ] **Step 2: Write the manual test script**

Create `scripts/manual_test_tray.py`:

```python
import time
from dictation_tool.tray import TrayIcon


def main():
    tray = TrayIcon(
        on_exit=lambda: print("Uscita richiesta"),
        on_toggle_startup=lambda v: print(f"Startup: {v}"),
        startup_enabled=False,
    )
    tray.run_detached()

    for state in ["idle", "recording", "transcribing", "idle"]:
        print(f"Imposto stato: {state}")
        tray.set_state(state)
        time.sleep(3)

    print("Controlla visivamente l'icona nella tray (grigia/rossa/gialla/grigia).")
    print("Prova anche il menu con click destro (Avvio automatico, Esci).")
    time.sleep(20)


if __name__ == "__main__":
    main()
```

- [ ] **Step 3: Run the manual test**

Run: `python scripts/manual_test_tray.py`
Expected: appare un'icona nella system tray che cambia colore ogni 3 secondi (grigio → rosso → giallo → grigio); il click destro mostra il menu con "Avvio automatico con Windows" e "Esci" funzionanti.

- [ ] **Step 4: Commit**

```bash
git add dictation_tool/tray.py scripts/manual_test_tray.py
git commit -m "feat: add system tray icon with state colors and menu"
```

---

## Task 8: Windows startup toggle

**Files:**
- Create: `dictation_tool/startup.py`
- Test: `tests/test_startup.py`

**Interfaces:**
- Consumes: nothing new
- Produces: `enable_startup() -> None`, `disable_startup() -> None`, `is_startup_enabled() -> bool`.

`winreg` is mocked in tests since it talks to the real Windows registry.

- [ ] **Step 1: Write the failing tests**

Create `tests/test_startup.py`:

```python
from unittest.mock import patch, MagicMock
from dictation_tool import startup


def test_is_startup_enabled_false_when_key_missing():
    with patch("dictation_tool.startup.winreg") as mock_winreg:
        mock_winreg.OpenKey.side_effect = FileNotFoundError()
        assert startup.is_startup_enabled() is False


def test_is_startup_enabled_true_when_value_present():
    with patch("dictation_tool.startup.winreg") as mock_winreg:
        mock_key = MagicMock()
        mock_winreg.OpenKey.return_value.__enter__.return_value = mock_key
        mock_winreg.QueryValueEx.return_value = ("some command", 1)
        assert startup.is_startup_enabled() is True


def test_enable_startup_sets_registry_value():
    with patch("dictation_tool.startup.winreg") as mock_winreg:
        mock_key = MagicMock()
        mock_winreg.OpenKey.return_value.__enter__.return_value = mock_key
        startup.enable_startup()
        mock_winreg.SetValueEx.assert_called_once()
        args = mock_winreg.SetValueEx.call_args[0]
        assert args[1] == "DictationTool"


def test_disable_startup_deletes_value_without_error_when_missing():
    with patch("dictation_tool.startup.winreg") as mock_winreg:
        mock_key = MagicMock()
        mock_winreg.OpenKey.return_value.__enter__.return_value = mock_key
        mock_winreg.DeleteValue.side_effect = FileNotFoundError()
        startup.disable_startup()
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_startup.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'dictation_tool.startup'`

- [ ] **Step 3: Implement the startup module**

Create `dictation_tool/startup.py`:

```python
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
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/test_startup.py -v`
Expected: PASS (4 tests)

- [ ] **Step 5: Commit**

```bash
git add dictation_tool/startup.py tests/test_startup.py
git commit -m "feat: add Windows startup registry toggle"
```

---

## Task 9: App orchestrator and entry point

**Files:**
- Create: `dictation_tool/app.py`
- Create: `main.py`

**Interfaces:**
- Consumes: `Config`/`load_config` (Task 1), `clean_transcript` (Task 2), `SttEngine` (Task 3), `AudioRecorder`/`NoAudioCapturedError` (Task 4), `OutputHandler` (Task 5), `HotkeyListener` (Task 6), `TrayIcon` (Task 7), `startup.enable_startup`/`disable_startup`/`is_startup_enabled` (Task 8)
- Produces: `App` class with `__init__(self, config: Config)`, `run(self) -> None` (blocking).

- [ ] **Step 1: Implement the app orchestrator**

Create `dictation_tool/app.py`:

```python
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
```

- [ ] **Step 2: Create the entry point**

Create `main.py`:

```python
import logging
from dictation_tool.config import load_config
from dictation_tool.app import App


def main():
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    config = load_config()
    app = App(config)
    app.run()


if __name__ == "__main__":
    main()
```

- [ ] **Step 3: Run the full app manually**

Run: `python main.py`
Expected: l'icona grigia appare nella tray; premendo `Ctrl+Space`, parlando in italiano, e ripremendo `Ctrl+Space`, il testo trascritto e ripulito appare incollato nel campo di testo attivo (es. Blocco Note). L'icona passa correttamente grigio → rosso (recording) → giallo (transcribing) → grigio.

- [ ] **Step 4: Commit**

```bash
git add dictation_tool/app.py main.py
git commit -m "feat: wire modules together into the app orchestrator and entry point"
```

---

## Task 10: End-to-end validation pass

**Files:** nessuno (task di verifica manuale, nessun codice nuovo)

Questo task ripercorre la sezione "Testing / validazione" dello spec su un'installazione reale, per confermare che la pipeline regge nell'uso quotidiano.

- [ ] **Step 1: Verifica su almeno 3 applicazioni target**

Con `python main.py` in esecuzione, testa il ciclo `Ctrl+Space` → parla → `Ctrl+Space` su:
1. Un campo di ricerca del browser
2. Un editor di testo (es. VS Code o Blocco Note)
3. Un client di chat (es. Telegram Desktop, Slack, o Teams)

Expected: in tutti e tre i casi il testo trascritto appare correttamente nel campo attivo, senza corrompere il contenuto già presente.

- [ ] **Step 2: Verifica il fallback CPU**

In `dictation_tool/config.py`, imposta temporaneamente `device` su `"cpu"` in `config.json` (o passa `device="cpu"` a `SttEngine` in uno script ad-hoc), riavvia l'app e ripeti una dettatura.

Expected: la trascrizione funziona comunque (più lentamente), confermando che il percorso CPU non è rotto. Ripristina poi `device` su `"auto"`.

- [ ] **Step 3: Verifica il ripristino della clipboard in condizioni reali**

Copia manualmente del testo (es. da un altro documento), poi esegui una dettatura con `Ctrl+Space`.

Expected: dopo l'incolla automatico, se incolli di nuovo manualmente (`Ctrl+V`) ottieni il testo che avevi copiato in origine, non la trascrizione.

- [ ] **Step 4: Verifica l'avvio automatico con Windows**

Dal menu tray, attiva "Avvio automatico con Windows", poi controlla in `regedit` (`HKEY_CURRENT_USER\Software\Microsoft\Windows\CurrentVersion\Run`) che la voce `DictationTool` sia presente. Disattivala e verifica che la voce sparisca.

- [ ] **Step 5: Verifica gestione hotkey in conflitto**

Avvia una seconda istanza di `python main.py` mentre la prima è già in esecuzione.

Expected: la seconda istanza logga un errore di registrazione hotkey fallita (non va in crash silenzioso) e non interferisce con la prima istanza già attiva.

- [ ] **Step 6: Commit finale (se sono stati modificati file di configurazione di default durante i test)**

```bash
git status
```

Se `config.json` di default o altri file tracciati sono stati modificati per i test, ripristinali ai valori di default prima di committare eventuali modifiche residue.
