from __future__ import annotations

import copy
import json
import re
import urllib.error
import urllib.request
from datetime import datetime
from pathlib import Path

import shutil
import preset_manager

HOME = Path.home()
APP_ROOT = Path(__file__).resolve().parent.parent
PRESET_BUNDLE = APP_ROOT / "preset_library"
GENERATED_ROOT = HOME / "Projects" / "AI-Runtimes" / "Qualification" / "presets" / "Superior-MI-Labs" / "Generated"
COMFY_INPUT = HOME / "Projects" / "AI-Runtimes" / "ComfyUI" / "input"

MODES = {
    "Reference Image (Qwen Image 2.1)": {
        "family": "Qwen Image 2.1",
        "blueprint": "Reference/Qwen-Image-2.1/20_Single_Reference.json",
        "required": ["qwen_image_2.1_int8_convrot.safetensors", "qwen3vl_8b_int8_convrot.safetensors", "qwen_image_2.1_vae_bf16.safetensors"],
    },
    "Text Image (FLUX.2 Klein 4B)": {
        "family": "FLUX.2 Klein 4B",
        "blueprint": "Image/FLUX2-Klein/02_Portrait_768.json",
        "required": ["flux-2-klein-4b-fp8.safetensors", "qwen_3_4b_fp4_flux2.safetensors", "flux2-vae.safetensors"],
    },
    "Text Image (Qwen Image 2.1)": {
        "family": "Qwen Image 2.1",
        "blueprint": "Image/Qwen-Image-2.1/03_Normal_768_16step.json",
        "required": ["qwen_image_2.1_int8_convrot.safetensors", "qwen3vl_8b_int8_convrot.safetensors", "qwen_image_2.1_vae_bf16.safetensors"],
    },
    "Video from Image (Wan2.2 TI2V 5B)": {
        "family": "Wan2.2 TI2V 5B",
        "blueprint": "Video/Wan2.2-TI2V-5B/13_I2V_Normal_576x1024.json",
        "required": ["wan2.2_ti2v_5B_fp16.safetensors", "umt5_xxl_fp8_e4m3fn_scaled.safetensors", "wan2.2_vae.safetensors"],
    },
}

IMAGE_PROFILES = {
    "Fast": (640, 640, 12),
    "Normal": (768, 768, 16),
    "Quality": (1024, 1024, 25),
}
PHONE_IMAGE_PROFILES = {
    "Fast": (576, 1024, 12),
    "Normal": (576, 1024, 16),
    "Quality": (768, 1344, 20),
}
LANDSCAPE_IMAGE_PROFILES = {
    "Fast": (832, 480, 12),
    "Normal": (1024, 576, 16),
    "Quality": (1152, 640, 20),
}
VIDEO_PROFILES = {
    "Fast": (640, 352, 49, 12),
    "Normal": (832, 480, 49, 16),
    "Quality": (832, 480, 81, 20),
}
PHONE_VIDEO_PROFILES = {
    "Fast": (480, 832, 33, 10),
    "Normal": (576, 1024, 49, 16),
    "Quality": (576, 1024, 81, 20),
}


def installed_modes() -> dict[str, bool]:
    files = preset_manager.scan_model_files()
    return {name: all(x in files for x in spec["required"]) for name, spec in MODES.items()}


def mode_blueprint(mode: str) -> dict:
    spec = MODES.get(mode)
    if not spec:
        raise ValueError(f"Unknown creation mode: {mode}")
    return _load(spec["blueprint"])


def inspect_workflow_capabilities(workflow: dict) -> dict:
    """Derive beginner-facing controls from the actual graph contract.

    Create should expose semantic controls only when the selected Blueprint has
    nodes/sockets that can consume them. This keeps the simple UI aligned with
    the graph instead of maintaining a second hand-authored capability table.
    """
    classes = {
        str(node.get("class_type"))
        for node in workflow.values()
        if isinstance(node, dict) and node.get("class_type")
    }

    reference_slots = []
    for node in workflow.values():
        if not isinstance(node, dict):
            continue
        if node.get("class_type") != "TextEncodeQwenImage21":
            continue
        for name in (node.get("inputs") or {}):
            m = re.fullmatch(r"(?:images\.)?image_(\d+)", str(name))
            if m:
                reference_slots.append(int(m.group(1)))

    # A generic LoadImage is not enough to identify an image-to-video source:
    # Qwen reference Blueprints also contain LoadImage. The typed consumer
    # determines the graph meaning.
    source_image = False
    for node in workflow.values():
        if not isinstance(node, dict) or node.get("class_type") != "Wan22ImageToVideoLatent":
            continue
        value = (node.get("inputs") or {}).get("start_image")
        if isinstance(value, list) and len(value) == 2:
            upstream = workflow.get(str(value[0]), {})
            source_image = isinstance(upstream, dict) and upstream.get("class_type") == "LoadImage"

    reference_image = bool(reference_slots)

    # Qwen reference editing takes its latent geometry from image_1, so an
    # arbitrary orientation picker is misleading there. Text generation and
    # Wan I2V do have explicit output geometry controls.
    format_control = (
        not reference_image
        and bool(classes & {"EmptyLatentImage", "EmptySD3LatentImage", "Wan22ImageToVideoLatent", "ResolutionSelector"})
    )

    quality_control = bool(
        classes
        & {
            "KSampler",
            "SamplerCustomAdvanced",
            "Flux2Scheduler",
            "BasicScheduler",
        }
    )

    return {
        "reference_image": reference_image,
        "reference_slots": max(reference_slots, default=0),
        "source_image": source_image,
        "format": format_control,
        "quality": quality_control,
        "node_types": tuple(sorted(classes)),
    }


