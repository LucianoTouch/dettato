import ctypes
import threading

import numpy as np
import sounddevice as sd

SAMPLE_RATE = 16000

_COINIT_APARTMENTTHREADED = 0x2
_com_state = threading.local()


def _ensure_com_initialized() -> None:
    """Initialize COM on the calling thread before opening a WASAPI stream.

    Opening a WASAPI stream from a thread that never called CoInitialize
    fails with "Unanticipated host error [PaErrorCode -9999]: WdmSyncIoctl"
    (CO_E_NOTINITIALIZED under the hood) — this is what broke the previous
    attempt when called from the `keyboard` hotkey callback thread. Each
    thread needs its own call, so this is done lazily per-thread rather than
    once at startup on the main thread.
    """
    if getattr(_com_state, "initialized", False):
        return
    try:
        ctypes.windll.ole32.CoInitializeEx(None, _COINIT_APARTMENTTHREADED)
    except Exception:
        pass
    _com_state.initialized = True


def _default_input_device():
    """Resolve the actual Windows-default input device via WASAPI.

    sounddevice's own default (sd.default.device) resolves through
    whichever host API comes first — on this machine that's the legacy
    MME API, whose "default" can diverge from the device configured as
    default in Windows Sound Settings and whose 31-char name truncation
    and resampling are lower quality. WASAPI's default_input_device
    tracks the real system setting.
    """
    try:
        for hostapi in sd.query_hostapis():
            if "wasapi" in hostapi["name"].lower():
                device = hostapi["default_input_device"]
                if device >= 0:
                    return device
    except Exception:
        pass
    return None


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
        device = _default_input_device()
        extra_settings = None
        if device is not None:
            _ensure_com_initialized()
            # WASAPI shared mode otherwise rejects any samplerate but the
            # device's native one (e.g. 48000Hz instead of the 16000Hz
            # Whisper needs); auto_convert lets WASAPI resample for us.
            extra_settings = sd.WasapiSettings(auto_convert=True)
        stream = sd.InputStream(
            device=device,
            samplerate=self.sample_rate,
            channels=1,
            dtype="float32",
            callback=self._callback,
            extra_settings=extra_settings,
        )
        try:
            stream.start()
        except Exception:
            # Otherwise the half-opened stream leaks its device handle,
            # leaving the mic stuck "busy" for every later attempt in
            # this process even though the device itself is free.
            stream.close()
            raise
        self._stream = stream

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
