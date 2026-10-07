from __future__ import annotations

import json
from dataclasses import asdict
from typing import Any, Mapping, Protocol

from .contracts import (
    AssistantContext,
    AssistantProposal,
    CapabilityRequest,
    HardwareProfile,
    RuntimeProfile,
)
from .graph_controls import GraphControlRegistry
from .registry import CapabilityRegistry


class AssistantProvider(Protocol):
    def propose(self, user_text: str, context: Mapping[str, Any]) -> Mapping[str, Any]: ...


_ALLOWED_QUALITY_PRIORITIES = {"balanced", "quality", "speed", "storage"}


def _json_data(value: Any) -> Any:
    """Require provider-facing context/proposals to be ordinary JSON data."""
    try:
        return json.loads(json.dumps(value, sort_keys=True, ensure_ascii=True))
    except (TypeError, ValueError) as exc:
        raise ValueError("Assistant data must be JSON-serializable.") from exc


def build_assistant_context(
    capabilities: CapabilityRegistry,
    controls: GraphControlRegistry | None = None,
    hardware: HardwareProfile | None = None,
    runtime: RuntimeProfile | None = None,
) -> AssistantContext:
    hardware_summary: dict[str, Any] = {}
    if hardware is not None:
        hardware_summary = {
            "platform": hardware.platform,
            "architecture": hardware.architecture,
            "memory_total_bytes": hardware.memory_total_bytes,
            "gpus": [
                {
                    "vendor": gpu.vendor,
                    "model": gpu.model,
                    "vram_bytes": gpu.vram_bytes,
                    "backend_candidates": list(gpu.backend_candidates),
                }
                for gpu in hardware.gpus
            ],
            "storage": [
                {
                    "path": storage.path,
                    "free_bytes": storage.free_bytes,
                }
                for storage in hardware.storage
            ],
        }

    runtime_summary: dict[str, Any] = {}
    if runtime is not None:
        runtime_summary = {
            "compute_backend": runtime.compute_backend,
            "backend_version": runtime.backend_version,
            "comfyui_version": runtime.comfyui_version,
            "installed_node_types": sorted(runtime.installed_node_types),
            "installed_packages": list(runtime.installed_packages),
        }

    return AssistantContext(
        capability_ids=tuple(sorted(capabilities.by_id())),
        graph_controls=tuple(controls.controls if controls is not None else ()),
        hardware_summary=_json_data(hardware_summary),
        runtime_summary=_json_data(runtime_summary),
    )


def context_payload(context: AssistantContext) -> dict[str, Any]:
    controls = []
    for control in context.graph_controls:
        controls.append({
            "id": control.id,
            "label": control.label,
            "data_type": control.data_type,
            "value": _json_data(control.value),
            "minimum": control.minimum,
            "maximum": control.maximum,
            "choices": list(control.choices),
            "editable": control.editable,
            "priority": control.priority,
        })
    return {
        "capability_ids": list(context.capability_ids),
        "graph_controls": controls,
        "hardware": _json_data(context.hardware_summary),
        "runtime": _json_data(context.runtime_summary),
    }


def _require_keys(payload: Mapping[str, Any], allowed: set[str], required: set[str]) -> None:
    keys = set(payload)
    missing = required - keys
    extra = keys - allowed
    if missing:
        raise ValueError(f"Assistant proposal is missing required keys: {sorted(missing)}")
    if extra:
        raise ValueError(f"Assistant proposal has unsupported keys: {sorted(extra)}")


def _preferences(value: Any) -> Mapping[str, Any]:
    if value is None:
        return {}
    if not isinstance(value, Mapping):
        raise ValueError("Assistant preferences must be an object.")
    clean: dict[str, Any] = {}
    for raw_key, raw_value in value.items():
        key = str(raw_key)
        if len(key) > 80:
            raise ValueError("Assistant preference key is too long.")
        if not isinstance(raw_value, (str, int, float, bool)) and raw_value is not None:
            raise ValueError("Assistant preference values must be scalar JSON values.")
        clean[key] = raw_value
    return clean


