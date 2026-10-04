import logging
import sys
import threading
from pathlib import Path

from dettato import paths, singleinstance


def _stop_running_instance() -> int:
    if singleinstance.signal_exit_event():
        print("Dettato: chiusura richiesta.")
        return 0
    print("Dettato non risulta in esecuzione.")
    return 1


def _watch_event(handle, callback, repeat: bool) -> None:
    while True:
        singleinstance.wait_for_event(handle)
        callback()
        if not repeat:
            return


def _setup_logging() -> None:
    log_path = paths.log_file_path()
    log_path.parent.mkdir(parents=True, exist_ok=True)
    handlers = [logging.FileHandler(log_path, encoding="utf-8")]
    # The windowed exe / pythonw have no console to write to.
    if sys.stderr is not None:
        handlers.append(logging.StreamHandler())
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(message)s",
        handlers=handlers,
    )


def main():
    args = sys.argv[1:]
    if "--stop" in args:
        sys.exit(_stop_running_instance())

    paths.migrate_legacy_data()
    _setup_logging()

    if "--restart" in args:
        acquired = singleinstance.acquire_single_instance_lock_waiting(timeout=15)
    else:
        acquired = singleinstance.acquire_single_instance_lock()
    if not acquired:
        # Clicking the Dettato icon while it's already running brings up
        # its window instead of silently doing nothing.
        logging.info("Dettato e' gia' in esecuzione, apro la sua finestra.")
        singleinstance.signal_show_event()
        return

    # Imported here, after the single-instance check: a duplicate launch
    # shouldn't pay for loading the UI and audio stack.
    from dettato import __version__, updater
    from dettato.config import load_config
    from dettato.app import App

    logging.info(f"Dettato {__version__}")
    if paths.is_frozen():
        # Leftover of a light update (the replaced exe can only be deleted
        # once the old process has exited).
        updater.cleanup_old(Path(sys.executable).parent)

    config = load_config()
    app = App(config)

    exit_handle = singleinstance.create_exit_event()
    show_handle = singleinstance.create_show_event()
    threading.Thread(target=_watch_event, args=(exit_handle, app.request_exit, False), daemon=True).start()
    threading.Thread(target=_watch_event, args=(show_handle, app.show_window, True), daemon=True).start()

    app.run()


if __name__ == "__main__":
    main()
