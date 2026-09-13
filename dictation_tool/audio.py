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
