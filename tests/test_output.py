from unittest.mock import patch

from dettato.output import OutputHandler


def test_leaves_text_on_clipboard_when_auto_paste_disabled():
    handler = OutputHandler(paste_delay=0)
    with patch("dettato.output.pyperclip.paste", return_value="testo precedente") as mock_paste, \
         patch("dettato.output.pyperclip.copy") as mock_copy, \
         patch("dettato.output.keyboard.send") as mock_send:
        handler.paste("nuovo testo", auto_paste=False)

    mock_send.assert_not_called()
    mock_paste.assert_not_called()
    mock_copy.assert_called_once_with("nuovo testo")


def test_pastes_and_restores_original_clipboard_when_auto_paste_enabled():
    handler = OutputHandler(paste_delay=0)
    with patch("dettato.output.pyperclip.paste", return_value="testo precedente"), \
         patch("dettato.output.pyperclip.copy") as mock_copy, \
         patch("dettato.output.keyboard.send") as mock_send:
        handler.paste("nuovo testo", auto_paste=True)

    mock_send.assert_called_once_with("ctrl+v")
    assert mock_copy.call_args_list[0].args == ("nuovo testo",)
    assert mock_copy.call_args_list[-1].args == ("testo precedente",)


def test_does_nothing_for_empty_text():
    handler = OutputHandler(paste_delay=0)
    with patch("dettato.output.pyperclip.copy") as mock_copy, \
         patch("dettato.output.keyboard.send") as mock_send:
        handler.paste("", auto_paste=True)

    mock_copy.assert_not_called()
    mock_send.assert_not_called()
