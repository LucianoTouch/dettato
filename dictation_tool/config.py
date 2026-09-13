import json
import os
from dataclasses import dataclass, asdict, field
from pathlib import Path
from typing import List, Optional

DEFAULT_FILLER_WORDS = ["ehm", "uhm", "cioè cioè", "insomma insomma"]

DEFAULT_CONFIG = {
    "hotkey": "ctrl+space",
    "model_size": "large-v3",
    "device": "auto",
    "filler_words": DEFAULT_FILLER_WORDS,
    "auto_paste": True,
    "run_on_startup": False,
}


@dataclass
class Config:
    hotkey: str = "ctrl+space"
    model_size: str = "large-v3"
    device: str = "auto"
    filler_words: List[str] = field(default_factory=lambda: list(DEFAULT_FILLER_WORDS))
    auto_paste: bool = True
    run_on_startup: bool = False


def default_config_path() -> Path:
    appdata = os.environ.get("APPDATA", str(Path.home()))
    return Path(appdata) / "dictation-tool" / "config.json"


def load_config(path: Optional[Path] = None) -> Config:
    path = path or default_config_path()
    if not path.exists():
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(DEFAULT_CONFIG, indent=2, ensure_ascii=False), encoding="utf-8")
        return Config()

    data = json.loads(path.read_text(encoding="utf-8"))
    merged = {**DEFAULT_CONFIG, **data}
    return Config(**merged)


def save_config(config: Config, path: Optional[Path] = None) -> None:
    path = path or default_config_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(asdict(config), indent=2, ensure_ascii=False), encoding="utf-8")
