from pathlib import Path
import json
import sys
import tempfile

APP = Path(__file__).resolve().parents[1] / "app"
sys.path.insert(0, str(APP))

from adapters.comfy_cli import load_trusted_asset_registry
from core.registry import load_capability_registry, load_implementation_registry


ROOT = Path(__file__).resolve().parents[1]


def test_production_capability_catalog_is_semantic_and_character_free():
    registry = load_capability_registry(ROOT / "catalog" / "r1" / "capabilities.json")
    ids = registry.by_id()

    assert "image.generate" in ids
    assert "image.reference" in ids
    assert "video.image_to_video" in ids
    assert all("character" not in capability_id.lower() for capability_id in ids)


def test_implementation_registry_loads_typed_candidates_without_code_mappings():
    payload = {
        "schema_version": 1,
        "implementations": [
            {
                "id": "example-cuda",
                "title": "Example CUDA",
                "capabilities": ["image.generate"],
                "backend": "cuda",
                "platforms": ["linux"],
                "architectures": ["x86_64"],
                "min_vram_bytes": 8589934592,
                "assets": [{"id": "model.example", "size_bytes": 1000}],
                "packages": ["node.example"],
                "blueprint_id": "example.basic",
                "stability": "qualified",
                "evidence_score": 80,
                "preference_scores": {"quality": 90, "speed": 70},
            }
        ],
    }
    with tempfile.TemporaryDirectory() as td:
        path = Path(td) / "implementations.json"
        path.write_text(json.dumps(payload), encoding="utf-8")
        registry = load_implementation_registry(path)

    candidate = registry.by_id()["example-cuda"]
    assert candidate.backend == "cuda"
    assert candidate.capabilities == ("image.generate",)
    assert candidate.assets[0].id == "model.example"
    assert candidate.preference_scores["quality"] == 90


def test_registry_rejects_duplicate_identity():
    payload = {
        "implementations": [
            {"id": "same", "title": "One", "capabilities": ["image.generate"]},
            {"id": "same", "title": "Two", "capabilities": ["image.generate"]},
        ]
    }
    with tempfile.TemporaryDirectory() as td:
        path = Path(td) / "implementations.json"
        path.write_text(json.dumps(payload), encoding="utf-8")
        try:
            load_implementation_registry(path)
        except ValueError as exc:
            assert "unique" in str(exc)
        else:
            raise AssertionError("duplicate implementation identity was accepted")



def test_production_r1_catalog_is_referentially_complete():
    capabilities = load_capability_registry(ROOT / "catalog" / "r1" / "capabilities.json")
    implementations = load_implementation_registry(ROOT / "catalog" / "r1" / "implementations.json")
    assets = load_trusted_asset_registry(ROOT / "catalog" / "r1" / "assets.json")
    preset_payload = json.loads((ROOT / "preset_library" / "index.json").read_text(encoding="utf-8"))
    blueprint_ids = {entry["id"] for entry in preset_payload["presets"]}

    capability_ids = set(capabilities.by_id())
    assert implementations.entries

    for candidate in implementations.entries:
        assert set(candidate.capabilities) <= capability_ids
        assert candidate.blueprint_id in blueprint_ids
        assert candidate.min_vram_bytes == 0
        assert candidate.recommended_vram_bytes > 0
        for asset in candidate.assets:
            assert asset.id in assets

    assert all(asset.url.startswith("https://huggingface.co/") for asset in assets.values())


def test_qwen_license_review_is_retained_in_production_catalog():
    implementations = load_implementation_registry(ROOT / "catalog" / "r1" / "implementations.json")
    qwen = [
        candidate for candidate in implementations.entries
        if candidate.id.startswith("qwen-image-2.1-convrot.")
    ]
    assert qwen
    assert all(candidate.license_status == "acknowledgement" for candidate in qwen)
