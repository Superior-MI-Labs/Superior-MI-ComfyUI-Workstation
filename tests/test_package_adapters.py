from pathlib import Path
import sys

APP = Path(__file__).resolve().parents[1] / "app"
sys.path.insert(0, str(APP))

from adapters.comfy_cli import (
    ComfyCliAssetService,
    ComfyCliPackageService,
    TrustedModelAsset,
)
from adapters.manager import ComfyManagerDiscovery


def test_manager_discovery_requires_registry_known_package():
    seen = []

    def fake_get(url, timeout):
        seen.append(url)
        return {
            "channel": "default",
            "node_packs": {
                "comfyui-example": {
                    "id": "comfyui-example",
                    "title": "Example",
                }
            },
        }

    discovery = ComfyManagerDiscovery("http://127.0.0.1:8188", get_json=fake_get)
    row = discovery.require_package("comfyui-example")
    assert row["id"] == "comfyui-example"
    assert "/customnode/getlist" in seen[0]
    assert "skip_update=true" in seen[0]

    try:
        discovery.require_package("missing")
    except KeyError as exc:
        assert "missing" in str(exc)
    else:
        raise AssertionError("unknown package was accepted")


def test_package_service_builds_fixed_argv_and_does_not_use_shell():
    commands = []

    class Discovery:
        def require_package(self, package_id):
            assert package_id == "comfyui-example"
            return {"id": package_id}

    service = ComfyCliPackageService(
        Path("/srv/ComfyUI"),
        Discovery(),
        comfy_binary="/usr/bin/comfy",
        dependency_mode="uv-compile",
        run_command=lambda command: commands.append(command) or "ok",
    )
    assert service.install("comfyui-example") == "ok"
    assert commands == [[
        "/usr/bin/comfy",
        "--workspace=/srv/ComfyUI",
        "node",
        "install",
        "comfyui-example",
        "--exit-on-fail",
        "--uv-compile",
    ]]


def test_package_service_rejects_command_fragments_before_discovery():
    called = []

    class Discovery:
        def require_package(self, package_id):
            called.append(package_id)
            return {}

    service = ComfyCliPackageService(
        Path("/srv/ComfyUI"),
        Discovery(),
        run_command=lambda command: "should not run",
    )
    for bad in ("--help", "https://example.com/repo", "node;rm", "UPPERCASE"):
        try:
            service.install(bad)
        except ValueError:
            pass
        else:
            raise AssertionError(f"unsafe package id accepted: {bad}")
    assert called == []


def test_package_service_refuses_registry_unknown_id():
    commands = []

    class Discovery:
        def require_package(self, package_id):
            raise KeyError(package_id)

    service = ComfyCliPackageService(
        Path("/srv/ComfyUI"),
        Discovery(),
        run_command=lambda command: commands.append(command) or "bad",
    )
    try:
        service.install("comfyui-unknown")
    except KeyError:
        pass
    else:
        raise AssertionError("unknown package reached comfy-cli")
    assert commands == []


def test_asset_service_downloads_only_pre_registered_asset():
    commands = []
    asset = TrustedModelAsset(
        id="model.example",
        url="https://huggingface.co/example/repo/resolve/main/model.safetensors",
        relative_path="diffusion_models",
    )
    service = ComfyCliAssetService(
        Path("/srv/ComfyUI"),
        {"model.example": asset},
        comfy_binary="/usr/bin/comfy",
        run_command=lambda command: commands.append(command) or "ok",
    )

    assert service.download("model.example") == "ok"
    assert commands == [[
        "/usr/bin/comfy",
        "--workspace=/srv/ComfyUI",
        "model",
        "download",
        "--url",
        asset.url,
        "--relative-path",
        "diffusion_models",
    ]]

    try:
        service.download("model.not-registered")
    except KeyError:
        pass
    else:
        raise AssertionError("unregistered model asset was accepted")
    assert len(commands) == 1


def test_asset_registry_rejects_unsafe_url_and_path():
    bad_assets = (
        TrustedModelAsset(id="http", url="http://example.com/model.bin"),
        TrustedModelAsset(id="credentials", url="https://user:pass@example.com/model.bin"),
        TrustedModelAsset(
            id="escape",
            url="https://example.com/model.bin",
            relative_path="../outside",
        ),
    )
    for asset in bad_assets:
        try:
            ComfyCliAssetService(Path("/srv/ComfyUI"), {asset.id: asset})
        except ValueError:
            pass
        else:
            raise AssertionError(f"unsafe asset registry entry accepted: {asset.id}")
