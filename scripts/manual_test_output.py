import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import time
import pyperclip
from dictation_tool.output import OutputHandler


def main():
    pyperclip.copy("contenuto clipboard originale di test")
    print("Clipboard impostata su testo di prova.")
    print("Apri il Blocco Note e clicca nel campo di testo. Hai 3 secondi.")
    time.sleep(3)

    handler = OutputHandler()
    handler.paste("Questo è un testo di prova dettato.", auto_paste=True)

    time.sleep(1)
    restored = pyperclip.paste()
    print(f"Clipboard dopo il ripristino: {restored!r}")
    assert restored == "contenuto clipboard originale di test", "Il ripristino della clipboard è fallito"
    print("OK: clipboard ripristinata correttamente.")


if __name__ == "__main__":
    main()
