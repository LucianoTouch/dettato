from pathlib import Path
from unittest.mock import patch

from dettato import sound


def test_play_waits_and_closes_when_wait_true():
    calls = []

    def fake_mci(command):
        calls.append(command)
        return True

    with patch("dettato.sound._mci", side_effect=fake_mci):
        sound.play(Path("bip.mp3"), wait=True)

    assert any(c.startswith("open") for c in calls)
    assert any("play dettato_beep wait" == c for c in calls)
    assert calls.count("close dettato_beep") == 2  # pre-emptive + post-wait cleanup


def test_play_does_not_close_when_not_waiting():
    calls = []

    def fake_mci(command):
        calls.append(command)
        return True

    with patch("dettato.sound._mci", side_effect=fake_mci):
        sound.play(Path("bip.mp3"), wait=False)

    assert calls.count("close dettato_beep") == 1  # only the pre-emptive close


def test_play_does_not_raise_when_open_fails():
    with patch("dettato.sound._mci", return_value=False):
        sound.play(Path("does-not-exist.mp3"))  # should not raise
