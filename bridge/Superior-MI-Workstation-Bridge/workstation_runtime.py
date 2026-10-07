from __future__ import annotations

import json
import sys
import urllib.parse
from dataclasses import asdict
from pathlib import Path
from typing import Any, Mapping

HERE = Path(__file__).resolve().parent
CONFIG_PATH = HERE / "_workstation.json"


def load_bridge_config() -> dict[str, Any]:
    try:
        payload = json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    return payload if isinstance(payload, dict) else {}


def _core_modules():
    config = load_bridge_config()
    app_path = Path(str(config.get("app_path") or ""))
    if not app_path.is_dir():
        raise RuntimeError(
            "Superior MI Workstation Core is unavailable. Re-run the desktop launcher to refresh the bridge."
        )
    app_value = str(app_path)
    if app_value not in sys.path:
        sys.path.insert(0, app_value)

    from adapters.assistant import OpenAICompatibleAssistantProvider
    from adapters.comfy_cli import load_trusted_asset_registry
    from core.assistant import AssistantService, build_assistant_context
    from core.contracts import CapabilityRequest, GraphControl, InstalledInventory
    from core.executor import fingerprint_plan
    from core.graph_controls import GraphControlRegistry
    from core.hardware import observe_hardware
    from core.registry import load_capability_registry, load_implementation_registry
    from core.resolver import resolve_capabilities
    from core.runtime_profile import observe_runtime

    return {
        "config": config,
        "OpenAICompatibleAssistantProvider": OpenAICompatibleAssistantProvider,
        "load_trusted_asset_registry": load_trusted_asset_registry,
        "AssistantService": AssistantService,
        "build_assistant_context": build_assistant_context,
        "CapabilityRequest": CapabilityRequest,
        "GraphControl": GraphControl,
        "GraphControlRegistry": GraphControlRegistry,
        "InstalledInventory": InstalledInventory,
        "fingerprint_plan": fingerprint_plan,
        "observe_hardware": observe_hardware,
        "load_capability_registry": load_capability_registry,
        "load_implementation_registry": load_implementation_registry,
        "resolve_capabilities": resolve_capabilities,
        "observe_runtime": observe_runtime,
    }


def core_status() -> dict[str, Any]:
    try:
        modules = _core_modules()
        config = modules["config"]
        catalog_root = Path(str(config.get("catalog_root") or ""))
        capabilities = modules["load_capability_registry"](catalog_root / "capabilities.json")
        entries = sorted(capabilities.entries, key=lambda entry: entry.id)
        return {
            "ok": True,
            "core_available": True,
            "capability_ids": [entry.id for entry in entries],
            "capabilities": [
                {"id": entry.id, "title": entry.title, "description": entry.description}
                for entry in entries
            ],
        }
    except Exception as exc:
        return {
            "ok": False,
            "core_available": False,
            "error": str(exc),
            "capability_ids": [],
        }


def _bounded_string(value: Any, *, name: str, maximum: int, required: bool = False) -> str:
    result = str(value or "").strip()
    if required and not result:
        raise ValueError(f"{name} is required.")
    if len(result) > maximum:
        raise ValueError(f"{name} is too long.")
    return result


def _graph_registry(rows: Any, modules: Mapping[str, Any]):
    if rows is None:
        rows = []
    if not isinstance(rows, list) or len(rows) > 500:
        raise ValueError("graph_controls must be a list with at most 500 entries.")

    GraphControl = modules["GraphControl"]
    controls = []
    for row in rows:
        if not isinstance(row, Mapping):
            raise ValueError("graph_controls entries must be objects.")
        choices = row.get("choices") or []
        if not isinstance(choices, list) or len(choices) > 500:
            raise ValueError("graph control choices must be a bounded list.")
        controls.append(
            GraphControl(
                id=_bounded_string(row.get("id"), name="control id", maximum=200, required=True),
                node_id=_bounded_string(row.get("nodeId"), name="node id", maximum=100, required=True),
                node_type=_bounded_string(row.get("nodeType"), name="node type", maximum=200),
                input_name=_bounded_string(row.get("inputName"), name="input name", maximum=200, required=True),
                data_type=_bounded_string(row.get("dataType"), name="data type", maximum=50) or "*",
                value=row.get("value"),
                widget=_bounded_string(row.get("widget"), name="widget", maximum=50) or "unsupported",
                label=_bounded_string(row.get("label"), name="label", maximum=200),
                group=_bounded_string(row.get("group"), name="group", maximum=100) or "Advanced",
                minimum=row.get("minimum"),
                maximum=row.get("maximum"),
                step=row.get("step"),
                choices=tuple(choices),
                editable=bool(row.get("editable", False)),
                priority=_bounded_string(row.get("priority"), name="priority", maximum=50) or "advanced",
            )
        )
    return modules["GraphControlRegistry"](tuple(controls))


def _installed_inventory(config: Mapping[str, Any], asset_registry: Mapping[str, Any], modules):
    comfy_root = Path(str(config.get("comfy_root") or ""))
    models_root = comfy_root / "models"
    installed = set()

    for asset_id, asset in asset_registry.items():
        parsed = urllib.parse.urlsplit(asset.url)
        filename = Path(urllib.parse.unquote(parsed.path)).name
        if not filename:
            continue
        target = models_root
        if asset.relative_path:
            target = target / asset.relative_path
        if (target / filename).exists():
            installed.add(asset_id)

    return modules["InstalledInventory"](asset_ids=frozenset(installed))


