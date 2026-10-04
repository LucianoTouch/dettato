import logging
import queue
import threading
import tkinter as tk
from dataclasses import replace
from tkinter import messagebox, ttk
from typing import Callable, Dict

from dettato.config import Config
from dettato.paths import resource_path

logger = logging.getLogger(__name__)

MODEL_CHOICES = [
    ("auto", "Automatico — large-v3 con GPU NVIDIA, medium senza"),
    ("large-v3", "large-v3 — massima precisione (consigliato)"),
    ("large-v3-turbo", "large-v3-turbo — quasi uguale, molto più veloce"),
    ("large-v2", "large-v2 — preciso, meno incline a inventare frasi"),
    ("medium", "medium — buon compromesso"),
    ("small", "small — veloce, meno preciso"),
    ("base", "base — molto veloce, poco preciso"),
    ("tiny", "tiny — solo per prove"),
]

DEVICE_CHOICES = [
    ("auto", "Automatico (GPU se disponibile)"),
    ("cuda", "GPU NVIDIA (CUDA)"),
    ("cpu", "CPU"),
]


def parse_replacements(text: str) -> Dict[str, str]:
    """'sbagliato = giusto' lines -> dict; '->' also accepted, junk skipped."""
    result = {}
    for line in text.splitlines():
        for sep in ("=", "->"):
            if sep in line:
                wrong, right = line.split(sep, 1)
                if wrong.strip() and right.strip():
                    result[wrong.strip()] = right.strip()
                break
    return result


def format_replacements(replacements: Dict[str, str]) -> str:
    return "\n".join(f"{wrong} = {right}" for wrong, right in replacements.items())


def _label_for(choices, value):
    for key, label in choices:
        if key == value:
            return label
    return value


def _key_for(choices, label):
    for key, text in choices:
        if text == label:
            return key
    return label


