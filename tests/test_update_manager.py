from pathlib import Path
import sys
APP=Path(__file__).resolve().parents[1]/"app"
sys.path.insert(0,str(APP))
import update_manager

def test_version_compare():
    assert update_manager.is_newer("3.1.0","3.0.1")
    assert not update_manager.is_newer("3.0.1","3.0.1")
    assert not update_manager.is_newer("3.0.0","3.0.1")

def test_update_url_namespace_guard():
    assert update_manager._allowed_update_url("https://github.com/Superior-MI-Labs/repo/releases/download/v/x.deb")
    assert not update_manager._allowed_update_url("https://example.com/x.deb")


def test_update_download_requires_checksum_and_allowed_namespace(tmp_path, monkeypatch):
    monkeypatch.setattr(update_manager, "DOWNLOADS", tmp_path)

    missing_hash = update_manager.UpdateInfo(
        available=True,
        current_version="3.0.3",
        latest_version="3.1.0",
        status="release",
        notes="",
        repo_url=update_manager.REPOSITORY_URL,
        deb_url="https://github.com/Superior-MI-Labs/repo/releases/download/v3.1.0/app.deb",
        deb_sha256="",
    )
    try:
        update_manager.download_update(missing_hash)
    except RuntimeError as exc:
        assert "SHA-256" in str(exc)
    else:
        raise AssertionError("update without checksum was accepted")

    foreign = update_manager.UpdateInfo(
        available=True,
        current_version="3.0.3",
        latest_version="3.1.0",
        status="release",
        notes="",
        repo_url=update_manager.REPOSITORY_URL,
        deb_url="https://example.com/app.deb",
        deb_sha256="0" * 64,
    )
    try:
        update_manager.download_update(foreign)
    except RuntimeError as exc:
        assert "outside" in str(exc)
    else:
        raise AssertionError("foreign update URL was accepted")


def test_update_download_verifies_hash_and_deletes_corrupt_file(tmp_path, monkeypatch):
    import hashlib

    payload = b"qualified-deb-payload"
    expected = hashlib.sha256(payload).hexdigest()

    class Response:
        headers = {"Content-Length": str(len(payload))}

        def __enter__(self):
            self._sent = False
            return self

        def __exit__(self, *args):
            return False

        def read(self, size=-1):
            if self._sent:
                return b""
            self._sent = True
            return payload

    monkeypatch.setattr(update_manager, "DOWNLOADS", tmp_path)
    monkeypatch.setattr(update_manager.urllib.request, "urlopen", lambda request, timeout=30: Response())

    info = update_manager.UpdateInfo(
        available=True,
        current_version="3.0.3",
        latest_version="3.1.0",
        status="release",
        notes="",
        repo_url=update_manager.REPOSITORY_URL,
        deb_url="https://github.com/Superior-MI-Labs/repo/releases/download/v3.1.0/app.deb",
        deb_sha256=expected,
    )
    target = update_manager.download_update(info)
    assert target.exists()
    assert target.read_bytes() == payload

    bad = update_manager.UpdateInfo(
        available=True,
        current_version="3.0.3",
        latest_version="3.1.1",
        status="release",
        notes="",
        repo_url=update_manager.REPOSITORY_URL,
        deb_url="https://github.com/Superior-MI-Labs/repo/releases/download/v3.1.1/app.deb",
        deb_sha256="f" * 64,
    )
    try:
        update_manager.download_update(bad)
    except RuntimeError as exc:
        assert "failed SHA-256 verification" in str(exc)
    else:
        raise AssertionError("corrupt update passed checksum verification")

    corrupt = tmp_path / "Superior-MI-Labs-ComfyUI-Workstation_3.1.1_all.deb"
    assert not corrupt.exists()
