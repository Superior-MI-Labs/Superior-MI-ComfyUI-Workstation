from __future__ import annotations

import copy
import json
import shutil
import urllib.error
import urllib.parse
import urllib.request
import uuid
from collections import defaultdict, deque
from pathlib import Path

HOME = Path.home()
APP_ROOT = Path(__file__).resolve().parent.parent
COMFY = HOME / "Projects" / "AI-Runtimes" / "ComfyUI"
BRIDGE_SOURCE = APP_ROOT / "bridge" / "Superior-MI-Workstation-Bridge"
BRIDGE_DEST = COMFY / "custom_nodes" / "Superior-MI-Workstation-Bridge"

def _request(url, data=None, method=None, headers=None, timeout=8.0):
    req = urllib.request.Request(
        url,
        data=data,
        method=method,
        headers={"User-Agent": "Superior-MI-Labs-ComfyUI-Workstation", **(headers or {})},
    )
    return urllib.request.urlopen(req, timeout=timeout)

def get_json(url, timeout=5.0):
    with _request(url, timeout=timeout) as r:
        return json.loads(r.read().decode("utf-8"))

def post_json(url, payload, timeout=8.0):
    data = json.dumps(payload).encode("utf-8")
    with _request(url, data=data, method="POST", headers={"Content-Type":"application/json"}, timeout=timeout) as r:
        body = r.read().decode("utf-8", "replace")
        return json.loads(body) if body else {}

def ensure_bridge() -> tuple[bool, str]:
    if not COMFY.exists():
        return False, "ComfyUI is not installed in the expected location."
    try:
        if BRIDGE_DEST.exists():
            # Update only our own bridge files.
            shutil.copytree(BRIDGE_SOURCE, BRIDGE_DEST, dirs_exist_ok=True)
            return True, "Superior MI ComfyUI bridge updated."
        BRIDGE_DEST.parent.mkdir(parents=True, exist_ok=True)
        shutil.copytree(BRIDGE_SOURCE, BRIDGE_DEST)
        return True, "Superior MI ComfyUI bridge installed."
    except Exception as exc:
        return False, str(exc)

def bridge_files_installed() -> bool:
    return (BRIDGE_DEST / "__init__.py").exists() and (BRIDGE_DEST / "web/js/superior-mi-workstation.js").exists()

def bridge_active(base_url: str) -> bool:
    try:
        data = get_json(base_url.rstrip("/") + "/superior-mi/bridge/status", timeout=1.5)
        return bool(data.get("ok"))
    except Exception:
        return False

def object_info(base_url: str) -> dict:
    return get_json(base_url.rstrip("/") + "/object_info", timeout=5.0)

def _input_type(spec):
    if isinstance(spec, (list, tuple)) and spec:
        head = spec[0]
        if isinstance(head, list):
            return "COMBO"
        return str(head)
    return str(spec) if spec is not None else "*"

def _schema_inputs(info: dict):
    inputs = info.get("input", {}) if isinstance(info, dict) else {}
    out = []
    for section in ("required", "optional"):
        raw = inputs.get(section, {}) or {}
        if isinstance(raw, dict):
            for name, spec in raw.items():
                out.append((name, _input_type(spec)))
    return out

def _schema_sections(info: dict):
    inputs = info.get("input", {}) if isinstance(info, dict) else {}
    for section in ("required", "optional", "hidden"):
        raw = inputs.get(section, {}) or {}
        if isinstance(raw, dict):
            yield section, raw


def _autogrow_children(info: dict) -> dict[str, str]:
    """Return legacy-child -> dotted live-input aliases for V3 Autogrow inputs."""
    aliases = {}
    for _section, raw in _schema_sections(info):
        for root, spec in raw.items():
            if not isinstance(spec, (list, tuple)) or not spec:
                continue
            io_type = str(spec[0])
            meta = spec[1] if len(spec) > 1 and isinstance(spec[1], dict) else {}
            if "AUTOGROW" not in io_type.upper():
                continue
            template = meta.get("template") or {}
            names = template.get("names")
            if isinstance(names, list):
                for name in names:
                    aliases[str(name)] = f"{root}.{name}"
                continue
            prefix = template.get("prefix")
            max_count = template.get("max")
            if isinstance(prefix, str) and isinstance(max_count, int):
                for i in range(max_count):
                    name = f"{prefix}{i}"
                    aliases[name] = f"{root}.{name}"
    return aliases


