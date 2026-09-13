from unittest.mock import patch

from dictation_tool.audio import _default_input_device


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
