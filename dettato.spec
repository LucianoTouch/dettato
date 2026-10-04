# PyInstaller spec for Dettato.exe — built by build.ps1, not by hand.
from pathlib import Path

from PyInstaller.utils.hooks import collect_all, collect_dynamic_libs

import nvidia

datas = [("assets/bip.mp3", "assets"), ("assets/dettato.ico", "assets")]
binaries = []
hiddenimports = ["pystray._win32", "dettato.stt"]

for package in ("faster_whisper", "ctranslate2"):
    d, b, h = collect_all(package)
    datas += d
    binaries += b
    hiddenimports += h
binaries += collect_dynamic_libs("onnxruntime")

# CUDA runtime from the nvidia-* wheels (namespace packages, so the hooks
# don't see them). Kept at nvidia/<pkg>/bin: dettato.stt looks there.
for root in nvidia.__path__:
    for dll in Path(root).glob("*/bin/*.dll"):
        binaries.append((str(dll), f"nvidia/{dll.parent.parent.name}/bin"))

a = Analysis(
    ["main.py"],
    pathex=[],
    binaries=binaries,
    datas=datas,
    hiddenimports=hiddenimports,
    excludes=["pytest", "_pytest", "IPython", "matplotlib"],
    noarchive=False,
)

# Fingerprint of everything bundled next to the exe (DLLs, extensions,
# data). Dettato's own code lives inside Dettato.exe, so a release with the
# same fingerprint can be installed by swapping just the exe (see
# dettato/updater.py); a different one needs the full installer.
import hashlib
import os

_fingerprint = hashlib.sha256()
for dest, src, _kind in sorted(a.binaries + a.datas):
    _fingerprint.update(f"{dest}|{os.path.getsize(src)}\n".encode())
_runtime_id_file = Path(workpath) / "runtime_id.txt"
_runtime_id_file.write_text(_fingerprint.hexdigest()[:16], encoding="utf-8")
a.datas += [("assets/runtime_id.txt", str(_runtime_id_file), "DATA")]

pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="Dettato",
    icon="assets/dettato.ico",
    console=False,
    upx=False,
    version="version_info.txt",
)
coll = COLLECT(exe, a.binaries, a.datas, strip=False, upx=False, name="Dettato")
