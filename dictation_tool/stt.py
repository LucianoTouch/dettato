import os

import numpy as np


def _register_cuda_dll_dirs() -> None:
    """Make pip-installed CUDA runtime DLLs (cuBLAS, cuDNN) discoverable.

    ctranslate2 loads these via a plain LoadLibraryW at inference time,
    which only searches the classic Windows DLL search order (app dir,
    system dir, PATH) — it does not honor os.add_dll_directory(). A plain
    `pip install` of nvidia-cublas-cu12/nvidia-cudnn-cu12 does not add
    their bin/ folders to PATH on its own, so we prepend them here.
    """
    try:
        import nvidia.cublas
        import nvidia.cudnn
    except ImportError:
        return
    bin_dirs = []
    for pkg in (nvidia.cublas, nvidia.cudnn):
        for path in pkg.__path__:
            bin_dir = os.path.join(path, "bin")
            if os.path.isdir(bin_dir):
                bin_dirs.append(bin_dir)
                os.add_dll_directory(bin_dir)
    if bin_dirs:
        os.environ["PATH"] = os.pathsep.join(bin_dirs) + os.pathsep + os.environ.get("PATH", "")


_register_cuda_dll_dirs()

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


def normalize_audio(audio: np.ndarray, target_peak: float = 0.9) -> np.ndarray:
    """Scale audio so its peak amplitude reaches target_peak.

    A quiet microphone input degrades both VAD speech detection and
    transcription accuracy/completeness (confirmed: the same clip
    transcribed more completely once boosted to a normal level). Leaves
    near-silent buffers untouched to avoid amplifying noise into nothing.
    """
    peak = float(np.abs(audio).max()) if audio.size else 0.0
    if peak < 1e-4:
        return audio.astype(np.float32)
    gain = target_peak / peak
    return np.clip(audio * gain, -1.0, 1.0).astype(np.float32)


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
        audio = normalize_audio(audio)
        segments, _ = self.model.transcribe(audio, language="it", vad_filter=True)
        return "".join(segment.text for segment in segments).strip()
