import numpy as np
import sounddevice as sd

SAMPLE_RATE = 16000


class NoAudioCapturedError(Exception):
    pass


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
        # WASAPI shared mode otherwise rejects any samplerate but the
        # device's native one (e.g. 48000Hz instead of the 16000Hz
        # Whisper needs); auto_convert lets WASAPI resample for us.
        extra_settings = sd.WasapiSettings(auto_convert=True) if device is not None else None
        self._stream = sd.InputStream(
            device=device,
            samplerate=self.sample_rate,
            channels=1,
            dtype="float32",
            callback=self._callback,
            extra_settings=extra_settings,
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
