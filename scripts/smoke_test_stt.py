import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import soundfile as sf
from dettato.stt import SttEngine


def main():
    if len(sys.argv) != 2:
        print("Uso: python scripts/smoke_test_stt.py <path_audio.wav>")
        sys.exit(1)

    audio_path = sys.argv[1]
    audio, sample_rate = sf.read(audio_path, dtype="float32")
    if audio.ndim > 1:
        audio = audio.mean(axis=1)

    if sample_rate != 16000:
        print(
            f"Errore: il file audio è a {sample_rate} Hz, ma è richiesto un file mono a 16000 Hz. "
            "Riconverti/riesporta il file a 16kHz mono (ad es. con uno strumento di conversione audio) "
            "prima di eseguire questo test."
        )
        sys.exit(1)

    print("Carico il modello (device=auto)...")
    engine = SttEngine(model_size="large-v3", device="auto")
    print(f"Device effettivo: {engine.device}")

    print("Trascrivo...")
    text = engine.transcribe(audio, sample_rate=sample_rate)
    print(f"Trascrizione: {text}")


if __name__ == "__main__":
    main()
