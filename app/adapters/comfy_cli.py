from __future__ import annotations

import re
import subprocess
import urllib.parse
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Mapping

from .manager import ComfyManagerDiscovery


_PACKAGE_ID = re.compile(r"^[a-z0-9][a-z0-9._-]*$")


def _default_run(command: list[str]) -> str:
    result = subprocess.run(
        command,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        check=False,
    )
    if result.returncode != 0:
        raise RuntimeError(
            result.stdout.strip()
            or f"Command failed with exit code {result.returncode}: {command[0]}"
        )
    return result.stdout.strip()


def _validate_package_id(package_id: str) -> str:
    value = str(package_id)
    if not _PACKAGE_ID.fullmatch(value):
        raise ValueError(
            "Package ID must be a lowercase Comfy Registry identifier, not a URL or command fragment."
        )
    return value


class ComfyCliPackageService:
    """Install Manager/Registry-known node packages through comfy-cli.

    Package IDs must resolve through ComfyUI-Manager discovery first. The
    command is built from fixed argv elements; no shell is used.
    """

    def __init__(
        self,
        workspace: Path,
        discovery: ComfyManagerDiscovery,
        *,
        comfy_binary: str = "comfy",
        dependency_mode: str = "default",
        run_command: Callable[[list[str]], str] = _default_run,
    ):
        if dependency_mode not in {"default", "uv-compile"}:
            raise ValueError("dependency_mode must be 'default' or 'uv-compile'")
        self.workspace = Path(workspace)
        self.discovery = discovery
        self.comfy_binary = comfy_binary
        self.dependency_mode = dependency_mode
        self._run_command = run_command

    def install(self, package_id: str) -> str:
        package_id = _validate_package_id(package_id)
        self.discovery.require_package(package_id)

        command = [
            self.comfy_binary,
            "--skip-prompt",
            f"--workspace={self.workspace}",
            "node",
            "install",
            package_id,
            "--exit-on-fail",
        ]
        if self.dependency_mode == "uv-compile":
            command.append("--uv-compile")

        output = self._run_command(command)
        return output or f"Installed package {package_id}."


@dataclass(frozen=True)
class TrustedModelAsset:
    id: str
    url: str
    relative_path: str = ""


def _validate_asset(asset: TrustedModelAsset) -> None:
    parsed = urllib.parse.urlsplit(asset.url)
    if parsed.scheme != "https" or not parsed.netloc:
        raise ValueError(f"Asset {asset.id} must use an absolute HTTPS URL.")
    if parsed.username or parsed.password:
        raise ValueError(f"Asset {asset.id} URL must not contain embedded credentials.")

    if asset.relative_path:
        path = Path(asset.relative_path)
        if path.is_absolute() or ".." in path.parts:
            raise ValueError(f"Asset {asset.id} relative path escapes the ComfyUI model root.")


class ComfyCliAssetService:
    """Download only pre-registered trusted model assets through comfy-cli."""

    def __init__(
        self,
        workspace: Path,
        assets: Mapping[str, TrustedModelAsset],
        *,
        comfy_binary: str = "comfy",
        run_command: Callable[[list[str]], str] = _default_run,
    ):
        self.workspace = Path(workspace)
        self.assets = dict(assets)
        self.comfy_binary = comfy_binary
        self._run_command = run_command

        for key, asset in self.assets.items():
            if key != asset.id:
                raise ValueError("Trusted asset registry key must equal asset.id.")
            _validate_asset(asset)

    def download(self, asset_id: str) -> str:
        try:
            asset = self.assets[str(asset_id)]
        except KeyError as exc:
            raise KeyError(f"Unknown trusted asset ID: {asset_id}") from exc

        command = [
            self.comfy_binary,
            "--skip-prompt",
            f"--workspace={self.workspace}",
            "model",
            "download",
            "--url",
            asset.url,
        ]
        if asset.relative_path:
            command.extend(["--relative-path", asset.relative_path])

        output = self._run_command(command)
        return output or f"Downloaded asset {asset.id}."
