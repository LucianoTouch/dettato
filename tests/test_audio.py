from unittest.mock import MagicMock, patch

import pytest

from dictation_tool.audio import AudioRecorder, _default_input_device


def test_resolves_wasapi_default_input_device():
    hostapis = [
        {"name": "MME", "default_input_device": 1},
        {"name": "Windows WASAPI", "default_input_device": 27},
    ]
    with patch("dictation_tool.audio.sd.query_hostapis", return_value=hostapis):
        assert _default_input_device() == 27


def test_returns_none_when_wasapi_has_no_input_device():
    hostapis = [
        {"name": "MME", "default_input_device": 1},
        {"name": "Windows WASAPI", "default_input_device": -1},
    ]
    with patch("dictation_tool.audio.sd.query_hostapis", return_value=hostapis):
        assert _default_input_device() is None


def test_returns_none_when_wasapi_unavailable():
    hostapis = [{"name": "MME", "default_input_device": 1}]
    with patch("dictation_tool.audio.sd.query_hostapis", return_value=hostapis):
        assert _default_input_device() is None


def test_returns_none_on_query_failure():
    with patch("dictation_tool.audio.sd.query_hostapis", side_effect=Exception("boom")):
        assert _default_input_device() is None


def test_start_closes_stream_and_clears_reference_when_start_fails():
    failing_stream = MagicMock()
    failing_stream.start.side_effect = RuntimeError("device busy")

    recorder = AudioRecorder()
    with patch("dictation_tool.audio.sd.InputStream", return_value=failing_stream):
        with pytest.raises(RuntimeError):
            recorder.start()

    failing_stream.close.assert_called_once()
    assert recorder._stream is None


def test_start_sets_stream_when_start_succeeds():
    ok_stream = MagicMock()

    recorder = AudioRecorder()
    with patch("dictation_tool.audio.sd.InputStream", return_value=ok_stream):
        recorder.start()

    ok_stream.start.assert_called_once()
    ok_stream.close.assert_not_called()
    assert recorder._stream is ok_stream
