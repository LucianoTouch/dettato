import logging
import os
import re
import sys
from pathlib import Path
from typing import List, Optional

import numpy as np

logger = logging.getLogger(__name__)


def _nvidia_roots():
    # Dettato.exe: PyInstaller copies the DLLs to <bundle>/nvidia/<pkg>/bin.
    if hasattr(sys, "_MEIPASS"):
        yield Path(sys._MEIPASS) / "nvidia"
    try:
        import nvidia
    except ImportError:
        return
    for path in nvidia.__path__:
        yield Path(path)


def _register_cuda_dll_dirs() -> None:
    """Make pip-installed CUDA runtime DLLs (cuBLAS, cuDNN) discoverable.

    ctranslate2 loads these via a plain LoadLibraryW at inference time,
    which only searches the classic Windows DLL search order (app dir,
    system dir, PATH) — it does not honor os.add_dll_directory(). A plain
    `pip install` of nvidia-cublas-cu12/nvidia-cudnn-cu12 does not add
    their bin/ folders to PATH on its own, so we prepend them here.
    """
    bin_dirs = []
    for root in _nvidia_roots():
        for bin_dir in sorted(root.glob("*/bin")):
            if bin_dir.is_dir() and str(bin_dir) not in bin_dirs:
                bin_dirs.append(str(bin_dir))
                os.add_dll_directory(str(bin_dir))
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


def normalize_audio(audio: np.ndarray, target_peak: float = 0.9, reference_percentile: float = 99.9) -> np.ndarray:
    """Scale audio so a robust peak estimate reaches target_peak.

    A quiet microphone input degrades both VAD speech detection and
    transcription accuracy/completeness (confirmed: the same clip
    transcribed more completely once boosted to a normal level). Leaves
    near-silent buffers untouched to avoid amplifying noise into nothing.

    Uses a high percentile of the amplitude instead of the true sample
    max: on real hardware a single-sample transient (e.g. a mic click)
    can be several times louder than the actual speech, so gain based on
    the true max leaves genuine speech under-amplified while that one
    outlier alone reaches target_peak (confirmed on a real recording:
    peak came from one isolated sample, 60% above the 99.9th percentile
    of the rest of the clip). `method="higher"` makes this identical to
    true-max behavior for small arrays, so it doesn't change short/clean
    inputs — it only kicks in once there are enough samples for the
    percentile to actually exclude the top ones.
    """
    if audio.size == 0:
        return audio.astype(np.float32)
    reference = float(np.percentile(np.abs(audio), reference_percentile, method="higher"))
    if reference < 1e-4:
        return audio.astype(np.float32)
    gain = target_peak / reference
    return np.clip(audio * gain, -1.0, 1.0).astype(np.float32)


def trim_silence(
    audio: np.ndarray,
    sample_rate: int = 16000,
    frame_ms: int = 30,
    padding_ms: int = 300,
    min_voiced_ms: int = 200,
    absolute_floor: float = 0.001,
    noise_factor: float = 3.0,
    min_dynamic_range: float = 4.0,
) -> np.ndarray:
    """Cut leading/trailing silence; return an empty array if there's no voice.

    Whisper fed silence or room noise invents subtitle-style phrases
    ("Grazie a tutti.", "Sottotitoli a cura di..."), so audio without
    speech must never reach the model. Silero VAD was tried and dropped
    for discarding real speech; this is a deliberately lenient energy
    gate instead: a frame counts as voice when its RMS clearly exceeds
    the recording's own noise floor (low percentile of frame RMS), so it
    adapts to a quiet mic. Short transients like the hotkey's key click
    don't add up to min_voiced_ms and are ignored.
    """
    frame = int(sample_rate * frame_ms / 1000)
    if audio.size < frame:
        return audio[:0].astype(np.float32)
    n_frames = audio.size // frame
    frames = audio[: n_frames * frame].reshape(n_frames, frame).astype(np.float64)
    rms = np.sqrt(np.mean(frames ** 2, axis=1))
    noise_floor = float(np.percentile(rms, 10))
    peak = float(np.percentile(rms, 95))
    # Speech always swings between syllables and gaps; steady room noise
    # doesn't. Without that swing there's nothing to transcribe.
    if peak < absolute_floor or peak < noise_floor * min_dynamic_range:
        return audio[:0].astype(np.float32)
    # Capped relative to the peak so a recording that is speech from start
    # to end (no silence to measure the floor on) isn't cut away.
    threshold = max(absolute_floor, min(noise_floor * noise_factor, peak * 0.3))
    voiced = np.flatnonzero(rms > threshold)
    if voiced.size * frame_ms < min_voiced_ms:
        return audio[:0].astype(np.float32)
    pad = int(sample_rate * padding_ms / 1000)
    start = max(0, voiced[0] * frame - pad)
    end = min(audio.size, (voiced[-1] + 1) * frame + pad)
    return audio[start:end].astype(np.float32)


# Phrases Whisper is known to hallucinate in Italian (learned from
# subtitled training data). Nobody dictates these, so a segment that is
# exactly one of them is always dropped.
_ALWAYS_HALLUCINATED = [
    r"sottotitoli .*",
    r".*amara\.org.*",
    r"(iscriviti|iscrivetevi) al (mio )?canale.*",
    r"grazie (a tutti )?per (la visione|l'ascolto|aver guardato|averci seguito|la vostra attenzione)",
]
# Plausible as real dictation, so dropped only when Whisper itself
# doubts there was speech.
_SUSPICIOUS = [
    r"grazie( mille)?( a tutti)?",
    r"alla prossima",
    r"ciao a tutti",
    r"buona visione",
]
_SUSPICIOUS_NO_SPEECH_PROB = 0.3