def mode_capabilities(mode: str) -> dict:
    return inspect_workflow_capabilities(mode_blueprint(mode))


def _load(rel: str) -> dict:
    return json.loads((PRESET_BUNDLE / rel).read_text(encoding="utf-8"))


def _safe_prefix(text: str) -> str:
    keep = "".join(c if c.isalnum() or c in "_-" else "_" for c in text)
    return "_".join(x for x in keep.split("_") if x)[:80] or "creation"


def _dimensions(orientation: str, quality: str, video: bool = False):
    quality = quality if quality in ("Fast", "Normal", "Quality") else "Normal"
    if video:
        table = PHONE_VIDEO_PROFILES if orientation == "Phone Portrait" else VIDEO_PROFILES
        return table[quality]
    if orientation == "Phone Portrait":
        return PHONE_IMAGE_PROFILES[quality]
    if orientation == "Landscape":
        return LANDSCAPE_IMAGE_PROFILES[quality]
    return IMAGE_PROFILES[quality]


def build_workflow(
    mode: str,
    prompt: str,
    orientation: str = "Square",
    quality: str = "Normal",
    reference_image: str | Path | None = None,
    source_image: str | Path | None = None,
) -> dict:
    prompt = (prompt or "").strip()
    if not prompt:
        raise ValueError("Enter a prompt first.")
    if mode not in MODES:
        raise ValueError(f"Unknown creation mode: {mode}")
    if not all(x in preset_manager.scan_model_files() for x in MODES[mode]["required"]):
        missing = [x for x in MODES[mode]["required"] if x not in preset_manager.scan_model_files()]
        raise RuntimeError("Required model files are missing:\n" + "\n".join(missing))

    if mode == "Reference Image (Qwen Image 2.1)":
        if not reference_image:
            raise ValueError("Choose a reference image first.")
        src = Path(reference_image).expanduser()
        if not src.exists() or not src.is_file():
            raise FileNotFoundError(f"Reference image not found: {src}")

        target_dir = COMFY_INPUT / "Superior-MI-References"
        target_dir.mkdir(parents=True, exist_ok=True)
        target = target_dir / src.name
        if not target.exists() or target.stat().st_size != src.stat().st_size:
            shutil.copy2(src, target)
        image_rel = str((Path("Superior-MI-References") / target.name).as_posix())

        wf = mode_blueprint(mode)
        load_id = next((key for key, node in wf.items() if node.get("class_type") == "LoadImage"), None)
        encode_id = next((key for key, node in wf.items() if node.get("class_type") == "TextEncodeQwenImage21"), None)
        sampler_id = next((key for key, node in wf.items() if node.get("class_type") == "KSampler"), None)
        save_id = next((key for key, node in wf.items() if node.get("class_type") == "SaveImage"), None)
        if not all((load_id, encode_id, sampler_id, save_id)):
            raise RuntimeError("Qwen reference Blueprint is incomplete.")

        wf[load_id]["inputs"]["image"] = image_rel
        wf[encode_id]["inputs"]["prompt"] = (
            "Use <image1> as a visual reference. Preserve relevant visual identity, "
            "shape, color, and design details from the reference while following this request: "
            + prompt
        )
        target_profile = _dimensions(orientation, quality, video=False)
        wf[encode_id]["inputs"]["resolution"] = max(target_profile[0], target_profile[1])
        wf[sampler_id]["inputs"]["steps"] = target_profile[2]
        wf[save_id]["inputs"]["filename_prefix"] = (
            f"SuperiorMI/Create/QwenReference/{datetime.now():%Y%m%d_%H%M%S}"
        )
        return wf

    if mode == "Text Image (FLUX.2 Klein 4B)":
        w, h, _steps = _dimensions(orientation, quality, video=False)
        # FLUX Klein distilled stays at its intended 4-step schedule.
        wf = mode_blueprint(mode)
        wf["4"]["inputs"]["text"] = prompt
        wf["6"]["inputs"].update({"width": w, "height": h, "batch_size": 1})
        wf["10"]["inputs"].update({"width": w, "height": h, "steps": 4})
        wf["13"]["inputs"]["filename_prefix"] = f"SuperiorMI/Create/FLUX/{datetime.now():%Y%m%d_%H%M%S}"
        return wf

    if mode == "Text Image (Qwen Image 2.1)":
        w, h, steps = _dimensions(orientation, quality, video=False)
        wf = mode_blueprint(mode)
        wf["4"]["inputs"].update({"prompt": prompt, "resolution": max(w, h)})
        wf["5"]["inputs"].update({"width": w, "height": h, "batch_size": 1})
        wf["7"]["inputs"]["steps"] = steps
        wf["9"]["inputs"]["filename_prefix"] = f"SuperiorMI/Create/Qwen/{datetime.now():%Y%m%d_%H%M%S}"
        return wf

    if mode == "Video from Image (Wan2.2 TI2V 5B)":
        if not source_image:
            raise ValueError("Choose a source image before creating a video.")
        src = Path(source_image).expanduser()
        if not src.exists() or not src.is_file():
            raise FileNotFoundError(f"Source image not found: {src}")
        # Copy into ComfyUI/input under a stable Workstation subfolder.
        target_dir = COMFY_INPUT / "Superior-MI-Video-Sources"
        target_dir.mkdir(parents=True, exist_ok=True)
        target = target_dir / src.name
        if not target.exists() or target.stat().st_size != src.stat().st_size:
            shutil.copy2(src, target)
        rel = str((Path("Superior-MI-Video-Sources") / target.name).as_posix())

        w, h, frames, steps = _dimensions(orientation, quality, video=True)
        wf = mode_blueprint(mode)
        wf["4"]["inputs"]["text"] = prompt
        # The I2V blueprint always binds a real media input before queueing.
        load_id = next((k for k,v in wf.items() if v.get("class_type")=="LoadImage"), None)
        if not load_id:
            raise RuntimeError("Wan I2V blueprint does not contain a LoadImage node.")
        wf[load_id]["inputs"]["image"] = rel
        latent_id = next((k for k,v in wf.items() if v.get("class_type")=="Wan22ImageToVideoLatent"), None)
        sampler_id = next((k for k,v in wf.items() if v.get("class_type")=="KSampler"), None)
        save_id = next((k for k,v in wf.items() if v.get("class_type")=="SaveVideo"), None)
        if not all((latent_id,sampler_id,save_id)):
            raise RuntimeError("Wan I2V blueprint is incomplete.")
        wf[latent_id]["inputs"].update({"width": w, "height": h, "length": frames, "batch_size": 1})
        wf[sampler_id]["inputs"]["steps"] = steps
        wf[save_id]["inputs"]["filename_prefix"] = f"SuperiorMI/Create/Wan/{datetime.now():%Y%m%d_%H%M%S}"
        return wf

    raise RuntimeError("Creation mode is not implemented.")


