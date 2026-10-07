from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import json

import preset_manager
import stack_manager
from core.registry import load_capability_registry

APP_ROOT = Path(__file__).resolve().parent.parent
PACKS_FILE = APP_ROOT / "catalog" / "packs.json"
CAPABILITIES_FILE = APP_ROOT / "catalog" / "r1" / "capabilities.json"


def _capability_titles() -> dict[str, str]:
    try:
        registry = load_capability_registry(CAPABILITIES_FILE)
        return {entry.id: entry.title for entry in registry.entries}
    except Exception:
        return {}


@dataclass(frozen=True)
class Blueprint:
    id: str
    title: str
    category: str
    family: str
    profile: str
    description: str
    path: str
    required_files: tuple[str, ...]
    stack_id: str = ""
    capability_id: str = ""
    staff_pick: bool = False

    @property
    def source_image_required(self) -> bool:
        # Compatibility projection for the legacy GTK beta. R1 Core uses the
        # semantic capability ID rather than a Character-specific flag.
        return self.capability_id in {"image.reference", "video.image_to_video"}

    @property
    def capability(self) -> str:
        return _capability_titles().get(self.capability_id, self.capability_id or "Unknown")


def load_blueprints() -> list[Blueprint]:
    rows = []
    for entry in preset_manager.load_manifest():
        rows.append(Blueprint(
            id=str(entry["id"]),
            title=str(entry["title"]),
            category=str(entry["category"]),
            family=str(entry.get("family", "")),
            profile=str(entry.get("profile", "")),
            description=str(entry.get("description", "")),
            path=str(entry.get("path", "")),
            required_files=tuple(entry.get("required_files", [])),
            stack_id=str(entry.get("stack_id", "")),
            capability_id=str(entry.get("capability_id", "")),
            staff_pick=entry.get("profile") in (
                "Normal",
                "Fast",
                "Single Reference",
                "I2V Normal",
                "Mobile Normal",
            ),
        ))
    return rows


def get_blueprint(blueprint_id: str) -> Blueprint | None:
    for blueprint in load_blueprints():
        if blueprint.id == blueprint_id:
            return blueprint
    return None


def blueprint_status(bp: Blueprint, files=None) -> str:
    files = files or preset_manager.scan_model_files()
    missing = [name for name in bp.required_files if name not in files]
    return "READY" if not missing else f"NEEDS PACK ({len(missing)} missing)"


def missing_files(bp: Blueprint, files=None) -> list[str]:
    files = files or preset_manager.scan_model_files()
    return [name for name in bp.required_files if name not in files]


def load_api_workflow(bp: Blueprint) -> dict:
    return json.loads((preset_manager.BUNDLE / bp.path).read_text(encoding="utf-8"))


def load_packs() -> list[dict]:
    try:
        raw = json.loads(PACKS_FILE.read_text(encoding="utf-8"))
        return raw.get("packs", []) if isinstance(raw, dict) else []
    except Exception:
        return []


def get_pack(pack_id: str) -> dict | None:
    for pack in load_packs():
        if pack.get("id") == pack_id:
            return pack
    return None


def pack_status(pack: dict) -> str:
    stacks = {stack["id"]: stack for stack in stack_manager.load_catalog()}
    statuses = [
        stack_manager.stack_status(stacks[stack_id])
        for stack_id in pack.get("stack_ids", [])
        if stack_id in stacks
    ]
    if statuses and all(status == "INSTALLED" for status in statuses):
        return "INSTALLED"
    if any(status.startswith("PARTIAL") or status == "INSTALLED" for status in statuses):
        return "PARTIAL"
    return "AVAILABLE"


def pack_stacks(pack: dict) -> list[dict]:
    stacks = {stack["id"]: stack for stack in stack_manager.load_catalog()}
    return [
        stacks[stack_id]
        for stack_id in pack.get("stack_ids", [])
        if stack_id in stacks
    ]