def _normalize_segment_text(text: str) -> str:
    text = text.lower().strip()
    text = re.sub(r"[^\w\s'.]", " ", text)
    return re.sub(r"\s+", " ", text).strip(" .")


def is_hallucination(segment) -> bool:
    text = _normalize_segment_text(segment.text)
    if not text:
        return True
    if any(re.fullmatch(p, text) for p in _ALWAYS_HALLUCINATED):
        return True
    no_speech = getattr(segment, "no_speech_prob", 0.0)
    if no_speech > _SUSPICIOUS_NO_SPEECH_PROB and any(re.fullmatch(p, text) for p in _SUSPICIOUS):
        return True
    return False


_PROMPT_MAX_CHARS = 600


def build_prompt(vocabulary: Optional[List[str]]) -> Optional[str]:
    """Whisper's initial_prompt: makes it spell the user's names/terms right.

    Written as well-punctuated Italian so it also nudges the punctuation
    style. Capped well under Whisper's 224-token prompt window.
    """
    terms = [t.strip() for t in (vocabulary or []) if t.strip()]
    if not terms:
        return None
    prompt = "Dettatura in italiano, con punteggiatura corretta. Termini: "
    included = []
    for term in terms:
        candidate = prompt + ", ".join(included + [term]) + "."
        if len(candidate) > _PROMPT_MAX_CHARS:
            break
        included.append(term)
    if not included:
        return None
    return prompt + ", ".join(included) + "."


_AUTO_MODEL = {"cuda": "large-v3", "cpu": "medium"}


def resolve_model(model_size: str, device: str) -> str:
    """"auto" picks what runs well on the hardware: large-v3 is near
    real-time on a GPU but far too slow on a CPU, where medium is the
    best accuracy that still feels responsive."""
    if model_size == "auto":
        return _AUTO_MODEL.get(device, "medium")
    return model_size


def model_repo(model_size: str) -> Optional[str]:
    from faster_whisper.utils import _MODELS

    return _MODELS.get(model_size)


def is_model_cached(model_size: str) -> bool:
    repo = model_repo(model_size)
    if repo is None:
        return True  # a local path or unknown name: nothing for us to download
    from huggingface_hub import try_to_load_from_cache

    return isinstance(try_to_load_from_cache(repo, "model.bin"), str)


def model_download_progress(model_size: str) -> int:
    """Bytes of the model downloaded so far into the Hugging Face cache."""
    repo = model_repo(model_size)
    if repo is None:
        return 0
    from huggingface_hub import constants

    blobs = Path(constants.HF_HUB_CACHE) / f"models--{repo.replace('/', '--')}" / "blobs"
    try:
        return sum(f.stat().st_size for f in blobs.iterdir() if f.is_file())
    except OSError:
        return 0


def model_download_size(model_size: str) -> Optional[int]:
    repo = model_repo(model_size)
    if repo is None:
        return None
    try:
        from huggingface_hub import HfApi

        info = HfApi().model_info(repo, files_metadata=True)
        return sum(s.size or 0 for s in info.siblings)
    except Exception:
        return None


class SttEngine:
    def __init__(self, model_size: str = "large-v3", device: str = "auto"):
        resolved_device = resolve_device(device)
        compute_type = compute_type_for_device(resolved_device)
        try:
            self.model_size = resolve_model(model_size, resolved_device)
            self.model = WhisperModel(self.model_size, device=resolved_device, compute_type=compute_type)
            self.device = resolved_device
        except Exception:
            self.model_size = resolve_model(model_size, "cpu")
            self.model = WhisperModel(self.model_size, device="cpu", compute_type="int8")
            self.device = "cpu"

    def transcribe(self, audio, sample_rate: int = 16000, vocabulary: Optional[List[str]] = None) -> str:
        # Trim before normalizing, so the gain isn't computed on noise.
        audio = trim_silence(np.asarray(audio, dtype=np.float32), sample_rate)
        if audio.size == 0:
            logger.info("Nessun parlato rilevato, niente da trascrivere")
            return ""
        audio = normalize_audio(audio)
        segments, _ = self.model.transcribe(
            audio,
            language="it",
            task="transcribe",
            beam_size=5,
            best_of=5,
            condition_on_previous_text=False,
            initial_prompt=build_prompt(vocabulary),
            # Fallback to higher temperatures when a segment comes out as a
            # repetition loop or with very low confidence.
            temperature=[0.0, 0.2, 0.4, 0.6, 0.8, 1.0],
            compression_ratio_threshold=2.4,
            log_prob_threshold=-1.0,
            no_speech_threshold=0.6,
            # Silero VAD (even with lenient parameters) proved unreliable
            # on real recordings from this setup — confirmed discarding
            # 100% of several genuine dictation attempts as "non-speech",
            # including one 87-second recording. trim_silence() above and
            # the hallucination filters below replace it.
            vad_filter=False,
            # Needed by hallucination_silence_threshold, which skips text
            # Whisper invents inside long pauses.
            word_timestamps=True,
            hallucination_silence_threshold=2.0,
        )
        kept = []
        for segment in segments:
            if is_hallucination(segment):
                logger.info(f"Scartato segmento probabilmente inventato: {segment.text.strip()!r}")
                continue
            kept.append(segment.text)
        return "".join(kept).strip()
