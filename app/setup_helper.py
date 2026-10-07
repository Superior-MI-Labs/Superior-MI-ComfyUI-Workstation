from __future__ import annotations

import os
import shutil
import subprocess
import time
from pathlib import Path

from core.hardware import observe_hardware
from core.runtime_profile import observe_runtime

HOME = Path.home()
RUNTIMES = HOME / "Projects/AI-Runtimes"
COMFY = RUNTIMES / "ComfyUI"
QUAL = RUNTIMES / "Qualification"


def run(cmd, cwd=None, progress=None, env=None):
    if progress:
        progress("$ " + " ".join(str(x) for x in cmd))
    p = subprocess.Popen(
        [str(x) for x in cmd],
        cwd=str(cwd) if cwd else None,
        env=env,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        bufsize=1,
    )
    lines = []
    assert p.stdout is not None
    for line in p.stdout:
        line = line.rstrip()
        lines.append(line)
        if progress and line:
            progress(line)
    rc = p.wait()
    text = "\n".join(lines)
    if rc:
        raise RuntimeError(text or f"Command failed with exit code {rc}: {cmd}")
    return text


def command(name):
    return shutil.which(name)


def detect_gpu():
    """Legacy GTK projection over the canonical R1 hardware/runtime observers."""
    result = {
        "vendor": "Unknown",
        "name": "Unknown",
        "vram_gib": 0.0,
        "driver": "Unknown",
        "cuda_reported": "Unknown",
        "nvidia_ok": False,
    }
    hardware = observe_hardware(storage_paths=())
    runtime = observe_runtime()
    preferred = next((gpu for gpu in hardware.gpus if gpu.vendor == "NVIDIA"), None)
    gpu = preferred or (hardware.gpus[0] if hardware.gpus else None)
    if gpu is None:
        return result

    result.update({
        "vendor": gpu.vendor,
        "name": gpu.model,
        "vram_gib": round(gpu.vram_bytes / (1024**3), 2) if gpu.vram_bytes else 0.0,
        "driver": gpu.driver or "Unknown",
        "nvidia_ok": gpu.vendor == "NVIDIA",
    })
    if runtime.compute_backend == "cuda" and runtime.backend_version:
        result["cuda_reported"] = runtime.backend_version
    return result


def comfy_state():
    return {
        "repo": (COMFY / ".git").exists(),
        "main": (COMFY / "main.py").exists(),
        "venv": (COMFY / ".venv/bin/python").exists(),
        "requirements": (COMFY / "requirements.txt").exists(),
        "complete": (COMFY / "main.py").exists() and (COMFY / ".venv/bin/python").exists(),
    }


def _write_launchers():
    RUNTIMES.mkdir(parents=True, exist_ok=True)
    (QUAL / "bin").mkdir(parents=True, exist_ok=True)
    (QUAL / "logs").mkdir(parents=True, exist_ok=True)
    run_sh = RUNTIMES / "run-comfyui.sh"
    run_sh.write_text(f'''#!/usr/bin/env bash
set -euo pipefail
COMFY="{COMFY}"
cd "$COMFY"
exec "$COMFY/.venv/bin/python" main.py --listen 127.0.0.1 --port 8188
''')
    run_sh.chmod(0o755)

    start_sh = QUAL / "bin/q-start-comfyui.sh"
    start_sh.write_text(f'''#!/usr/bin/env bash
set -euo pipefail
COMFY="{COMFY}"
LOGROOT="{QUAL / 'logs'}"
mkdir -p "$LOGROOT"
for p in $(pgrep -f 'python.*main.py' || true); do
  cwd="$(readlink -f "/proc/$p/cwd" 2>/dev/null || true)"
  if [[ "$cwd" == "$COMFY" ]]; then
    echo "ComfyUI already running (PID $p)"
    exit 0
  fi
done
LOG="$LOGROOT/comfyui-$(date +%Y-%m-%d-%H%M%S).log"
cd "$COMFY"
nohup "$COMFY/.venv/bin/python" main.py --listen 127.0.0.1 --port 8188 >"$LOG" 2>&1 &
echo $! > "$LOGROOT/comfyui.pid"
echo "ComfyUI starting"
echo "PID: $!"
echo "Log: $LOG"
echo "URL: http://127.0.0.1:8188"
''')
    start_sh.chmod(0o755)

    stop_sh = QUAL / "bin/q-stop-comfyui.sh"
    stop_sh.write_text(f'''#!/usr/bin/env bash
set -euo pipefail
COMFY="{COMFY}"
found=0
for p in $(pgrep -f 'python.*main.py' || true); do
  cwd="$(readlink -f "/proc/$p/cwd" 2>/dev/null || true)"
  if [[ "$cwd" == "$COMFY" ]]; then
    kill -TERM "$p" 2>/dev/null || true
    found=1
  fi
done
if [[ $found -eq 1 ]]; then
  echo "ComfyUI stop issued"
else
  echo "ComfyUI already stopped"
fi
''')
    stop_sh.chmod(0o755)


