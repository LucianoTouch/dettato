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
        # Deliberately no explicit device/WASAPI here: this is called from
        # the `keyboard` hotkey callback thread, and forcing the WASAPI
        # host API's default device fails on that thread on this machine
        # (PaErrorCode -9999 / WdmSyncIoctl) even though it works fine
        # from a plain script's main thread — reproduced directly by
        # opening the same stream from a background thread. Leaving the
        # device unset lets PortAudio pick a host API (MME here) that
        # opens fine regardless of calling thread.
        stream = sd.InputStream(
            samplerate=self.sample_rate,
            channels=1,
            dtype="float32",
            callback=self._callback,
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
