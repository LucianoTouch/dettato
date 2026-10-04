import numpy as np
import pytest

import dettato.stt as stt
from dettato.stt import normalize_audio


SR = 16000


def _speech_like(seconds, level=0.1, freq=220.0):
    """A tone gated by a ~4 Hz syllable envelope: loud vowels, near-silent gaps."""
    t = np.arange(int(SR * seconds)) / SR
    envelope = np.abs(np.sin(2 * np.pi * 2 * t))
    return (level * envelope * np.sin(2 * np.pi * freq * t)).astype(np.float32)


def _noise(seconds, level=0.0005, seed=0):
    rng = np.random.default_rng(seed)
    return (rng.standard_normal(int(SR * seconds)) * level).astype(np.float32)


def _segment(text, no_speech_prob=0.01):
    return type("Segment", (), {"text": text, "no_speech_prob": no_speech_prob})()


def _engine_returning(monkeypatch, segments, captured=None):
    class FakeModel:
        calls = 0

        def transcribe(self, audio, **kwargs):
            FakeModel.calls += 1
            if captured is not None:
                captured.update(kwargs)
                captured["audio"] = audio
            return list(segments), None

    monkeypatch.setattr(stt, "WhisperModel", lambda *args, **kwargs: FakeModel())
    return stt.SttEngine(model_size="tiny", device="cpu"), FakeModel


def test_transcribe_uses_stable_settings(monkeypatch):
    captured = {}
    engine, _ = _engine_returning(monkeypatch, [_segment(" ciao mondo")], captured)

    result = engine.transcribe(np.concatenate([_noise(0.5), _speech_like(1.0), _noise(0.5)]))

    assert result == "ciao mondo"
    assert captured["language"] == "it"
    assert captured["task"] == "transcribe"
    assert captured["beam_size"] == 5
    assert captured["condition_on_previous_text"] is False
    assert captured["vad_filter"] is False
    assert captured["temperature"][0] == 0.0 and len(captured["temperature"]) > 1
    assert captured["word_timestamps"] is True
    assert captured["hallucination_silence_threshold"] == 2.0
    assert captured["initial_prompt"] is None


def test_transcribe_passes_vocabulary_as_prompt(monkeypatch):
    captured = {}
    engine, _ = _engine_returning(monkeypatch, [_segment(" ok")], captured)
    engine.transcribe(_speech_like(1.0), vocabulary=["Meta Ads", "Costruisci & Arreda"])
    assert "Meta Ads" in captured["initial_prompt"]
    assert "Costruisci & Arreda" in captured["initial_prompt"]


def test_transcribe_skips_model_on_silence(monkeypatch):
    engine, model = _engine_returning(monkeypatch, [_segment(" Grazie a tutti.")])
    assert engine.transcribe(_noise(4.0)) == ""
    assert model.calls == 0


def test_transcribe_drops_hallucinated_segments_only(monkeypatch):
    segments = [
        _segment(" Il preventivo è pronto."),
        _segment(" Sottotitoli creati dalla comunità Amara.org"),
    ]
    engine, _ = _engine_returning(monkeypatch, segments)
    assert engine.transcribe(_speech_like(1.0)) == "Il preventivo è pronto."


# ----- trim_silence


def test_trim_silence_returns_empty_for_pure_silence():
    assert stt.trim_silence(np.zeros(SR * 2, dtype=np.float32)).size == 0


def test_trim_silence_returns_empty_for_steady_room_noise():
    assert stt.trim_silence(_noise(3.0, level=0.01)).size == 0


def test_trim_silence_ignores_a_short_click():
    audio = _noise(3.0)
    audio[SR : SR + 400] = 0.5  # 25 ms key click
    assert stt.trim_silence(audio).size == 0


def test_trim_silence_keeps_speech_with_padding():
    audio = np.concatenate([_noise(2.0), _speech_like(1.0), _noise(2.0)])
    trimmed = stt.trim_silence(audio)
    # ~1 s of speech + up to 0.3 s padding each side, far less than 5 s.
    assert 1.0 * SR <= trimmed.size <= 1.7 * SR
    assert np.abs(trimmed).max() == pytest.approx(0.1, abs=2e-3)


def test_trim_silence_keeps_recording_that_is_all_speech():
    audio = _speech_like(2.0)
    assert stt.trim_silence(audio).size >= int(1.8 * SR)