def install_comfyui_nvidia(progress=None):
    gpu = detect_gpu()
    if not gpu["nvidia_ok"]:
        raise RuntimeError("The guided installer currently supports NVIDIA Linux systems only. Use the official ComfyUI manual installation guide for AMD/Intel/CPU systems.")
    if not command("git"):
        raise RuntimeError("git is missing. Install the workstation package dependencies first.")
    if not command("python3"):
        raise RuntimeError("python3 is missing.")

    RUNTIMES.mkdir(parents=True, exist_ok=True)
    if COMFY.exists() and any(COMFY.iterdir()) and not (COMFY / ".git").exists():
        raise RuntimeError(f"{COMFY} already exists but is not a ComfyUI git checkout. It was left untouched.")

    if not COMFY.exists():
        run(["git", "clone", "https://github.com/Comfy-Org/ComfyUI.git", str(COMFY)], progress=progress)
    elif (COMFY / ".git").exists():
        if progress: progress("Existing ComfyUI checkout found. Leaving source revision unchanged during setup.")

    if not (COMFY / ".venv/bin/python").exists():
        run(["python3", "-m", "venv", str(COMFY / ".venv")], progress=progress)

    py = COMFY / ".venv/bin/python"
    pip = COMFY / ".venv/bin/pip"
    if not pip.exists():
        run([str(py), "-m", "ensurepip", "--upgrade"], progress=progress)

    run([str(py), "-m", "pip", "install", "--upgrade", "pip", "setuptools", "wheel"], progress=progress)
    run([
        str(py), "-m", "pip", "install",
        "torch", "torchvision", "torchaudio",
        "--extra-index-url", "https://download.pytorch.org/whl/cu130",
    ], progress=progress)
    run([str(py), "-m", "pip", "install", "-r", str(COMFY / "requirements.txt")], cwd=COMFY, progress=progress)

    _write_launchers()
    if progress:
        progress("Verifying PyTorch / CUDA...")
    verify = subprocess.run([
        str(py), "-c",
        "import torch; print('torch',torch.__version__); print('cuda build',torch.version.cuda); print('cuda available',torch.cuda.is_available()); assert torch.cuda.is_available()",
    ], text=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, check=False)
    if progress and verify.stdout:
        progress(verify.stdout.strip())
    if verify.returncode:
        raise RuntimeError("ComfyUI installed, but the CUDA verification failed:\n" + verify.stdout)
    return "ComfyUI installation completed successfully."


def repair_launchers():
    if not (COMFY / "main.py").exists() or not (COMFY / ".venv/bin/python").exists():
        raise RuntimeError("ComfyUI is not fully installed yet.")
    _write_launchers()
    return "Runtime launcher scripts repaired."


def disk_free_gib():
    st = os.statvfs(str(HOME))
    return round(st.f_bavail * st.f_frsize / (1024**3), 1)
