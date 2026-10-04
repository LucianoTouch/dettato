"""Manual accuracy check: silence/noise rejection and vocabulary effect.

Synthesizes Italian sentences with Windows' Italian TTS voice, optionally
mixes them with a few seconds of real room noise from the default mic
(kept in memory only), and prints what Dettato's pipeline produces with
and without a vocabulary.

    .venv\\Scripts\\python scripts\\accuracy_check.py [--mic] [--model large-v3]
"""
import argparse
import subprocess
import sys
import tempfile
import time
from pathlib import Path

import numpy as np
import soundfile as sf

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from dettato.postprocess import clean_transcript  # noqa: E402
from dettato.stt import SttEngine, trim_silence  # noqa: E402

SR = 16000
VOCABULARY = ["Meta Ads", "Costruisci & Arreda", "Vision Ark", "Euroffice", "PED"]
REPLACEMENTS = {}
SENTENCES = [
    "Domani pubblichiamo la campagna Meta Ads per Costruisci e Arreda.",
    "Invia il PED di ottobre a Vision Ark e a Euroffice entro venerdì.",
    "Sì, va bene.",
]


def synthesize(text: str) -> np.ndarray:
    with tempfile.TemporaryDirectory() as tmp:
        wav = Path(tmp) / "tts.wav"
        script = (
            "Add-Type -AssemblyName System.Speech;"
            "$s = New-Object System.Speech.Synthesis.SpeechSynthesizer;"
            "$s.SelectVoice('Microsoft Elsa Desktop');"
            "$f = New-Object System.Speech.AudioFormat.SpeechAudioFormatInfo(16000, "
            "[System.Speech.AudioFormat.AudioBitsPerSample]::Sixteen, "
            "[System.Speech.AudioFormat.AudioChannel]::Mono);"
            f"$s.SetOutputToWaveFile('{wav}', $f);"
            f"$s.Speak('{text.replace(chr(39), chr(39) * 2)}');"
            "$s.Dispose()"
        )
        subprocess.run(["powershell", "-NoProfile", "-Command", script], check=True)
        audio, sr = sf.read(wav, dtype="float32")
    assert sr == SR
    # A typical headset level, well below full scale.
    return audio * 0.3


def record_room_noise(seconds: float) -> np.ndarray:
    from dettato.audio import AudioRecorder

    recorder = AudioRecorder()
    print(f"Registro {seconds:.0f} s di rumore ambiente dal microfono (non parlare)…")
    recorder.start()
    time.sleep(seconds)
    return recorder.stop()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--mic", action="store_true", help="usa rumore ambiente reale dal microfono")
    parser.add_argument("--model", default="large-v3")
    args = parser.parse_args()

    if args.mic:
        noise = record_room_noise(4.0)
        rms = float(np.sqrt(np.mean(noise ** 2)))
        print(f"Rumore ambiente: RMS {rms:.5f}, picco {np.abs(noise).max():.4f}")
    else:
        noise = (np.random.default_rng(0).standard_normal(SR * 4) * 0.001).astype(np.float32)

    engine = SttEngine(model_size=args.model, device="auto")
    print(f"Modello {args.model} su {engine.device}\n")

    print("== Solo rumore (atteso: nessun testo)")
    print(f"   trim_silence: {trim_silence(noise).size / SR:.2f} s di audio tenuto")
    print(f"   risultato: {engine.transcribe(noise)!r}\n")

    head, tail = noise[: SR], noise[SR : 2 * SR]
    for sentence in SENTENCES:
        audio = np.concatenate([head, synthesize(sentence), tail]).astype(np.float32)
        print(f"== Detto:          {sentence}")
        plain = clean_transcript(engine.transcribe(audio), [], REPLACEMENTS)
        print(f"   senza vocabolario: {plain}")
        tuned = clean_transcript(engine.transcribe(audio, vocabulary=VOCABULARY), [], REPLACEMENTS)
        print(f"   con vocabolario:   {tuned}\n")


if __name__ == "__main__":
    main()