def _assistant_provider(payload: Mapping[str, Any], modules):
    settings = payload.get("assistant") or {}
    if not isinstance(settings, Mapping):
        raise ValueError("assistant settings must be an object.")

    base_url = _bounded_string(settings.get("base_url"), name="assistant base_url", maximum=500)
    model = _bounded_string(settings.get("model"), name="assistant model", maximum=200)
    api_key = _bounded_string(settings.get("api_key"), name="assistant api_key", maximum=4096)

    if not base_url and not model:
        return None
    if not base_url or not model:
        raise ValueError("Both assistant base_url and model are required.")

    return modules["OpenAICompatibleAssistantProvider"](
        base_url=base_url,
        model=model,
        api_key=api_key,
    )


def _planning_state(payload: Mapping[str, Any], modules):
    config = modules["config"]
    catalog_root = Path(str(config.get("catalog_root") or ""))

    capabilities = modules["load_capability_registry"](catalog_root / "capabilities.json")
    implementations = modules["load_implementation_registry"](catalog_root / "implementations.json")
    trusted_assets = modules["load_trusted_asset_registry"](catalog_root / "assets.json")

    comfy_root = Path(str(config.get("comfy_root") or ""))
    hardware = modules["observe_hardware"](storage_paths=(comfy_root / "models",))
    runtime = modules["observe_runtime"](
        comfyui_url=_bounded_string(payload.get("comfyui_url"), name="comfyui_url", maximum=500),
    )
    inventory = _installed_inventory(config, trusted_assets, modules)
    return capabilities, implementations, hardware, runtime, inventory


def _resolution_payload(resolution, modules) -> dict[str, Any]:
    result = asdict(resolution)
    if resolution.plan is not None:
        result["plan_fingerprint"] = modules["fingerprint_plan"](resolution.plan)
    return result


def plan(payload: Mapping[str, Any]) -> dict[str, Any]:
    if not isinstance(payload, Mapping):
        raise ValueError("Request body must be an object.")

    raw_capabilities = payload.get("capabilities")
    if not isinstance(raw_capabilities, list) or not raw_capabilities:
        raise ValueError("capabilities must be a non-empty list.")

    capability_ids = tuple(str(value) for value in raw_capabilities)
    if len(capability_ids) != len(set(capability_ids)):
        raise ValueError("capabilities must not contain duplicates.")

    quality = _bounded_string(payload.get("quality_priority") or "balanced", name="quality_priority", maximum=20)
    if quality not in {"balanced", "quality", "speed", "storage"}:
        raise ValueError("Unsupported quality_priority.")

    local_only = payload.get("local_only", True)
    if not isinstance(local_only, bool):
        raise ValueError("local_only must be boolean.")

    storage_budget = payload.get("storage_budget_bytes")
    if storage_budget is not None:
        if isinstance(storage_budget, bool) or not isinstance(storage_budget, int) or storage_budget < 0:
            raise ValueError("storage_budget_bytes must be a non-negative integer or null.")

    modules = _core_modules()
    capabilities, implementations, hardware, runtime, inventory = _planning_state(payload, modules)
    known = set(capabilities.by_id())
    unknown = sorted(set(capability_ids) - known)
    if unknown:
        raise ValueError(f"Unknown capabilities: {unknown}")

    request = modules["CapabilityRequest"](
        capabilities=capability_ids,
        local_only=local_only,
        quality_priority=quality,
        storage_budget_bytes=storage_budget,
    )
    resolution = modules["resolve_capabilities"](
        request,
        hardware,
        runtime,
        inventory,
        implementations.entries,
    )
    return {
        "ok": True,
        "capability_request": asdict(request),
        "resolution": _resolution_payload(resolution, modules),
        "hardware": asdict(hardware),
        "runtime": asdict(runtime),
    }


def propose(payload: Mapping[str, Any]) -> dict[str, Any]:
    if not isinstance(payload, Mapping):
        raise ValueError("Request body must be an object.")

    user_text = _bounded_string(
        payload.get("text"),
        name="text",
        maximum=8000,
        required=True,
    )

    modules = _core_modules()
    capabilities, implementations, hardware, runtime, inventory = _planning_state(payload, modules)
    controls = _graph_registry(payload.get("graph_controls"), modules)

    context = modules["build_assistant_context"](
        capabilities,
        controls,
        hardware,
        runtime,
    )
    proposal = modules["AssistantService"](
        _assistant_provider(payload, modules)
    ).propose(user_text, context)

    response: dict[str, Any] = {
        "ok": True,
        "proposal": asdict(proposal),
        "hardware": asdict(hardware),
        "runtime": asdict(runtime),
    }

    if proposal.kind == "capability_request" and proposal.capability_request is not None:
        resolution = modules["resolve_capabilities"](
            proposal.capability_request,
            hardware,
            runtime,
            inventory,
            implementations.entries,
        )
        response["resolution"] = _resolution_payload(resolution, modules)

    return response