def validate_assistant_proposal(
    raw: Mapping[str, Any],
    context: AssistantContext,
) -> AssistantProposal:
    if not isinstance(raw, Mapping):
        raise ValueError("Assistant provider must return a JSON object.")

    kind = raw.get("kind")
    if kind == "capability_request":
        _require_keys(
            raw,
            {
                "kind",
                "capabilities",
                "local_only",
                "quality_priority",
                "storage_budget_bytes",
                "preferences",
                "message",
            },
            {"kind", "capabilities"},
        )
        capabilities = raw.get("capabilities")
        if not isinstance(capabilities, list) or not capabilities:
            raise ValueError("capabilities must be a non-empty list.")
        capability_ids = tuple(str(value) for value in capabilities)
        if len(capability_ids) != len(set(capability_ids)):
            raise ValueError("capabilities must not contain duplicates.")
        unknown = sorted(set(capability_ids) - set(context.capability_ids))
        if unknown:
            raise ValueError(f"Assistant proposed unknown capabilities: {unknown}")

        local_only = raw.get("local_only", True)
        if not isinstance(local_only, bool):
            raise ValueError("local_only must be boolean.")

        quality_priority = str(raw.get("quality_priority", "balanced"))
        if quality_priority not in _ALLOWED_QUALITY_PRIORITIES:
            raise ValueError(
                f"quality_priority must be one of {sorted(_ALLOWED_QUALITY_PRIORITIES)}"
            )

        storage_budget = raw.get("storage_budget_bytes")
        if storage_budget is not None:
            if isinstance(storage_budget, bool) or not isinstance(storage_budget, int) or storage_budget < 0:
                raise ValueError("storage_budget_bytes must be a non-negative integer or null.")

        return AssistantProposal(
            kind=kind,
            capability_request=CapabilityRequest(
                capabilities=capability_ids,
                local_only=local_only,
                quality_priority=quality_priority,
                storage_budget_bytes=storage_budget,
                preferences=_preferences(raw.get("preferences")),
            ),
            message=str(raw.get("message", "")),
        )

    if kind == "graph_changes":
        _require_keys(raw, {"kind", "changes", "message"}, {"kind", "changes"})
        changes = raw.get("changes")
        if not isinstance(changes, Mapping) or not changes:
            raise ValueError("changes must be a non-empty object.")

        by_id = {control.id: control for control in context.graph_controls}
        unknown = sorted(set(str(key) for key in changes) - set(by_id))
        if unknown:
            raise ValueError(f"Assistant proposed unknown graph controls: {unknown}")

        clean: dict[str, Any] = {}
        for raw_id, value in changes.items():
            control_id = str(raw_id)
            control = by_id[control_id]
            if not control.editable:
                raise ValueError(f"Assistant proposed non-editable graph control: {control_id}")
            GraphControlRegistry.validate_value(control, value)
            clean[control_id] = _json_data(value)

        return AssistantProposal(
            kind=kind,
            graph_changes=clean,
            message=str(raw.get("message", "")),
        )

    if kind in {"clarify", "message"}:
        _require_keys(raw, {"kind", "message"}, {"kind", "message"})
        message = raw.get("message")
        if not isinstance(message, str) or not message.strip():
            raise ValueError("Assistant message must be a non-empty string.")
        return AssistantProposal(kind=kind, message=message.strip())

    raise ValueError(f"Unsupported assistant proposal kind: {kind!r}")


class AssistantService:
    """Constrained intent/proposal layer.

    This service has no executor, subprocess, package, download, or workflow
    mutation methods. It validates provider output into typed Core proposals.
    """

    def __init__(self, provider: AssistantProvider | None):
        self.provider = provider

    @property
    def available(self) -> bool:
        return self.provider is not None

    def propose(self, user_text: str, context: AssistantContext) -> AssistantProposal:
        text = str(user_text).strip()
        if not text:
            raise ValueError("User text must not be empty.")
        if self.provider is None:
            return AssistantProposal(
                kind="message",
                message="Assistant provider is not configured. Core Create, Studio, and planning remain available.",
            )

        raw = self.provider.propose(text, context_payload(context))
        return validate_assistant_proposal(raw, context)
