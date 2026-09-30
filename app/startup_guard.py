from __future__ import annotations
import json
import os
import time
from pathlib import Path

HOME = Path.home()
CACHE = HOME / ".cache" / "superior-mi-comfyui-workstation"
STATE = CACHE / "startup-state.json"
LOG = CACHE / "startup-stage.log"

def stage(name: str, detail: str = ""):
    CACHE.mkdir(parents=True, exist_ok=True)
    payload = {
        "time": time.time(),
        "pid": os.getpid(),
        "stage": str(name),
        "detail": str(detail),
    }
    try:
        STATE.write_text(json.dumps(payload, indent=2) + "\n")
        with LOG.open("a") as f:
            f.write(f"{time.strftime('%Y-%m-%d %H:%M:%S')} pid={os.getpid()} stage={name} {detail}\n")
    except Exception:
        pass

def complete():
    stage("ready", "main window presented")
