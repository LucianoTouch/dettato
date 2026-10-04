"""Regenerate assets/dettato.ico (exe, shortcuts, window) from dettato.icons."""
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from dettato.icons import STATE_COLORS, make_icon

out = Path(__file__).resolve().parent.parent / "assets" / "dettato.ico"
image = make_icon(STATE_COLORS["idle"], 256)
image.save(out, sizes=[(16, 16), (24, 24), (32, 32), (48, 48), (64, 64), (128, 128), (256, 256)])
image.save(out.with_suffix(".png"))
print(f"Scritto {out}")
