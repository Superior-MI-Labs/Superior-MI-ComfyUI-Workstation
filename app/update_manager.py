from __future__ import annotations

import hashlib
import json
import os
import re
import shutil
import subprocess
import urllib.error
import urllib.request
from dataclasses import dataclass
from pathlib import Path

CURRENT_VERSION = "3.0.3"
REPOSITORY = "Superior-MI-Labs/Superior-MI-ComfyUI-Workstation"
REPOSITORY_URL = "https://github.com/Superior-MI-Labs/Superior-MI-ComfyUI-Workstation"
MANIFEST_URL = "https://raw.githubusercontent.com/Superior-MI-Labs/Superior-MI-ComfyUI-Workstation/main/update.json"

HOME = Path.home()
APP_ROOT = Path(__file__).resolve().parent.parent
DOWNLOADS = HOME / "Downloads"

@dataclass(frozen=True)
class UpdateInfo:
    available: bool
    current_version: str
    latest_version: str
    status: str
    notes: str
    repo_url: str
    deb_url: str = ""
    zip_url: str = ""
    source_url: str = ""
    deb_sha256: str = ""
    zip_sha256: str = ""
    channel: str = "development"

def _version_tuple(value: str):
    # Numeric comparison only. Suffixes do not make a development build appear
    # newer than the corresponding numeric version.
    nums = [int(x) for x in re.findall(r"\d+", str(value))[:4]]
    return tuple(nums + [0] * (4 - len(nums)))

def is_newer(latest: str, current: str = CURRENT_VERSION) -> bool:
    return _version_tuple(latest) > _version_tuple(current)

def fetch_manifest(timeout: float = 6.0) -> dict:
    req = urllib.request.Request(
        MANIFEST_URL,
        headers={"User-Agent": "Superior-MI-Labs-ComfyUI-Workstation/3.0.1"},
    )
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            data = json.loads(r.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        if exc.code == 404:
            raise RuntimeError(
                "The Superior MI development update repository has not been published yet."
            ) from exc
        raise RuntimeError(f"GitHub update check failed: HTTP {exc.code}") from exc
    except Exception as exc:
        raise RuntimeError(f"Could not reach the update service: {exc}") from exc
    if not isinstance(data, dict) or not data.get("version"):
        raise RuntimeError("The update manifest is invalid.")
    return data

def check_for_updates() -> UpdateInfo:
    m = fetch_manifest()
    latest = str(m.get("version", CURRENT_VERSION))
    hashes = m.get("sha256") or {}
    return UpdateInfo(
        available=is_newer(latest),
        current_version=CURRENT_VERSION,
        latest_version=latest,
        status=str(m.get("status", "development")),
        notes=str(m.get("notes", "")),
        repo_url=str(m.get("repo_url", REPOSITORY_URL)),
        deb_url=str(m.get("deb_url", "")),
        zip_url=str(m.get("zip_url", "")),
        source_url=str(m.get("source_url", REPOSITORY_URL + "/archive/refs/heads/main.zip")),
        deb_sha256=str(hashes.get("deb", "")),
        zip_sha256=str(hashes.get("zip", "")),
        channel=str(m.get("channel", "development")),
    )

def _allowed_update_url(url: str) -> bool:
    return (
        url.startswith("https://github.com/Superior-MI-Labs/")
        or url.startswith("https://objects.githubusercontent.com/")
        or url.startswith("https://raw.githubusercontent.com/Superior-MI-Labs/")
    )

def download_update(info: UpdateInfo, progress=None) -> Path:
    url = info.deb_url
    expected = info.deb_sha256.strip().lower()
    if not url:
        raise RuntimeError("This update does not publish a Debian package yet.")
    if not _allowed_update_url(url):
        raise RuntimeError("Refusing an update URL outside the Superior-MI-Labs GitHub namespace.")
    if not expected:
        raise RuntimeError("Refusing an update without a published SHA-256 checksum.")

    DOWNLOADS.mkdir(parents=True, exist_ok=True)
    target = DOWNLOADS / f"Superior-MI-Labs-ComfyUI-Workstation_{info.latest_version}_all.deb"
    req = urllib.request.Request(url, headers={"User-Agent": "Superior-MI-Labs-ComfyUI-Workstation"})
    with urllib.request.urlopen(req, timeout=30) as r, target.open("wb") as f:
        total = int(r.headers.get("Content-Length") or 0)
        done = 0
        while True:
            block = r.read(1024 * 1024)
            if not block:
                break
            f.write(block)
            done += len(block)
            if progress:
                progress(done, total)
    actual = hashlib.sha256(target.read_bytes()).hexdigest()
    if actual != expected:
        target.unlink(missing_ok=True)
        raise RuntimeError(
            f"Downloaded update failed SHA-256 verification. Expected {expected}, got {actual}."
        )
    return target

def install_deb(path: Path):
    if not path.exists():
        raise FileNotFoundError(path)
    helper = shutil.which("pkexec")
    if not helper:
        raise RuntimeError("pkexec is unavailable. Install the downloaded .deb through your package manager.")
    subprocess.Popen([helper, "apt", "install", "-y", str(path)], start_new_session=True)

DEV_CHECKOUT = HOME / "Projects" / "Superior-MI-ComfyUI-Workstation-Development"

def source_checkout_root() -> Path | None:
    if (APP_ROOT / ".git").exists():
        return APP_ROOT
    if (DEV_CHECKOUT / ".git").exists():
        return DEV_CHECKOUT
    return None

def source_pull_available() -> bool:
    return shutil.which("git") is not None

def sync_development_source(progress=None) -> Path:
    if not shutil.which("git"):
        raise RuntimeError("git is not installed.")
    target = source_checkout_root()
    if target is None:
        DEV_CHECKOUT.parent.mkdir(parents=True, exist_ok=True)
        if progress:
            progress("Cloning development repository…")
        subprocess.run(
            ["git", "clone", "--ff-only" if False else "--depth", "1", REPOSITORY_URL + ".git", str(DEV_CHECKOUT)],
            check=True,
        )
        return DEV_CHECKOUT

    origin = subprocess.run(
        ["git", "remote", "get-url", "origin"],
        cwd=target, text=True, capture_output=True, check=True,
    ).stdout.strip()
    allowed = {
        REPOSITORY_URL,
        REPOSITORY_URL + ".git",
        "git@github.com:" + REPOSITORY + ".git",
    }
    if origin not in allowed:
        raise RuntimeError(f"Refusing to update a checkout with unexpected origin: {origin}")

    dirty = subprocess.run(
        ["git", "status", "--porcelain"],
        cwd=target, text=True, capture_output=True, check=True,
    ).stdout.strip()
    if dirty:
        raise RuntimeError("Development checkout has local modifications. Update was not pulled.")

    if progress:
        progress("Fetching development repository…")
    subprocess.run(["git", "fetch", "origin"], cwd=target, check=True)
    if progress:
        progress("Fast-forwarding development checkout…")
    subprocess.run(["git", "pull", "--ff-only"], cwd=target, check=True)
    return target

def pull_source_update():
    return sync_development_source()
