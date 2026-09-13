from unittest.mock import MagicMock, patch

import pytest

from dictation_tool.audio import AudioRecorder


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
