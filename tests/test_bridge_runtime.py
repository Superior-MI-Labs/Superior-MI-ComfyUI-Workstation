from pathlib import Path
import importlib.util
import json
import sys

ROOT = Path(__file__).resolve().parents[1]
APP = ROOT / "app"
sys.path.insert(0, str(APP))

import comfy_integration


BRIDGE_RUNTIME = (
    ROOT
    / "bridge"
    / "Superior-MI-Workstation-Bridge"
    / "workstation_runtime.py"
)


def load_runtime_module():
    spec = importlib.util.spec_from_file_location("smi_bridge_runtime_test", BRIDGE_RUNTIME)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def write_config(tmp_path):
    comfy = tmp_path / "ComfyUI"
    (comfy / "models").mkdir(parents=True)
    config = tmp_path / "_workstation.json"
    config.write_text(
        json.dumps(
            {
                "schema_version": 1,
                "app_path": str(APP),
                "catalog_root": str(ROOT / "catalog" / "r1"),
                "preset_index": str(ROOT / "preset_library" / "index.json"),
                "comfy_root": str(comfy),
            }
        ),
        encoding="utf-8",
    )
    return config


def test_bridge_core_status_loads_single_workstation_core(tmp_path):
    runtime = load_runtime_module()
    runtime.CONFIG_PATH = write_config(tmp_path)

    status = runtime.core_status()

    assert status["ok"] is True
    assert status["core_available"] is True
    assert "image.generate" in status["capability_ids"]
    titles = {row["id"]: row["title"] for row in status["capabilities"]}
    assert titles["image.generate"] == "Generate Image"


def test_bridge_provider_free_plan_uses_r1_registry(tmp_path):
    runtime = load_runtime_module()
    runtime.CONFIG_PATH = write_config(tmp_path)

    result = runtime.plan(
        {
            "capabilities": ["image.generate"],
            "quality_priority": "balanced",
            "local_only": True,
            "comfyui_url": "http://127.0.0.1:8188",
        }
    )

    assert result["ok"] is True
    assert result["capability_request"]["capabilities"] == ("image.generate",)
    assert result["resolution"]["requested_capabilities"] == ("image.generate",)
    assert result["resolution"]["assessments"]
    # CI may be CPU-only; the important invariant is an honest typed result,
    # not pretending a CUDA candidate is available.
    if result["resolution"]["plan"] is None:
        assert result["resolution"]["unresolved_capabilities"] == ("image.generate",)


def test_bridge_assistant_off_is_a_supported_state(tmp_path):
    runtime = load_runtime_module()
    runtime.CONFIG_PATH = write_config(tmp_path)

    result = runtime.propose(
        {
            "text": "Help me make an image.",
            "assistant": {},
            "graph_controls": [],
            "comfyui_url": "http://127.0.0.1:8188",
        }
    )

    assert result["ok"] is True
    assert result["proposal"]["kind"] == "message"
    assert "not configured" in result["proposal"]["message"]


def test_bridge_install_writes_runtime_discovery_manifest(tmp_path, monkeypatch):
    source = tmp_path / "bridge-source"
    (source / "web" / "js").mkdir(parents=True)
    (source / "__init__.py").write_text("# bridge\n", encoding="utf-8")
    (source / "web" / "js" / "superior-mi-workstation.js").write_text("// js\n", encoding="utf-8")

    app_root = tmp_path / "workstation"
    (app_root / "app").mkdir(parents=True)
    (app_root / "catalog" / "r1").mkdir(parents=True)
    (app_root / "preset_library").mkdir(parents=True)

    comfy = tmp_path / "ComfyUI"
    comfy.mkdir()
    destination = comfy / "custom_nodes" / "Superior-MI-Workstation-Bridge"

    monkeypatch.setattr(comfy_integration, "APP_ROOT", app_root)
    monkeypatch.setattr(comfy_integration, "COMFY", comfy)
    monkeypatch.setattr(comfy_integration, "BRIDGE_SOURCE", source)
    monkeypatch.setattr(comfy_integration, "BRIDGE_DEST", destination)

    ok, _message = comfy_integration.ensure_bridge()
    assert ok is True

    payload = json.loads((destination / "_workstation.json").read_text(encoding="utf-8"))
    assert payload["app_path"] == str(app_root / "app")
    assert payload["catalog_root"] == str(app_root / "catalog" / "r1")
    assert payload["preset_index"] == str(app_root / "preset_library" / "index.json")
    assert payload["comfy_root"] == str(comfy)
