import hashlib
import io
import json
import zipfile
from pathlib import Path
from unittest.mock import patch

import pytest

from dettato import updater
from dettato.updater import Asset, Release, UpdateError


def _release_json(*names):
    return {
        "tag_name": "v1.2.0",
        "body": "note dalla release",
        "assets": [{"name": n, "browser_download_url": f"https://example.test/{n}"} for n in names],
    }


def _manifest(version="1.2.0", runtime_id="abc", with_update=True):
    m = {
        "version": version,
        "runtime_id": runtime_id,
        "notes": "Migliorata la precisione",
        "setup": {"name": "Dettato-Setup.exe", "sha256": "AA" * 32, "size": 100},
    }
    if with_update:
        m["update"] = {"name": "Dettato-update.zip", "sha256": "bb" * 32, "size": 10}
    return m


# ----- versions


@pytest.mark.parametrize(
    "remote,local,newer",
    [("1.2.0", "1.1.0", True), ("v1.10.0", "1.9.9", True), ("1.1.0", "1.1.0", False), ("1.0.9", "1.1.0", False), ("boh", "1.0.0", False)],
)
def test_is_newer(remote, local, newer):
    assert updater.is_newer(remote, local) is newer


# ----- release parsing


def test_parse_release_maps_manifest_to_download_urls():
    release = updater.parse_release(
        _release_json("Dettato-Setup.exe", "Dettato-update.zip", "manifest.json"), _manifest()
    )
    assert release.version == "1.2.0"
    assert release.setup.url == "https://example.test/Dettato-Setup.exe"
    assert release.setup.sha256 == "aa" * 32
    assert release.update.url == "https://example.test/Dettato-update.zip"
    assert release.notes == "Migliorata la precisione"


def test_parse_release_without_setup_is_an_error():
    with pytest.raises(UpdateError):
        updater.parse_release(_release_json("manifest.json"), _manifest())


def test_parse_release_tolerates_missing_light_package():
    release = updater.parse_release(_release_json("Dettato-Setup.exe", "manifest.json"), _manifest())
    assert release.update is None
    assert not release.is_light_for("abc")


def test_light_update_only_when_runtime_matches():
    release = updater.parse_release(
        _release_json("Dettato-Setup.exe", "Dettato-update.zip", "manifest.json"), _manifest(runtime_id="abc")
    )
    assert release.is_light_for("abc")
    assert not release.is_light_for("other")
    assert release.download_size_for("abc") == 10
    assert release.download_size_for("other") == 100


def test_check_returns_release_only_when_newer():
    def fake_get_json(url):
        if url.endswith("/releases/latest"):
            return _release_json("Dettato-Setup.exe", "manifest.json")
        return _manifest(version="1.2.0")

    with patch.object(updater, "_get_json", side_effect=fake_get_json):
        assert updater.check("1.1.0").version == "1.2.0"
        assert updater.check("1.2.0") is None


def test_check_propagates_network_errors():
    with patch.object(updater, "_get_json", side_effect=OSError("offline")):
        with pytest.raises(OSError):
            updater.check("1.1.0")


# ----- download


class _FakeResponse(io.BytesIO):
    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False


def test_download_verifies_hash(tmp_path):
    payload = b"x" * 5000
    asset = Asset("f.bin", "https://example.test/f.bin", hashlib.sha256(payload).hexdigest(), len(payload))
    seen = []
    with patch.object(updater, "_open", return_value=_FakeResponse(payload)):
        path = updater.download(asset, tmp_path, lambda done, total: seen.append((done, total)))
    assert path.read_bytes() == payload
    assert seen[-1] == (5000, 5000)


def test_download_with_wrong_hash_is_rejected_and_removed(tmp_path):
    asset = Asset("f.bin", "https://example.test/f.bin", "00" * 32, 3)
    with patch.object(updater, "_open", return_value=_FakeResponse(b"abc")):
        with pytest.raises(UpdateError):
            updater.download(asset, tmp_path)
    assert not (tmp_path / "f.bin").exists()


# ----- light install


def _zip_with_exe(path: Path, content: bytes) -> Path:
    with zipfile.ZipFile(path, "w") as z:
        z.writestr("Dettato.exe", content)
    return path


def test_install_light_swaps_exe_and_keeps_old_for_cleanup(tmp_path):
    app = tmp_path / "app"
    app.mkdir()
    (app / "Dettato.exe").write_bytes(b"old")
    updater.install_light(_zip_with_exe(tmp_path / "u.zip", b"new"), app)
    assert (app / "Dettato.exe").read_bytes() == b"new"
    assert (app / "Dettato.old.exe").read_bytes() == b"old"

    updater.cleanup_old(app)
    assert not (app / "Dettato.old.exe").exists()
    assert (app / "Dettato.exe").read_bytes() == b"new"


def test_install_light_rejects_zip_without_exe_and_changes_nothing(tmp_path):
    app = tmp_path / "app"
    app.mkdir()
    (app / "Dettato.exe").write_bytes(b"old")
    bad = tmp_path / "bad.zip"
    with zipfile.ZipFile(bad, "w") as z:
        z.writestr("altro.txt", "x")
    with pytest.raises(UpdateError):
        updater.install_light(bad, app)
    assert (app / "Dettato.exe").read_bytes() == b"old"
    assert not (app / "Dettato.old.exe").exists()


def test_runtime_id_is_dev_from_source():
    assert updater.runtime_id() == "dev"
