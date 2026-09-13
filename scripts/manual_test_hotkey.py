import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import time
from dictation_tool.hotkey import HotkeyListener


def main():
    count = {"n": 0}

    def on_toggle():
        count["n"] += 1
        print(f"Hotkey premuta! (volta numero {count['n']})")

    listener = HotkeyListener("ctrl+space", on_toggle)
    ok = listener.start()
    if not ok:
        print("Registrazione hotkey fallita.")
        return

    print("Premi Ctrl+Space alcune volte in qualsiasi finestra. Il test termina dopo 15 secondi.")
    time.sleep(15)
    listener.stop()
    print(f"Totale attivazioni: {count['n']}")


if __name__ == "__main__":
    main()
