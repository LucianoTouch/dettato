import sys
import soundfile as sf
from dictation_tool.stt import SttEngine


def main():
    if len(sys.argv) != 2:
        print("Uso: python scripts/smoke_test_stt.py <path_audio.wav>")
        sys.exit(1)

    audio_path = sys.argv[1]
    audio, sample_rate = sf.read(audio_path, dtype="float32")
    if audio.ndim > 1:
        audio = audio.mean(axis=1)

    print("Carico il modello (device=auto)...")
    engine = SttEngine(model_size="large-v3", device="auto")
    print(f"Device effettivo: {engine.device}")

    print("Trascrivo...")
    text = engine.transcribe(audio, sample_rate=sample_rate)
    print(f"Trascrizione: {text}")


if __name__ == "__main__":
    main()