def _allowed_input_names(info: dict) -> tuple[set[str], dict[str, str]]:
    exact = set()
    aliases = _autogrow_children(info)
    for _section, raw in _schema_sections(info):
        exact.update(map(str, raw))
    # Some ComfyUI builds expose the expanded dotted inputs directly.
    exact.update(aliases.values())
    return exact, aliases


def adapt_api_prompt(prompt: dict, object_info_map: dict) -> dict:
    """Adapt a Blueprint to the local ComfyUI input contract.

    The API graph is treated as data. Before execution we reconcile each node
    against /object_info. V3 dynamic inputs such as Qwen Image 2.1 references
    are rewritten from legacy `image_1` form to `images.image_1`.
    """
    adapted = copy.deepcopy(prompt)
    errors = []

    for node_id, node in adapted.items():
        if not isinstance(node, dict):
            continue
        ctype = str(node.get("class_type") or "")
        if not ctype:
            continue
        info = object_info_map.get(ctype)
        if not isinstance(info, dict):
            errors.append(f"Node {node_id}: ComfyUI does not provide node type {ctype}")
            continue

        inputs = node.setdefault("inputs", {})
        exact, aliases = _allowed_input_names(info)

        # Rewrite known legacy dynamic child names before validation.
        for legacy, dotted in aliases.items():
            if legacy in inputs and dotted not in inputs:
                inputs[dotted] = inputs.pop(legacy)

        # If a build exposes dotted fields directly, accept them. If object_info
        # only exposes the Autogrow root, aliases above represent its live paths.
        unknown = []
        for name in inputs:
            if name in exact:
                continue
            # Connections and scalar widgets are both invalid if the local node
            # schema cannot consume their key. Fail before Python execute().
            unknown.append(name)
        if unknown:
            errors.append(
                f"Node {node_id} ({ctype}) has inputs unsupported by this ComfyUI build: "
                + ", ".join(sorted(unknown))
            )

    if errors:
        raise RuntimeError(
            "Blueprint/runtime contract mismatch. The Workstation stopped before queueing:\n"
            + "\n".join(errors)
        )
    return adapted


def prepare_api_prompt(base_url: str, prompt: dict) -> tuple[dict, dict]:
    info = object_info(base_url)
    return adapt_api_prompt(prompt, info), info


