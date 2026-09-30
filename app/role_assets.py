from __future__ import annotations
from pathlib import Path

ROLE_FILES = {
    "field": "01_kisha_field_researcher_reference_sheet.png",
    "analyst": "02_kisha_data_analyst_reference_sheet.png",
    "digital": "03_kisha_digital_interface_reference_sheet.png",
    "reflection": "04_kisha_reflection_mode_reference_sheet.png",
    "explorer": "05_kisha_explorer_reference_sheet.png",
    "everyday": "06_kisha_everyday_lab_reference_sheet.png",
}
ROLE_TITLES = {
    "field": "Kisha / Field Researcher",
    "analyst": "Kisha / Data Analyst",
    "digital": "Kisha / Digital Interface",
    "reflection": "Kisha / Reflection Mode",
    "explorer": "Kisha / Explorer",
    "everyday": "Kisha / Everyday Lab",
}

def app_root() -> Path:
    return Path(__file__).resolve().parent.parent

def asset_root() -> Path:
    return app_root() / "assets" / "kisha"

def role_path(role: str, thumbnail: bool = True) -> Path:
    name = ROLE_FILES.get(role, ROLE_FILES["digital"])
    if thumbnail:
        p = asset_root() / "thumbs" / name
        if p.exists():
            return p
    return asset_root() / name

def full_role_path(role: str) -> Path:
    return asset_root() / ROLE_FILES.get(role, ROLE_FILES["digital"])

def app_icon_path() -> Path:
    return app_root() / "assets" / "superior-mi-comfyui.png"
