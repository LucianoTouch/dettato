import numpy as np
import pytest

from dictation_tool.stt import normalize_audio


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
