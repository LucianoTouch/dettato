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
