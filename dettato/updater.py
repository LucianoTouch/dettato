"""Check GitHub Releases for a newer Dettato and install it.

Each release carries three assets: the full Dettato-Setup.exe, a small
Dettato-update.zip holding only Dettato.exe (all of Dettato's own code
lives in the exe), and manifest.json describing both. When the release
was built against the same bundled libraries (same runtime id), swapping
the exe is enough; otherwise the full installer runs.
"""
import hashlib
import json
import logging
import shutil
import subprocess
import urllib.request
import zipfile
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Optional

from dettato import paths

logger = logging.getLogger(__name__)

REPO = "LucianoTouch/dettato"
_API_LATEST = "https://api.github.com/repos/{repo}/releases/latest"
_USER_AGENT = "Dettato-updater"
_TIMEOUT = 15
EXE_NAME = "Dettato.exe"
_OLD_EXE_NAME = "Dettato.old.exe"
_NEW_EXE_NAME = "Dettato.new.exe"


class UpdateError(Exception):
    pass


@dataclass
class Asset:
    name: str
    url: str
    sha256: str
    size: int


@dataclass
class Release:
    version: str
    notes: str
    runtime_id: str
    setup: Asset
    update: Optional[Asset]

    def is_light_for(self, runtime_id: str) -> bool:
        return self.update is not None and self.runtime_id == runtime_id

    def download_size_for(self, runtime_id: str) -> int:
        return (self.update if self.is_light_for(runtime_id) else self.setup).size


def parse_version(text: str) -> tuple:
    text = text.strip().lstrip("vV")
    return tuple(int(part) for part in text.split("."))


def is_newer(remote: str, local: str) -> bool:
    try:
        return parse_version(remote) > parse_version(local)
    except ValueError:
        return False


def runtime_id() -> str:
    """Identifies the bundled libraries; "dev" when running from source."""
    if not paths.is_frozen():
        return "dev"
    try:
        return paths.resource_path("runtime_id.txt").read_text(encoding="utf-8").strip()
    except OSError:
        return "unknown"


def _open(url: str):
    request = urllib.request.Request(url, headers={"User-Agent": _USER_AGENT})
    return urllib.request.urlopen(request, timeout=_TIMEOUT)


def _get_json(url: str):
    with _open(url) as response:
        return json.loads(response.read().decode("utf-8"))


def parse_release(release_json: dict, manifest: dict) -> Release:
    urls = {a["name"]: a["browser_download_url"] for a in release_json.get("assets", [])}

    def asset(key: str) -> Optional[Asset]:
        info = manifest.get(key)
        if not info or info.get("name") not in urls:
            return None
        return Asset(info["name"], urls[info["name"]], info["sha256"].lower(), int(info["size"]))

    setup = asset("setup")
    if setup is None:
        raise UpdateError("La release non contiene l'installer")
    return Release(
        version=str(manifest["version"]),
        notes=str(manifest.get("notes") or release_json.get("body") or ""),
        runtime_id=str(manifest.get("runtime_id", "")),
        setup=setup,
        update=asset("update"),
    )


def fetch_latest(repo: str = REPO) -> Release:
    release_json = _get_json(_API_LATEST.format(repo=repo))
    manifest_url = next(
        (a["browser_download_url"] for a in release_json.get("assets", []) if a["name"] == "manifest.json"),
        None,
    )
    if manifest_url is None:
        raise UpdateError("La release non contiene manifest.json")
    return parse_release(release_json, _get_json(manifest_url))


def check(current_version: str, repo: str = REPO) -> Optional[Release]:
    """The latest release if newer than current_version, else None.
    Network problems raise; callers decide whether to stay silent."""
    release = fetch_latest(repo)
    return release if is_newer(release.version, current_version) else None


def download(asset: Asset, dest_dir: Path, progress: Callable[[int, int], None] = lambda done, total: None) -> Path:
    dest_dir.mkdir(parents=True, exist_ok=True)
    dest = dest_dir / asset.name
    digest = hashlib.sha256()
    done = 0
    with _open(asset.url) as response, open(dest, "wb") as out:
        while True:
            chunk = response.read(1024 * 1024)
            if not chunk:
                break
            out.write(chunk)
            digest.update(chunk)
            done += len(chunk)
            progress(done, asset.size)
    if digest.hexdigest() != asset.sha256:
        dest.unlink(missing_ok=True)
        raise UpdateError(f"File scaricato danneggiato ({asset.name}): riprova più tardi")
    return dest


def install_light(zip_path: Path, app_dir: Path) -> None:
    """Swap in the new Dettato.exe next to the running one.

    Windows refuses to overwrite a running exe but allows renaming it, so
    the current one becomes Dettato.old.exe (deleted on next start by
    cleanup_old) and the new one takes its name. Rolled back on failure.
    """
    exe = app_dir / EXE_NAME
    old = app_dir / _OLD_EXE_NAME
    new = app_dir / _NEW_EXE_NAME
    with zipfile.ZipFile(zip_path) as archive:
        if EXE_NAME not in archive.namelist():
            raise UpdateError("Pacchetto di aggiornamento non valido")
        with archive.open(EXE_NAME) as src, open(new, "wb") as dst:
            shutil.copyfileobj(src, dst)
    try:
        old.unlink(missing_ok=True)
    except OSError:
        # Still locked by a previous, not yet exited instance.
        old = app_dir / f"Dettato.old-{new.stat().st_mtime_ns}.exe"
    exe.rename(old)
    try:
        new.rename(exe)
    except OSError:
        old.rename(exe)
        new.unlink(missing_ok=True)
        raise


def cleanup_old(app_dir: Path) -> None:
    for leftover in list(app_dir.glob("Dettato.old*.exe")) + [app_dir / _NEW_EXE_NAME]:
        try:
            leftover.unlink(missing_ok=True)
        except OSError:
            pass


def launch_full(setup_path: Path) -> None:
    """Run the installer with its progress bar visible; it closes and
    restarts Dettato by itself."""
    subprocess.Popen([str(setup_path), "/SILENT", "/SUPPRESSMSGBOXES", "/NORESTART"], close_fds=True)