def api_prompt_to_ui(prompt: dict, object_info_map: dict) -> dict:
    """Convert an API-format prompt into a loadable ComfyUI graph.

    The conversion is generated from the local /object_info contract so widget
    ordering and connection types follow the installed ComfyUI build instead of
    being hard-coded to one frontend release.
    """
    ids = list(prompt.keys())
    id_map = {old: i + 1 for i, old in enumerate(ids)}
    deps = {old: set() for old in ids}
    for old, node in prompt.items():
        for value in (node.get("inputs", {}) or {}).values():
            if isinstance(value, list) and len(value) == 2 and str(value[0]) in id_map:
                deps[old].add(str(value[0]))

    # Topological depth for a readable left-to-right layout.
    level = {old: 0 for old in ids}
    for _ in range(len(ids) + 2):
        changed = False
        for old in ids:
            lv = max([level.get(d, 0) + 1 for d in deps[old]] or [0])
            if lv != level[old]:
                level[old] = lv
                changed = True
        if not changed:
            break
    rows = defaultdict(int)

    ui_nodes = []
    node_by_old = {}
    for order, old in enumerate(ids):
        node = prompt[old]
        ctype = str(node.get("class_type", "Unknown"))
        info = object_info_map.get(ctype, {})
        schema = _schema_inputs(info)
        inputs_api = node.get("inputs", {}) or {}

        linked_inputs = []
        widgets_values = []
        widgets_named = {}
        target_slot_by_name = {}
        linked_names = set()
        for idx, (name, typ) in enumerate(schema):
            val = inputs_api.get(name, None)
            if isinstance(val, list) and len(val) == 2 and str(val[0]) in id_map:
                target_slot_by_name[name] = len(linked_inputs)
                linked_inputs.append({"name": name, "type": typ, "link": None})
                linked_names.add(name)
            elif name in inputs_api:
                widgets_values.append(val)
                widgets_named[name] = val

        # Preserve scalar inputs unknown to object_info at the end rather than losing them.
        for name, val in inputs_api.items():
            if name in linked_names or name in {n for n, _ in schema}:
                continue
            if not (isinstance(val, list) and len(val) == 2 and str(val[0]) in id_map):
                widgets_values.append(val)
                widgets_named[name] = val

        outs = info.get("output", []) or []
        out_names = info.get("output_name", []) or []
        outputs = []
        for idx, typ in enumerate(outs):
            name = str(out_names[idx]) if idx < len(out_names) else str(typ)
            outputs.append({"name": name, "type": str(typ), "slot_index": idx, "links": []})

        lv = level[old]
        row = rows[lv]
        rows[lv] += 1
        ui = {
            "id": id_map[old],
            "type": ctype,
            "pos": [60 + lv * 390, 60 + row * 230],
            "size": [320, max(82, 62 + 26 * max(len(linked_inputs), len(widgets_values)))],
            "flags": {},
            "order": order,
            "mode": 0,
            "inputs": linked_inputs,
            "outputs": outputs,
            "properties": {"Node name for S&R": ctype},
            "widgets_values": widgets_values,
        }
        if widgets_named:
            ui["widgets_values_named"] = widgets_named
        title = (node.get("_meta") or {}).get("title")
        if title:
            ui["title"] = str(title)
        ui["_target_slots"] = target_slot_by_name
        node_by_old[old] = ui
        ui_nodes.append(ui)

    links = []
    link_id = 1
    for target_old, node in prompt.items():
        inputs_api = node.get("inputs", {}) or {}
        target = node_by_old[target_old]
        schema_map = dict(_schema_inputs(object_info_map.get(str(node.get("class_type")), {})))
        for name, val in inputs_api.items():
            if not (isinstance(val, list) and len(val) == 2 and str(val[0]) in id_map):
                continue
            source_old, source_slot = str(val[0]), int(val[1])
            source = node_by_old[source_old]
            target_slot = target["_target_slots"].get(name)
            if target_slot is None:
                # Unknown linked input: append it so the graph remains connected.
                typ = schema_map.get(name, "*")
                target_slot = len(target["inputs"])
                target["inputs"].append({"name": name, "type": typ, "link": None})
            typ = target["inputs"][target_slot].get("type", "*")
            target["inputs"][target_slot]["link"] = link_id
            while len(source["outputs"]) <= source_slot:
                source["outputs"].append({"name": f"output_{len(source['outputs'])}", "type": typ, "slot_index": len(source["outputs"]), "links": []})
            source["outputs"][source_slot].setdefault("links", []).append(link_id)
            links.append([link_id, source["id"], source_slot, target["id"], target_slot, typ])
            link_id += 1

    for n in ui_nodes:
        n.pop("_target_slots", None)

    return {
        "id": str(uuid.uuid4()),
        "revision": 0,
        "last_node_id": max([n["id"] for n in ui_nodes] or [0]),
        "last_link_id": link_id - 1,
        "nodes": ui_nodes,
        "links": links,
        "groups": [],
        "config": {},
        "extra": {
            "ds": {"scale": 0.75, "offset": [80, 80]},
            "workflowRendererVersion": "LG",
            "superiorMI": {"generated": True},
        },
        "version": 0.4,
    }

def _safe_name(name: str) -> str:
    clean = "".join(c if c.isalnum() or c in " _-." else "_" for c in str(name)).strip()
    return clean[:100] or "Superior MI Workflow"

def store_ui_workflow(base_url: str, ui_workflow: dict, name: str, folder: str = "Superior MI") -> str:
    filename = _safe_name(name)
    if not filename.lower().endswith(".json"):
        filename += ".json"
    path = f"workflows/{_safe_name(folder)}/{filename}"
    encoded = urllib.parse.quote(path, safe="")
    url = base_url.rstrip("/") + f"/api/userdata/{encoded}?overwrite=true&full_info=true"
    raw = json.dumps(ui_workflow, indent=2).encode("utf-8")
    with _request(url, data=raw, method="POST", headers={"Content-Type":"application/json"}, timeout=10.0) as r:
        if r.status != 200:
            raise RuntimeError(f"ComfyUI workflow import failed: HTTP {r.status}")
        r.read()
    return path

def request_open_workflow(base_url: str, path: str) -> bool:
    try:
        post_json(base_url.rstrip("/") + "/superior-mi/open-workflow", {"path": path}, timeout=2.5)
        return True
    except Exception:
        return False

def import_api_workflow(base_url: str, api_prompt: dict, name: str, folder: str = "Superior MI", open_now: bool = True):
    info = object_info(base_url)
    api_prompt = adapt_api_prompt(api_prompt, info)
    ui = api_prompt_to_ui(api_prompt, info)
    path = store_ui_workflow(base_url, ui, name, folder)
    bridge_ok = request_open_workflow(base_url, path) if open_now else bridge_active(base_url)
    return {"path": path, "workflow": ui, "bridge_active": bridge_ok}
