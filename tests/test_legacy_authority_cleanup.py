from pathlib import Path
from types import SimpleNamespace
from unittest import mock
import json
import sys

ROOT = Path(__file__).resolve().parents[1]
APP = ROOT / "app"
sys.path.insert(0, str(APP))

import setup_helper
import stack_manager
from core.contracts import GPUProfile, HardwareProfile, RuntimeProfile


def test_family_stack_mapping_is_deleted_from_python():
    source = (APP / "blueprint_manager.py").read_text(encoding="utf-8")
    main = (APP / "main.py").read_text(encoding="utf-8")
    assert "FAMILY_STACK" not in source
    assert "FAMILY_STACK" not in main


def test_every_manifest_blueprint_has_data_owned_stack_and_capability():
    payload = json.loads((ROOT / "preset_library" / "index.json").read_text(encoding="utf-8"))
    entries = payload["presets"]
    assert entries
    assert all(entry.get("stack_id") for entry in entries)
    assert all(entry.get("capability_id") for entry in entries)
    assert not any(entry.get("category") == "Character" for entry in entries)


def test_pack_catalog_no_longer_exposes_character_as_core_pack():
    payload = json.loads((ROOT / "catalog" / "packs.json").read_text(encoding="utf-8"))
    rendered = json.dumps(payload).lower()
    assert "starter-character" not in rendered
    assert "character creator pack" not in rendered
    assert "canonical characters" not in rendered


def test_legacy_stack_manager_cannot_mutate_custom_nodes_through_git():
    source = (APP / "stack_manager.py").read_text(encoding="utf-8")
    assert '["git","clone"' not in source
    assert '["git","-C"' not in source

    stack = {
        "id": "legacy-custom-node",
        "custom_nodes": [{"repo": "https://example.invalid/repo.git", "folder": "Node"}],
        "assets": [],
    }
    with mock.patch.object(stack_manager, "find_hf", side_effect=AssertionError("must fail before download")):
        try:
            stack_manager.download_stack(stack)
        except RuntimeError as exc:
            assert "direct-Git" in str(exc)
            assert "package service" in str(exc)
        else:
            raise AssertionError("legacy custom-node mutation was not blocked")


def test_legacy_gpu_projection_uses_canonical_r1_observers():
    source = (APP / "setup_helper.py").read_text(encoding="utf-8")
    assert "nvidia-smi" not in source

    hw = HardwareProfile(
        platform="linux",
        architecture="x86_64",
        gpus=(
            GPUProfile(
                vendor="NVIDIA",
                model="Example GPU",
                vram_bytes=16 * 1024**3,
                driver="555.1",
                backend_candidates=("cuda",),
            ),
        ),
    )
    rt = RuntimeProfile(compute_backend="cuda", backend_version="13.0")

    with mock.patch.object(setup_helper, "observe_hardware", return_value=hw), \
         mock.patch.object(setup_helper, "observe_runtime", return_value=rt):
        result = setup_helper.detect_gpu()

    assert result == {
        "vendor": "NVIDIA",
        "name": "Example GPU",
        "vram_gib": 16.0,
        "driver": "555.1",
        "cuda_reported": "13.0",
        "nvidia_ok": True,
    }
