import logging
import os
from pathlib import Path

from dictation_tool.config import load_config
from dictation_tool.app import App


def _log_file_path() -> Path:
    appdata = os.environ.get("APPDATA", str(Path.home()))
    return Path(appdata) / "dictation-tool" / "dictation.log"


def main():
    log_format = "%(asctime)s %(levelname)s %(message)s"
    log_path = _log_file_path()
    log_path.parent.mkdir(parents=True, exist_ok=True)
    logging.basicConfig(
        level=logging.INFO,
        format=log_format,
        handlers=[
            logging.StreamHandler(),
            logging.FileHandler(log_path, encoding="utf-8"),
        ],
    )
    config = load_config()
    app = App(config)
    app.run()


if __name__ == "__main__":
    main()
