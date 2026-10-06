from __future__ import annotations

import copy
from dataclasses import dataclass
from typing import Any, Mapping

from .contracts import GraphControl


def _humanize(name: str) -> str:
    return " ".join(part.capitalize() for part in str(name).replace("-", "_").split("_") if part)


def _schema_sections(info: Mapping[str, Any]):
    inputs = info.get("input", {}) if isinstance(info, Mapping) else {}
    for section in ("required", "optional"):
        raw = inputs.get(section, {}) or {}
        if isinstance(raw, Mapping):
            yield section, raw


def _autogrow_aliases(info: Mapping[str, Any]) -> dict[str, tuple[str, Any]]:
    aliases: dict[str, tuple[str, Any]] = {}
    for section, raw in _schema_sections(info):
        for root, spec in raw.items():
            if not isinstance(spec, (list, tuple)) or not spec:
                continue
            io_type = str(spec[0])
            meta = spec[1] if len(spec) > 1 and isinstance(spec[1], Mapping) else {}
            if "AUTOGROW" not in io_type.upper():
                continue
            template = meta.get("template") or {}
            names = template.get("names")
            child_spec = (template.get("input") or {}).get("required", {}).get("image")
            if isinstance(names, list):
                for child in names:
                    aliases[f"{root}.{child}"] = (section, child_spec or ["IMAGE", {}])
    return aliases


def _schema_for_input(info: Mapping[str, Any], input_name: str):
    for section, raw in _schema_sections(info):
        if input_name in raw:
            return section, raw[input_name]
    return _autogrow_aliases(info).get(input_name, (None, None))


def _is_connection(value: Any, prompt: Mapping[str, Any]) -> bool:
    return (
        isinstance(value, list)
        and len(value) == 2
        and str(value[0]) in {str(key) for key in prompt}
        and isinstance(value[1], int)
    )


def _decode_spec(spec: Any) -> tuple[str, dict[str, Any], tuple[Any, ...]]:
    if not isinstance(spec, (list, tuple)) or not spec:
        return "*", {}, ()
    head = spec[0]
    meta = spec[1] if len(spec) > 1 and isinstance(spec[1], Mapping) else {}
    if isinstance(head, list):
        return "COMBO", dict(meta), tuple(head)
    return str(head), dict(meta), ()


def _group_for(name: str, data_type: str) -> tuple[str, str]:
    n = name.lower()
    if "prompt" in n:
        return "Prompt", "primary"
    if n in {"width", "height", "resolution", "aspect_ratio", "aspect"}:
        return "Resolution", "primary"
    if any(token in n for token in ("steps", "cfg", "guidance", "sampler", "scheduler", "denoise", "seed")):
        return "Sampling", "primary" if n in {"steps", "seed"} else "advanced"
    if any(token in n for token in ("model", "checkpoint", "vae", "clip", "lora")):
        return "Model", "advanced"
    if any(token in n for token in ("filename", "output", "format", "compression")):
        return "Output", "advanced"
    if data_type in {"IMAGE", "VIDEO", "AUDIO"}:
        return "Inputs", "primary"
    return "Advanced", "advanced"


def _widget_for(data_type: str, meta: Mapping[str, Any], choices: tuple[Any, ...]) -> str:
    if choices:
        return "dropdown"
    upper = data_type.upper()
    if upper in {"BOOLEAN", "BOOL"}:
        return "toggle"
    if upper in {"INT", "FLOAT", "NUMBER"}:
        if "min" in meta and "max" in meta:
            return "slider-number"
        return "number"
    if upper == "STRING":
        return "multiline" if meta.get("multiline") else "text"
    if upper in {"IMAGE", "VIDEO", "AUDIO"}:
        return "file"
    return "text"


def _apply_presentation(control: GraphControl, presentation: Mapping[str, Any] | None) -> GraphControl:
    if not presentation:
        return control
    override = presentation.get(control.id)
    if not isinstance(override, Mapping):
        return control
    data = control.__dict__.copy()
    for key in ("label", "group", "priority"):
        if key in override:
            data[key] = str(override[key])
    if override.get("hidden") is True:
        data["priority"] = "hidden"
    return GraphControl(**data)


