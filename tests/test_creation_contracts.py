from pathlib import Path
import json
import sys

ROOT = Path(__file__).resolve().parents[1]
APP = ROOT / "app"
sys.path.insert(0, str(APP))

import creation_helper
import comfy_integration

def test_qwen_reference_blueprints_use_v3_autogrow_paths():
    bad = []
    for path in (ROOT / "preset_library" / "Character" / "Qwen-Image-2.1").glob("*.json"):
        data = json.loads(path.read_text())
        for node_id, node in data.items():
            if not isinstance(node, dict) or node.get("class_type") != "TextEncodeQwenImage21":
                continue
            for name in (node.get("inputs") or {}):
                if name.startswith("image_"):
                    bad.append((path.name, node_id, name))
    assert not bad, bad

def test_character_control_is_graph_derived():
    caps = creation_helper.mode_capabilities("Character Image (Qwen Image 2.1)")
    assert caps["character"] is True
    assert caps["reference_slots"] >= 1
    assert caps["source_image"] is False
    # Its latent geometry follows image_1, so arbitrary format selection is hidden.
    assert caps["format"] is False

def test_text_modes_do_not_offer_character_control():
    assert creation_helper.mode_capabilities("Text Image (Qwen Image 2.1)")["character"] is False
    assert creation_helper.mode_capabilities("Text Image (FLUX.2 Klein 4B)")["character"] is False

def test_wan_i2v_offers_source_image_not_character():
    caps = creation_helper.mode_capabilities("Video from Image (Wan2.2 TI2V 5B)")
    assert caps["source_image"] is True
    assert caps["character"] is False
    assert caps["format"] is True

def test_runtime_adapter_rewrites_legacy_qwen_autogrow_input():
    prompt = {
        "10": {"class_type": "LoadImage", "inputs": {"image": "Kisha.png"}},
        "4": {
            "class_type": "TextEncodeQwenImage21",
            "inputs": {
                "clip": ["2", 0],
                "prompt": "Use <image1>",
                "negative_prompt": "",
                "resolution": 768,
                "vae": ["3", 0],
                "image_1": ["10", 0],
            },
        },
    }
    info = {
        "LoadImage": {
            "input": {"required": {"image": [["Kisha.png"], {}]}},
        },
        "TextEncodeQwenImage21": {
            "input": {
                "required": {
                    "clip": ["CLIP", {}],
                    "prompt": ["STRING", {}],
                    "negative_prompt": ["STRING", {}],
                    "resolution": ["INT", {}],
                    "images": [
                        "COMFY_AUTOGROW_V3",
                        {
                            "template": {
                                "names": ["image_1", "image_2"],
                                "min": 0,
                                "input": {"required": {"image": ["IMAGE", {}]}},
                            }
                        },
                    ],
                },
                "optional": {"vae": ["VAE", {}]},
            },
        },
    }
    fixed = comfy_integration.adapt_api_prompt(prompt, info)
    inputs = fixed["4"]["inputs"]
    assert "image_1" not in inputs
    assert inputs["images.image_1"] == ["10", 0]

def test_runtime_adapter_rejects_unknown_keyword_before_execute():
    prompt = {"1": {"class_type": "NodeX", "inputs": {"wrong": 1}}}
    info = {"NodeX": {"input": {"required": {"right": ["INT", {}]}}}}
    try:
        comfy_integration.adapt_api_prompt(prompt, info)
    except RuntimeError as exc:
        assert "wrong" in str(exc)
    else:
        raise AssertionError("unknown node input was not rejected")
