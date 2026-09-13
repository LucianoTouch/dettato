# Dictation Tool

A Windows background dictation tool for Italian. Press a global hotkey (`Ctrl+Space` by
default) to start and stop recording from your microphone; the audio is transcribed
locally using OpenAI's Whisper `large-v3` model via `faster-whisper` (no audio or text
ever leaves your machine), cleaned up, and pasted into whatever window has focus. A
system tray icon shows the current state (idle / recording / transcribing).

## Setup

```
pip install -r requirements.txt
python main.py
```

## Testing

`pytest` runs the automated test suite. The `scripts/manual_test_*.py` files are not
part of the automated suite — they are for manual, hands-on smoke-testing of things
that need real hardware or a GUI (microphone, global hotkey, tray icon, clipboard),
as described in the project plan.
