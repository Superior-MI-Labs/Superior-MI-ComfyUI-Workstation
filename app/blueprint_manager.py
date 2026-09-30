from __future__ import annotations
from dataclasses import dataclass
from pathlib import Path
import json

import preset_manager
import stack_manager

APP_ROOT = Path(__file__).resolve().parent.parent
PACKS_FILE = APP_ROOT / "catalog" / "packs.json"

FAMILY_STACK = {
    "FLUX.2 Klein 4B": "flux2-klein-4b-fast",
    "Qwen Image 2.1": "qwen-image-2.1-convrot",
    "Wan2.2 TI2V 5B": "wan2.2-ti2v-5b",
    "MiniMax H3": "h3-kijai-w4a8-clipproj",
}

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
    source_image_required: bool = False
    character_aware: bool = False
    staff_pick: bool = False

    @property
    def capability(self) -> str:
        if self.source_image_required:
            return "Image → Video"
        if self.character_aware:
            return "Reference → Image"
        if self.category == "Video":
            return "Video"
        if self.category == "Character":
            return "Character"
        return "Text → Image"

def load_blueprints() -> list[Blueprint]:
    rows = []
    for e in preset_manager.load_manifest():
        path = str(e.get("path", ""))
        family = str(e.get("family", ""))
        is_wan_ref = family == "Wan2.2 TI2V 5B" and "/Wan2.2-TI2V-5B/" in ("/" + path) and e.get("category") == "Character"
        is_qwen_ref = family == "Qwen Image 2.1" and e.get("category") == "Character" and "Reference" in (e.get("title","") + e.get("profile",""))
        rows.append(Blueprint(
            id=str(e["id"]),
            title=str(e["title"]),
            category=str(e["category"]),
            family=family,
            profile=str(e.get("profile","")),
            description=str(e.get("description","")),
            path=path,
            required_files=tuple(e.get("required_files", [])),
            stack_id=FAMILY_STACK.get(family, ""),
            source_image_required=is_wan_ref,
            character_aware=is_qwen_ref,
            staff_pick=e.get("profile") in ("Normal", "Fast", "Single Reference", "I2V Normal", "Mobile Normal"),
        ))
    return rows

def get_blueprint(blueprint_id: str) -> Blueprint | None:
    for b in load_blueprints():
        if b.id == blueprint_id:
            return b
    return None

def blueprint_status(bp: Blueprint, files=None) -> str:
    files = files or preset_manager.scan_model_files()
    missing = [x for x in bp.required_files if x not in files]
    return "READY" if not missing else f"NEEDS PACK ({len(missing)} missing)"

def missing_files(bp: Blueprint, files=None) -> list[str]:
    files = files or preset_manager.scan_model_files()
    return [x for x in bp.required_files if x not in files]

def load_api_workflow(bp: Blueprint) -> dict:
    return json.loads((preset_manager.BUNDLE / bp.path).read_text(encoding="utf-8"))

def load_packs() -> list[dict]:
    try:
        raw = json.loads(PACKS_FILE.read_text(encoding="utf-8"))
        return raw.get("packs", []) if isinstance(raw, dict) else []
    except Exception:
        return []

def get_pack(pack_id: str) -> dict | None:
    for p in load_packs():
        if p.get("id") == pack_id:
            return p
    return None

def pack_status(pack: dict) -> str:
    stacks = {s["id"]: s for s in stack_manager.load_catalog()}
    statuses = [stack_manager.stack_status(stacks[sid]) for sid in pack.get("stack_ids", []) if sid in stacks]
    if statuses and all(x == "INSTALLED" for x in statuses):
        return "INSTALLED"
    if any(x.startswith("PARTIAL") or x == "INSTALLED" for x in statuses):
        return "PARTIAL"
    return "AVAILABLE"

def pack_stacks(pack: dict) -> list[dict]:
    stacks = {s["id"]: s for s in stack_manager.load_catalog()}
    return [stacks[sid] for sid in pack.get("stack_ids", []) if sid in stacks]