def save_workflow(workflow: dict, label: str) -> Path:
    day = GENERATED_ROOT / datetime.now().strftime("%Y-%m-%d")
    day.mkdir(parents=True, exist_ok=True)
    path = day / f"{datetime.now():%H%M%S}_{_safe_prefix(label)}.json"
    path.write_text(json.dumps(workflow, indent=2) + "\n", encoding="utf-8")
    return path


def validate_node_types(workflow: dict, base_url: str, timeout: float = 3.0) -> list[str]:
    req = urllib.request.Request(base_url.rstrip("/") + "/object_info", headers={"User-Agent": "Superior-MI-Labs-ComfyUI-Workstation"})
    with urllib.request.urlopen(req, timeout=timeout) as response:
        info = json.loads(response.read().decode("utf-8"))
    needed = sorted({str(node.get("class_type")) for node in workflow.values() if isinstance(node, dict) and node.get("class_type")})
    return [name for name in needed if name not in info]


def queue_workflow(workflow: dict, base_url: str, timeout: float = 8.0) -> str:
    missing = validate_node_types(workflow, base_url, timeout=min(timeout, 4.0))
    if missing:
        raise RuntimeError("ComfyUI is missing workflow node types:\n" + "\n".join(missing))
    payload = json.dumps({"prompt": workflow}).encode("utf-8")
    req = urllib.request.Request(
        base_url.rstrip("/") + "/prompt",
        data=payload,
        headers={"Content-Type": "application/json", "User-Agent": "Superior-MI-Labs-ComfyUI-Workstation"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=timeout) as response:
            data = json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        body = exc.read().decode("utf-8", "replace")
        raise RuntimeError(f"ComfyUI rejected the workflow (HTTP {exc.code}):\n{body[:4000]}") from exc
    return str(data.get("prompt_id") or data)