class SettingsWindow:
    """The "Dettato" window: current status plus every setting.

    Tk lives on its own thread (pystray owns the main one), so every call
    from outside goes through a queue drained on the Tk thread.
    """

    def __init__(
        self,
        get_config: Callable[[], Config],
        get_status: Callable[[], str],
        is_startup_enabled: Callable[[], bool],
        on_save: Callable[[Config, bool], bool],
        capture_hotkey: Callable[[], str],
        on_open_log: Callable[[], None],
        on_restart: Callable[[], None],
        on_quit: Callable[[], None],
        version: str = "",
        get_update: Callable[[], tuple] = lambda: (None, None, False),
        on_update: Callable[[], None] = lambda: None,
        on_check_updates: Callable[[], None] = lambda: None,
    ):
        self._version = version
        self._get_update = get_update
        self._on_update = on_update
        self._on_check_updates = on_check_updates
        self._get_config = get_config
        self._get_status = get_status
        self._is_startup_enabled = is_startup_enabled
        self._on_save = on_save
        self._capture_hotkey = capture_hotkey
        self._on_open_log = on_open_log
        self._on_restart = on_restart
        self._on_quit = on_quit
        self._calls = queue.Queue()
        self._root = None
        self._window = None
        self._thread = threading.Thread(target=self._run_tk, daemon=True, name="tk")
        self._thread.start()

    # ----- thread-safe API -------------------------------------------------

    def show(self) -> None:
        self._calls.put(self._show)

    def close(self) -> None:
        self._calls.put(self._shutdown)

    # ----- Tk thread -------------------------------------------------------

    def _run_tk(self) -> None:
        self._root = tk.Tk()
        self._root.withdraw()
        self._set_icon(self._root)
        self._root.after(100, self._drain)
        self._root.mainloop()

    def _drain(self) -> None:
        while True:
            try:
                call = self._calls.get_nowait()
            except queue.Empty:
                break
            try:
                call()
            except Exception:
                logger.exception("Errore nella finestra di Dettato")
        if self._root is not None:
            self._root.after(100, self._drain)

    def _shutdown(self) -> None:
        root, self._root = self._root, None
        root.quit()

    @staticmethod
    def _set_icon(window) -> None:
        try:
            window.iconbitmap(default=str(resource_path("dettato.ico")))
        except tk.TclError:
            pass

    def _show(self) -> None:
        if self._window is not None and self._window.winfo_exists():
            self._window.deiconify()
            self._bring_to_front(self._window)
            return
        self._build()

    @staticmethod
    def _bring_to_front(win) -> None:
        # A briefly-topmost window is how Tk gets above the app that
        # currently has focus (lift() alone is ignored by Windows).
        win.attributes("-topmost", True)
        win.lift()
        win.focus_force()
        win.after(300, lambda: win.winfo_exists() and win.attributes("-topmost", False))

    def _build(self) -> None:
        config = self._get_config()
        win = tk.Toplevel(self._root)
        self._window = win
        win.title("Dettato")
        win.resizable(False, False)
        win.protocol("WM_DELETE_WINDOW", win.destroy)

        frame = ttk.Frame(win, padding=16)
        frame.grid(sticky="nsew")
        frame.columnconfigure(1, weight=1)

        header = ttk.Frame(frame)
        header.grid(row=0, column=0, columnspan=3, sticky="w")
        ttk.Label(header, text="Dettato", font=("Segoe UI", 16, "bold")).grid(row=0, column=0, sticky="w")
        if self._version:
            ttk.Label(header, text=self._version, foreground="#777").grid(row=0, column=1, sticky="sw", padx=6, pady=(0, 4))

        # Shown only while a newer version is available (see _refresh_status).
        self._update_frame = ttk.Frame(frame, padding=(10, 8), relief="groove")
        self._update_frame.columnconfigure(0, weight=1)
        self._update_var = tk.StringVar()
        ttk.Label(self._update_frame, textvariable=self._update_var, wraplength=330, justify="left").grid(
            row=0, column=0, sticky="w"
        )
        self._update_button = ttk.Button(self._update_frame, text="Aggiorna ora", command=self._on_update)
        self._update_button.grid(row=0, column=1, sticky="e", padx=(8, 0))
        self._status_var = tk.StringVar(value=self._get_status())
        ttk.Label(frame, textvariable=self._status_var, foreground="#555").grid(
            row=1, column=0, columnspan=3, sticky="w", pady=(0, 12)
        )

        notebook = ttk.Notebook(frame)
        notebook.grid(row=3, column=0, columnspan=3, sticky="nsew")
        general = ttk.Frame(notebook, padding=12)
        general.columnconfigure(1, weight=1)
        precision = ttk.Frame(notebook, padding=12)
        precision.columnconfigure(0, weight=1)
        notebook.add(general, text="Generale")
        notebook.add(precision, text="Precisione")

        # ----- Generale
        row = 0
        ttk.Label(general, text="Scorciatoia per dettare").grid(row=row, column=0, sticky="w", pady=4)
        self._hotkey_var = tk.StringVar(value=config.hotkey)
        ttk.Entry(general, textvariable=self._hotkey_var, state="readonly", width=24).grid(
            row=row, column=1, sticky="ew", padx=8
        )
        self._capture_button = ttk.Button(general, text="Cambia…", command=self._start_capture)
        self._capture_button.grid(row=row, column=2, sticky="e")

        row += 1
        ttk.Label(general, text="Elaborazione").grid(row=row, column=0, sticky="w", pady=4)
        self._device_var = tk.StringVar(value=_label_for(DEVICE_CHOICES, config.device))
        ttk.Combobox(
            general,
            textvariable=self._device_var,
            values=[label for _, label in DEVICE_CHOICES],
            state="readonly",
            width=44,
        ).grid(row=row, column=1, columnspan=2, sticky="ew", padx=(8, 0))

        row += 1
        ttk.Label(general, text="Parole da eliminare").grid(row=row, column=0, sticky="w", pady=4)
        self._fillers_var = tk.StringVar(value=", ".join(config.filler_words))
        ttk.Entry(general, textvariable=self._fillers_var).grid(
            row=row, column=1, columnspan=2, sticky="ew", padx=(8, 0)
        )
        row += 1
        ttk.Label(general, text="separate da virgola", foreground="#777").grid(
            row=row, column=1, columnspan=2, sticky="w", padx=8
        )

        row += 1
        self._auto_paste_var = tk.BooleanVar(value=config.auto_paste)
        ttk.Checkbutton(
            general,
            text="Incolla subito il testo dove si trova il cursore\n(se disattivato resta solo negli appunti, da incollare con Ctrl+V)",
            variable=self._auto_paste_var,
        ).grid(row=row, column=0, columnspan=3, sticky="w", pady=(12, 4))

        row += 1
        self._startup_var = tk.BooleanVar(value=self._is_startup_enabled())
        ttk.Checkbutton(
            general, text="Avvia Dettato all'accesso a Windows", variable=self._startup_var
        ).grid(row=row, column=0, columnspan=3, sticky="w", pady=4)

        row += 1
        self._check_updates_var = tk.BooleanVar(value=config.check_updates)
        ttk.Checkbutton(
            general, text="Controlla automaticamente gli aggiornamenti", variable=self._check_updates_var
        ).grid(row=row, column=0, columnspan=2, sticky="w", pady=4)
        ttk.Button(general, text="Controlla ora", command=self._on_check_updates).grid(row=row, column=2, sticky="e")

        # ----- Precisione
        ttk.Label(precision, text="Modello").grid(row=0, column=0, sticky="w")
        self._model_var = tk.StringVar(value=_label_for(MODEL_CHOICES, config.model_size))
        ttk.Combobox(
            precision,
            textvariable=self._model_var,
            values=[label for _, label in MODEL_CHOICES],
            state="readonly",
            width=56,
        ).grid(row=1, column=0, sticky="ew", pady=(2, 10))

        ttk.Label(precision, text="Vocabolario — nomi e termini da scrivere giusti, uno per riga").grid(
            row=2, column=0, sticky="w"
        )
        self._vocabulary_text = self._make_text(precision, "\n".join(config.vocabulary))
        self._vocabulary_text.grid(row=3, column=0, sticky="ew", pady=(2, 10))

        ttk.Label(precision, text="Correzioni — una per riga, nella forma:  sbagliato = giusto").grid(
            row=4, column=0, sticky="w"
        )
        self._replacements_text = self._make_text(precision, format_replacements(config.replacements))
        self._replacements_text.grid(row=5, column=0, sticky="ew", pady=(2, 0))
        ttk.Label(
            precision, text="es.  meta ed = Meta Ads      Valgono subito, senza riavviare.", foreground="#777"
        ).grid(row=6, column=0, sticky="w")

        buttons = ttk.Frame(frame)
        buttons.grid(row=4, column=0, columnspan=3, sticky="ew", pady=(16, 0))
        buttons.columnconfigure(2, weight=1)
        ttk.Button(buttons, text="Apri il log", command=self._on_open_log).grid(row=0, column=0)
        ttk.Button(buttons, text="Esci da Dettato", command=self._quit).grid(row=0, column=1, padx=8)
        ttk.Button(buttons, text="Chiudi", command=win.destroy).grid(row=0, column=3)
        ttk.Button(buttons, text="Salva", command=self._save).grid(row=0, column=4, padx=(8, 0))

        win.bind("<Escape>", lambda e: win.destroy())
        self._refresh_status()
        win.update_idletasks()
        x = (win.winfo_screenwidth() - win.winfo_width()) // 2
        y = (win.winfo_screenheight() - win.winfo_height()) // 3
        win.geometry(f"+{x}+{y}")
        self._bring_to_front(win)

    @staticmethod
    def _make_text(parent, content: str) -> tk.Text:
        text = tk.Text(parent, height=5, width=56, font=("Segoe UI", 9), wrap="none", undo=True)
        text.insert("1.0", content)
        return text

    def _refresh_status(self) -> None:
        if self._window is None or not self._window.winfo_exists():
            return
        self._status_var.set(self._get_status())
        release, status, busy = self._get_update()
        if release is None:
            self._update_frame.grid_remove()
        else:
            notes = "\n".join(release.notes.strip().splitlines()[:4])
            text = f"È disponibile Dettato {release.version}."
            if notes:
                text += f"\n{notes}"
            if status:
                text += f"\n\n{status}"
            self._update_var.set(text)
            self._update_button.configure(state="disabled" if busy else "normal")
            self._update_frame.grid(row=2, column=0, columnspan=3, sticky="ew", pady=(0, 12))
        self._window.after(500, self._refresh_status)

    def _start_capture(self) -> None:
        self._capture_button.configure(state="disabled", text="Premi i tasti…")
        self._hotkey_var.set("premi la nuova combinazione…")

        def worker():
            try:
                hotkey = self._capture_hotkey()
            except Exception:
                logger.exception("Registrazione della scorciatoia non riuscita")
                hotkey = ""
            self._calls.put(lambda: self._finish_capture(hotkey))

        threading.Thread(target=worker, daemon=True).start()

    def _finish_capture(self, hotkey: str) -> None:
        if self._window is None or not self._window.winfo_exists():
            return
        self._hotkey_var.set(hotkey or self._get_config().hotkey)
        self._capture_button.configure(state="normal", text="Cambia…")

    def _save(self) -> None:
        current = self._get_config()
        fillers = [w.strip() for w in self._fillers_var.get().split(",") if w.strip()]
        new = replace(
            current,
            hotkey=self._hotkey_var.get().strip() or current.hotkey,
            model_size=_key_for(MODEL_CHOICES, self._model_var.get()),
            device=_key_for(DEVICE_CHOICES, self._device_var.get()),
            filler_words=fillers,
            auto_paste=self._auto_paste_var.get(),
            run_on_startup=self._startup_var.get(),
            check_updates=self._check_updates_var.get(),
            vocabulary=[t.strip() for t in self._vocabulary_text.get("1.0", "end").splitlines() if t.strip()],
            replacements=parse_replacements(self._replacements_text.get("1.0", "end")),
        )
        needs_restart = new.model_size != current.model_size or new.device != current.device
        if not self._on_save(new, needs_restart):
            messagebox.showerror(
                "Dettato",
                f"Impossibile usare la scorciatoia '{new.hotkey}': forse è già usata da un altro programma.",
                parent=self._window,
            )
            self._hotkey_var.set(current.hotkey)
            return
        if needs_restart:
            if messagebox.askyesno(
                "Dettato",
                "Il nuovo modello sarà usato al prossimo avvio.\nRiavviare Dettato adesso?",
                parent=self._window,
            ):
                self._window.destroy()
                self._on_restart()
                return
        self._window.destroy()

    def _quit(self) -> None:
        if messagebox.askyesno("Dettato", "Chiudere Dettato?\nLa scorciatoia non funzionerà più finché non lo riavvii.", parent=self._window):
            self._window.destroy()
            self._on_quit()
