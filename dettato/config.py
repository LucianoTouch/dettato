import copy
import json
import logging
from dataclasses import dataclass, asdict, field, fields
from pathlib import Path
from typing import Dict, List, Optional

from dettato import paths

logger = logging.getLogger(__name__)

DEFAULT_FILLER_WORDS = ["ehm", "uhm", "cioè cioè", "insomma insomma"]

DEFAULT_CONFIG = {
    "hotkey": "ctrl+space",
    "model_size": "auto",
    "device": "auto",
    "filler_words": DEFAULT_FILLER_WORDS,
    "auto_paste": True,
    "run_on_startup": False,
    "vocabulary": [],
    "replacements": {},
    "check_updates": True,
}


@dataclass
class Config:
    hotkey: str = "ctrl+space"
    # "auto": large-v3 on an NVIDIA GPU, medium on CPU (see stt.resolve_model).
    model_size: str = "auto"
    device: str = "auto"
    filler_words: List[str] = field(default_factory=lambda: list(DEFAULT_FILLER_WORDS))
    auto_paste: bool = True
    run_on_startup: bool = False
    # Names/terms Whisper should spell right (fed as its initial prompt).
    vocabulary: List[str] = field(default_factory=list)
    # Fixed corrections applied to the text, e.g. {"meta ed": "Meta Ads"}.
    replacements: Dict[str, str] = field(default_factory=dict)
    check_updates: bool = True


def default_config_path() -> Path:
    return paths.data_dir() / "config.json"


def load_config(path: Optional[Path] = None) -> Config:
    path = path or default_config_path()
    if not path.exists():
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(DEFAULT_CONFIG, indent=2, ensure_ascii=False), encoding="utf-8")
        return Config()

    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        # Ignore unknown keys (e.g. leftover fields from an older version)
        # instead of letting Config(**merged) reject the whole file and
        # silently fall back to all-defaults over one stray field.
        valid_keys = {f.name for f in fields(Config)}
        merged = {k: v for k, v in {**copy.deepcopy(DEFAULT_CONFIG), **data}.items() if k in valid_keys}
        return Config(**merged)
    except Exception as e:
        logger.warning(f"Impossibile leggere il file di configurazione '{path}' ({e}), uso i valori predefiniti")
        return Config()


def save_config(config: Config, path: Optional[Path] = None) -> None:
    path = path or default_config_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(asdict(config), indent=2, ensure_ascii=False), encoding="utf-8")