@dataclass(frozen=True)
class GraphControlRegistry:
    controls: tuple[GraphControl, ...]

    def by_id(self) -> dict[str, GraphControl]:
        return {control.id: control for control in self.controls}

    def visible(self, include_advanced: bool = False, include_hidden: bool = False) -> tuple[GraphControl, ...]:
        allowed = {"primary"}
        if include_advanced:
            allowed.add("advanced")
        if include_hidden:
            allowed.add("hidden")
        return tuple(control for control in self.controls if control.priority in allowed)

    def apply(self, prompt: Mapping[str, Any], changes: Mapping[str, Any]) -> dict:
        """Return a copied prompt with validated scalar control changes applied."""
        result = copy.deepcopy(prompt)
        controls = self.by_id()
        for control_id, value in changes.items():
            if control_id not in controls:
                raise KeyError(f"Unknown graph control: {control_id}")
            control = controls[control_id]
            if not control.editable:
                raise ValueError(f"Graph control is not editable: {control_id}")
            _validate_value(control, value)
            node = result.get(control.node_id)
            if node is None and control.node_id.isdigit():
                node = result.get(int(control.node_id))
            if not isinstance(node, dict):
                raise KeyError(f"Graph node no longer exists: {control.node_id}")
            node.setdefault("inputs", {})[control.input_name] = value
        return result


def _validate_value(control: GraphControl, value: Any) -> None:
    if control.choices and value not in control.choices:
        raise ValueError(f"{control.id} must be one of {control.choices!r}")
    if control.data_type.upper() == "INT" and (isinstance(value, bool) or not isinstance(value, int)):
        raise TypeError(f"{control.id} requires an integer")
    if control.data_type.upper() == "FLOAT" and (isinstance(value, bool) or not isinstance(value, (int, float))):
        raise TypeError(f"{control.id} requires a number")
    if control.minimum is not None and isinstance(value, (int, float)) and value < control.minimum:
        raise ValueError(f"{control.id} is below minimum {control.minimum}")
    if control.maximum is not None and isinstance(value, (int, float)) and value > control.maximum:
        raise ValueError(f"{control.id} is above maximum {control.maximum}")


def derive_graph_controls(
    prompt: Mapping[str, Any],
    object_info_map: Mapping[str, Any],
    presentation: Mapping[str, Any] | None = None,
) -> GraphControlRegistry:
    """Derive editable Workstation controls from the actual ComfyUI graph/schema.

    Connections are intentionally excluded. Scalar/widget values remain graph
    owned and are represented here only as normalized bindings.
    """
    controls: list[GraphControl] = []
    for raw_node_id, raw_node in prompt.items():
        if not isinstance(raw_node, Mapping):
            continue
        node_id = str(raw_node_id)
        node_type = str(raw_node.get("class_type") or "")
        info = object_info_map.get(node_type, {})
        inputs = raw_node.get("inputs") or {}
        if not isinstance(inputs, Mapping):
            continue

        for input_name, value in inputs.items():
            if _is_connection(value, prompt):
                continue
            section, spec = _schema_for_input(info, str(input_name))
            if spec is None:
                control = GraphControl(
                    id=f"{node_id}.{input_name}",
                    node_id=node_id,
                    node_type=node_type,
                    input_name=str(input_name),
                    data_type="*",
                    value=value,
                    widget="read-only",
                    label=_humanize(str(input_name)),
                    group="Advanced",
                    section="unknown",
                    editable=False,
                    priority="advanced",
                    reason="Input is not present in the live ComfyUI node schema.",
                )
                controls.append(_apply_presentation(control, presentation))
                continue

            data_type, meta, choices = _decode_spec(spec)
            group, priority = _group_for(str(input_name), data_type)
            control = GraphControl(
                id=f"{node_id}.{input_name}",
                node_id=node_id,
                node_type=node_type,
                input_name=str(input_name),
                data_type=data_type,
                value=value,
                widget=_widget_for(data_type, meta, choices),
                label=str(meta.get("label") or _humanize(str(input_name))),
                group=group,
                section=str(section or "required"),
                minimum=meta.get("min"),
                maximum=meta.get("max"),
                step=meta.get("step"),
                choices=choices,
                editable=True,
                priority=priority,
            )
            controls.append(_apply_presentation(control, presentation))

    return GraphControlRegistry(tuple(controls))
