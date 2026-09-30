from __future__ import annotations
import json, shutil, os
from pathlib import Path

HOME = Path.home()
COMFY = HOME / "Projects/AI-Runtimes/ComfyUI"
MODEL_ROOT = HOME / "Models/Media"
PRESET_ROOT = HOME / "Projects/AI-Runtimes/Qualification/presets"
APP_ROOT = Path(__file__).resolve().parent.parent
BUNDLE = APP_ROOT / "preset_library"

def scan_model_files():
    found = set()
    for root in (COMFY / "models", MODEL_ROOT):
        if not root.exists():
            continue
        for p in root.rglob("*"):
            try:
                if p.is_file() or p.is_symlink():
                    found.add(p.name)
            except OSError:
                pass
    return found

def load_manifest():
    p = BUNDLE / "index.json"
    if not p.exists():
        return []
    return json.loads(p.read_text()).get("presets", [])

def compatible(entry, files=None):
    files = files or scan_model_files()
    return all(x in files for x in entry.get("required_files", []))

def detect_families(files=None):
    files = files or scan_model_files()
    families = {}
    for e in load_manifest():
        fam = e["family"]
        families.setdefault(fam, False)
        if compatible(e, files):
            families[fam] = True
    if any("minimax_h3_" in x for x in files):
        families["MiniMax H3"] = True
    return families

def install_entry(entry):
    src = BUNDLE / entry["path"]
    dst = PRESET_ROOT / "Superior-MI-Labs" / entry["path"]
    dst.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(src, dst)
    return dst

def install_all_compatible():
    files = scan_model_files()
    installed=[]
    for e in load_manifest():
        if compatible(e, files):
            installed.append(install_entry(e))
    return installed

def install_all():
    return [install_entry(e) for e in load_manifest()]
