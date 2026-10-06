from __future__ import annotations

import json
import os
import platform as platform_module
import re
import shutil
import subprocess
from pathlib import Path
from typing import Callable, Iterable

from .contracts import GPUProfile, HardwareProfile, StorageProfile

RunText = Callable[[list[str]], str]


def _run_text(command: list[str]) -> str:
    try:
        result = subprocess.run(
            command,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
            timeout=6,
            check=False,
        )
    except (OSError, subprocess.SubprocessError):
        return ""
    return result.stdout.strip() if result.returncode == 0 else ""


def _bytes_from_memory_label(value: str) -> int:
    match = re.search(r"([0-9]+(?:\.[0-9]+)?)\s*(GB|MB|KB)", value, re.I)
    if not match:
        return 0
    amount = float(match.group(1))
    unit = match.group(2).upper()
    scale = {"KB": 1024, "MB": 1024**2, "GB": 1024**3}[unit]
    return int(amount * scale)


def parse_os_release_text(text: str) -> dict[str, str]:
    values: dict[str, str] = {}
    for raw in text.splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        values[key] = value.strip().strip('"').strip("'")
    return values


def parse_nvidia_smi_csv(text: str) -> tuple[GPUProfile, ...]:
    gpus = []
    for line in text.splitlines():
        if not line.strip():
            continue
        parts = [part.strip() for part in line.split(",")]
        if len(parts) < 3:
            continue
        name, memory_mib, driver = parts[:3]
        compute_capability = parts[3] if len(parts) > 3 else ""
        try:
            vram = int(float(memory_mib) * 1024**2)
        except ValueError:
            vram = 0
        gpus.append(
            GPUProfile(
                vendor="NVIDIA",
                model=name,
                vram_bytes=vram,
                driver=driver,
                backend_candidates=("cuda",),
                compute_capability=compute_capability,
            )
        )
    return tuple(gpus)


def parse_lspci_gpus(text: str) -> tuple[GPUProfile, ...]:
    gpus = []
    for line in text.splitlines():
        lower = line.lower()
        if not any(kind in lower for kind in ("vga compatible controller", "3d controller", "display controller")):
            continue
        if "nvidia" in lower:
            vendor = "NVIDIA"
        elif "amd" in lower or "advanced micro devices" in lower or "ati " in lower:
            vendor = "AMD"
        elif "intel" in lower:
            vendor = "Intel"
        else:
            vendor = "Unknown"
        model = line.split(":", 2)[-1].strip()
        candidates = {"NVIDIA": ("cuda",), "AMD": ("rocm",), "Intel": ("xpu",)}.get(vendor, ())
        gpus.append(GPUProfile(vendor=vendor, model=model, backend_candidates=candidates))
    return tuple(gpus)


def parse_macos_displays_json(text: str) -> tuple[GPUProfile, ...]:
    try:
        payload = json.loads(text)
    except (TypeError, json.JSONDecodeError):
        return ()
    rows = payload.get("SPDisplaysDataType", []) if isinstance(payload, dict) else []
    gpus = []
    for row in rows:
        if not isinstance(row, dict):
            continue
        model = str(row.get("sppci_model") or row.get("_name") or "Apple GPU")
        vendor = "Apple" if "apple" in model.lower() else str(row.get("spdisplays_vendor") or "Unknown")
        vram = _bytes_from_memory_label(
            str(row.get("spdisplays_vram") or row.get("spdisplays_vram_shared") or "")
        )
        gpus.append(
            GPUProfile(
                vendor=vendor,
                model=model,
                vram_bytes=vram,
                backend_candidates=("mps",) if vendor == "Apple" else (),
            )
        )
    return tuple(gpus)


def parse_windows_video_json(text: str) -> tuple[GPUProfile, ...]:
    try:
        payload = json.loads(text)
    except (TypeError, json.JSONDecodeError):
        return ()
    rows = payload if isinstance(payload, list) else [payload]
    gpus = []
    for row in rows:
        if not isinstance(row, dict):
            continue
        model = str(row.get("Name") or "Unknown GPU")
        lower = model.lower()
        vendor = "NVIDIA" if "nvidia" in lower else "AMD" if ("amd" in lower or "radeon" in lower) else "Intel" if "intel" in lower else "Unknown"
        try:
            vram = int(row.get("AdapterRAM") or 0)
        except (TypeError, ValueError):
            vram = 0
        candidates = {"NVIDIA": ("cuda",), "AMD": ("rocm",), "Intel": ("xpu",)}.get(vendor, ())
        gpus.append(
            GPUProfile(
                vendor=vendor,
                model=model,
                vram_bytes=vram,
                driver=str(row.get("DriverVersion") or ""),
                backend_candidates=candidates,
            )
        )
    return tuple(gpus)


def _gpu_key(gpu: GPUProfile) -> tuple[str, str]:
    return gpu.vendor.lower(), re.sub(r"\s+", " ", gpu.model.lower()).strip()


