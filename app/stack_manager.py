from __future__ import annotations
import json, os, shutil, subprocess, urllib.request
from pathlib import Path

HOME = Path.home()
COMFY = HOME / "Projects/AI-Runtimes/ComfyUI"
MODEL_ROOT = HOME / "Models/Media"
PRESET_ROOT = HOME / "Projects/AI-Runtimes/Qualification/presets"
APP_ROOT = Path(__file__).resolve().parent.parent
CATALOG_FILE = APP_ROOT / "catalog/stacks.json"

def load_catalog():
    if not CATALOG_FILE.exists():
        return []
    return json.loads(CATALOG_FILE.read_text()).get("stacks", [])

def scan_names():
    names=set()
    for root in (COMFY/"models", MODEL_ROOT):
        if not root.exists():
            continue
        for p in root.rglob("*"):
            try:
                if p.is_file() or p.is_symlink():
                    names.add(p.name)
            except OSError:
                pass
    return names

def stack_status(stack, names=None):
    names = names or scan_names()
    assets = stack.get("assets", [])
    if not assets:
        return "INFO"
    have = sum(1 for a in assets if Path(a["file"]).name in names)
    if have == len(assets):
        return "INSTALLED"
    if have:
        return f"PARTIAL {have}/{len(assets)}"
    return "AVAILABLE"

def find_hf():
    return shutil.which("hf") or str(HOME / ".local/bin/hf")

def _run(cmd, cwd=None):
    p=subprocess.run(cmd, cwd=cwd, text=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, check=False)
    if p.returncode:
        raise RuntimeError(p.stdout.strip() or f"command failed: {cmd}")
    return p.stdout.strip()

def download_stack(stack, authorized=False, progress=None):
    if stack.get("license_restricted") and not authorized:
        raise PermissionError("This stack is marked license-restricted. Confirm you have applicable authorization/rights before downloading.")
    if stack.get("custom_nodes"):
        raise RuntimeError(
            "Legacy direct-Git custom-node installation is disabled. "
            "Resolve custom nodes through the Workstation R1 package service / ComfyUI-Manager."
        )
    hf=find_hf()
    if not Path(hf).exists() and not shutil.which("hf"):
        raise RuntimeError("Hugging Face 'hf' CLI not found. Install huggingface_hub first.")
    base = MODEL_ROOT / stack.get("canonical_base","Catalog")
    base.mkdir(parents=True, exist_ok=True)
    names=scan_names()
    results=[]
    for i,a in enumerate(stack.get("assets",[]), start=1):
        name=Path(a["file"]).name
        if name in names:
            results.append(f"SKIP installed: {name}")
            continue
        if progress:
            progress(f"Downloading {i}/{len(stack.get('assets',[]))}: {name}")
        _run([hf,"download",a["repo"],a["file"],"--local-dir",str(base)])
        src=base / a["file"]
        if not src.exists():
            # HF CLI may flatten in future versions; attempt basename search.
            matches=list(base.rglob(name))
            if not matches:
                raise RuntimeError(f"Download completed but file was not found: {name}")
            src=matches[0]
        target_dir=COMFY/"models"/a["target"]
        target_dir.mkdir(parents=True, exist_ok=True)
        target=target_dir/name
        if target.exists() or target.is_symlink():
            target.unlink()
        target.symlink_to(src)
        results.append(f"OK {name} -> {target}")
        names.add(name)

    return "\n".join(results) or "No downloadable assets in this catalog entry."

def install_workflows(stack, progress=None):
    urls=stack.get("workflow_urls",[])
    if not urls:
        return "No workflow URLs are defined for this stack."
    dest=PRESET_ROOT/"Superior-MI-Official"/stack["id"]
    dest.mkdir(parents=True, exist_ok=True)
    out=[]
    for i,url in enumerate(urls, start=1):
        name=url.rsplit("/",1)[-1]
        if progress: progress(f"Fetching workflow {i}/{len(urls)}: {name}")
        req=urllib.request.Request(url, headers={"User-Agent":"Superior-MI-Labs-ComfyUI"})
        with urllib.request.urlopen(req, timeout=30) as r:
            data=r.read()
        (dest/name).write_bytes(data)
        out.append(str(dest/name))
    return "\n".join(out)