def test_trim_silence_keeps_short_word_with_room_noise():
    audio = np.concatenate([_noise(1.0, level=0.003), _speech_like(0.35, level=0.05), _noise(1.0, level=0.003)])
    assert stt.trim_silence(audio).size > 0


def test_trim_silence_keeps_quiet_speech_from_a_quiet_mic():
    audio = np.concatenate([_noise(1.0, level=0.0002), _speech_like(1.0, level=0.005), _noise(1.0, level=0.0002)])
    assert stt.trim_silence(audio).size >= SR


# ----- hallucination filter


@pytest.mark.parametrize(
    "text",
    [
        " Sottotitoli creati dalla comunità Amara.org",
        " Sottotitoli a cura di QTSS",
        " Grazie per la visione!",
        " Iscriviti al canale",
        "   ",
    ],
)
def test_always_dropped_phrases(text):
    assert stt.is_hallucination(_segment(text))


def test_plausible_phrase_dropped_only_when_whisper_doubts_speech():
    assert stt.is_hallucination(_segment(" Grazie a tutti.", no_speech_prob=0.5))
    assert not stt.is_hallucination(_segment(" Grazie a tutti.", no_speech_prob=0.05))


def test_phrase_inside_real_text_is_kept():
    assert not stt.is_hallucination(_segment(" Il report è pronto, grazie a tutti.", no_speech_prob=0.9))


# ----- prompt


def test_build_prompt_none_without_vocabulary():
    assert stt.build_prompt([]) is None
    assert stt.build_prompt(None) is None
    assert stt.build_prompt(["  "]) is None


def test_build_prompt_is_capped():
    prompt = stt.build_prompt([f"Termine{i}" for i in range(500)])
    assert len(prompt) <= 600
    assert prompt.endswith(".")
    assert "Termine0" in prompt


def test_boosts_quiet_audio_to_target_peak():
    audio = np.array([0.0, 0.09, -0.05, 0.02], dtype=np.float32)
    result = normalize_audio(audio, target_peak=0.9)
    assert np.abs(result).max() == pytest.approx(0.9, abs=1e-5)


def test_preserves_waveform_shape_relative_to_peak():
    audio = np.array([0.0, 0.09, -0.045], dtype=np.float32)
    result = normalize_audio(audio, target_peak=0.9)
    # -0.045 is half the peak (0.09) in the original; ratio should hold after scaling
    assert float(result[2]) == pytest.approx(-0.5 * float(result[1]), abs=1e-6)


def test_does_not_amplify_near_silence():
    audio = np.zeros(100, dtype=np.float32)
    result = normalize_audio(audio, target_peak=0.9)
    assert np.abs(result).max() == 0.0


def test_clips_rather_than_overshoots_for_already_loud_audio():
    audio = np.array([0.0, 0.95, -0.6], dtype=np.float32)
    result = normalize_audio(audio, target_peak=0.9)
    assert np.abs(result).max() <= 1.0


def test_returns_float32():
    audio = np.array([0.0, 0.1, -0.05], dtype=np.float64)
    result = normalize_audio(audio, target_peak=0.9)
    assert result.dtype == np.float32


def test_ignores_single_sample_transient_when_computing_gain():
    # A lone click (e.g. a mic startup pop) at 10x the level of real
    # speech should not by itself dictate the gain applied to the rest
    # of a real-length clip - otherwise the actual speech stays quiet.
    rng = np.random.default_rng(0)
    speech_level = 0.02
    audio = (rng.random(16000).astype(np.float32) - 0.5) * (2 * speech_level)
    audio[100] = 0.2  # isolated transient, 10x the speech level
    result = normalize_audio(audio, target_peak=0.9)
    typical_peak_after = np.abs(np.delete(result, 100)).max()
    assert typical_peak_after > 0.5


def test_auto_model_is_large_v3_on_gpu_and_medium_on_cpu():
    assert stt.resolve_model("auto", "cuda") == "large-v3"
    assert stt.resolve_model("auto", "cpu") == "medium"
    assert stt.resolve_model("small", "cuda") == "small"


def test_engine_with_auto_model_on_cpu_loads_medium(monkeypatch):
    loaded = []
    monkeypatch.setattr(stt, "WhisperModel", lambda size, **kwargs: loaded.append(size) or object())
    engine = stt.SttEngine(model_size="auto", device="cpu")
    assert loaded == ["medium"]
    assert engine.model_size == "medium"
