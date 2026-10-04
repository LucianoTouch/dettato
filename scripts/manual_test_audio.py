import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import time
import soundfile as sf
from dettato.audio import AudioRecorder


def main():
    recorder = AudioRecorder()
    print("Registrazione per 3 secondi... parla ora.")
    recorder.start()
    time.sleep(3)
    audio = recorder.stop()
    sf.write("test_recording.wav", audio, recorder.sample_rate)
    print(f"Salvato test_recording.wav, {len(audio)} campioni.")
    print("Riproduci il file per verificare che l'audio sia comprensibile.")


if __name__ == "__main__":
    main()