def _merge_gpus(*groups: Iterable[GPUProfile]) -> tuple[GPUProfile, ...]:
    merged: dict[tuple[str, str], GPUProfile] = {}
    for group in groups:
        for gpu in group:
            key = _gpu_key(gpu)
            existing = merged.get(key)
            if existing is None:
                merged[key] = gpu
                continue
            # Prefer the observation with more concrete driver/VRAM/backend data.
            old_score = sum(bool(x) for x in (existing.vram_bytes, existing.driver, existing.backend_candidates))
            new_score = sum(bool(x) for x in (gpu.vram_bytes, gpu.driver, gpu.backend_candidates))
            if new_score > old_score:
                merged[key] = gpu
    return tuple(merged.values())


def observe_gpus(system: str | None = None, run_text: RunText = _run_text) -> tuple[GPUProfile, ...]:
    system = system or platform_module.system()

    if system == "Darwin":
        raw = run_text(["system_profiler", "SPDisplaysDataType", "-json"])
        return parse_macos_displays_json(raw)

    if system == "Windows":
        raw = run_text([
            "powershell",
            "-NoProfile",
            "-Command",
            "Get-CimInstance Win32_VideoController | Select-Object Name,AdapterRAM,DriverVersion | ConvertTo-Json -Compress",
        ])
        return parse_windows_video_json(raw)

    if system == "Linux":
        nvidia_raw = run_text([
            "nvidia-smi",
            "--query-gpu=name,memory.total,driver_version,compute_cap",
            "--format=csv,noheader,nounits",
        ])
        if not nvidia_raw:
            nvidia_raw = run_text([
                "nvidia-smi",
                "--query-gpu=name,memory.total,driver_version",
                "--format=csv,noheader,nounits",
            ])
        nvidia = parse_nvidia_smi_csv(nvidia_raw)

        pci = parse_lspci_gpus(run_text(["lspci"]))
        # nvidia-smi has materially richer NVIDIA identity. Do not create a
        # second physical GPU record from lspci for the same vendor lane.
        if nvidia:
            pci = tuple(gpu for gpu in pci if gpu.vendor != "NVIDIA")

        return _merge_gpus(nvidia, pci)

    return ()


def _linux_cpu_model() -> str:
    path = Path("/proc/cpuinfo")
    try:
        for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
            if line.lower().startswith("model name") and ":" in line:
                return line.split(":", 1)[1].strip()
    except OSError:
        pass
    return ""


def _physical_cpu_count_linux() -> int:
    path = Path("/proc/cpuinfo")
    try:
        packages = set()
        physical = core = None
        for line in path.read_text(encoding="utf-8", errors="replace").splitlines() + [""]:
            if not line.strip():
                if physical is not None and core is not None:
                    packages.add((physical, core))
                physical = core = None
                continue
            if line.startswith("physical id") and ":" in line:
                physical = line.split(":", 1)[1].strip()
            elif line.startswith("core id") and ":" in line:
                core = line.split(":", 1)[1].strip()
        return len(packages)
    except OSError:
        return 0


def _memory_snapshot() -> tuple[int, int]:
    if Path("/proc/meminfo").exists():
        values = {}
        try:
            for line in Path("/proc/meminfo").read_text().splitlines():
                if ":" not in line:
                    continue
                key, raw = line.split(":", 1)
                amount = raw.strip().split()[0]
                if amount.isdigit():
                    values[key] = int(amount) * 1024
            return values.get("MemTotal", 0), values.get("MemAvailable", 0)
        except OSError:
            pass

    try:
        pages = os.sysconf("SC_PHYS_PAGES")
        page_size = os.sysconf("SC_PAGE_SIZE")
        total = int(pages * page_size)
    except (AttributeError, OSError, ValueError):
        total = 0
    return total, 0


def _storage_profile(path: Path) -> StorageProfile | None:
    try:
        usage = shutil.disk_usage(path)
    except OSError:
        return None
    return StorageProfile(
        path=str(path),
        free_bytes=usage.free,
        total_bytes=usage.total,
    )


def observe_hardware(
    *,
    system: str | None = None,
    machine: str | None = None,
    run_text: RunText = _run_text,
    storage_paths: Iterable[Path] | None = None,
) -> HardwareProfile:
    system = system or platform_module.system()
    machine = machine or platform_module.machine()
    logical = os.cpu_count() or 0
    physical = _physical_cpu_count_linux() if system == "Linux" else 0
    cpu_model = _linux_cpu_model() if system == "Linux" else platform_module.processor()
    total_memory, available_memory = _memory_snapshot()

    distribution = ""
    os_version = platform_module.release()
    if system == "Linux":
        try:
            os_release = parse_os_release_text(Path("/etc/os-release").read_text(encoding="utf-8", errors="replace"))
        except OSError:
            os_release = {}
        distribution = os_release.get("PRETTY_NAME") or os_release.get("NAME") or ""
        os_version = os_release.get("VERSION_ID") or platform_module.release()

    paths = list(storage_paths or (Path.home(),))
    storage = tuple(item for item in (_storage_profile(path) for path in paths) if item is not None)

    return HardwareProfile(
        platform=system.lower(),
        architecture=machine,
        os_version=os_version,
        distribution=distribution,
        cpu_model=cpu_model,
        logical_cpu_count=logical,
        physical_cpu_count=physical,
        memory_total_bytes=total_memory,
        memory_available_bytes=available_memory,
        gpus=observe_gpus(system=system, run_text=run_text),
        storage=storage,
    )
