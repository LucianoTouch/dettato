import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import time
from dettato.tray import TrayIcon


def main():
    tray = TrayIcon(
        on_exit=lambda: print("Uscita richiesta"),
        on_toggle_startup=lambda v: print(f"Startup: {v}"),
        startup_enabled=False,
    )
    tray.run_detached()

    for state in ["idle", "recording", "transcribing", "idle"]:
        print(f"Imposto stato: {state}")
        tray.set_state(state)
        time.sleep(3)

    print("Controlla visivamente l'icona nella tray (grigia/rossa/gialla/grigia).")
    print("Prova anche il menu con click destro (Avvio automatico, Esci).")
    time.sleep(20)


if __name__ == "__main__":
    main()
