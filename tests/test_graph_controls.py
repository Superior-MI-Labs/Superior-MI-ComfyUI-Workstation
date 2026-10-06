from pathlib import Path
import sys

APP = Path(__file__).resolve().parents[1] / "app"
sys.path.insert(0, str(APP))

from core.graph_controls import derive_graph_controls


def _fixture():
    prompt = {
        "1": {
            "class_type": "Sampler",
            "inputs": {
                "model": ["0", 0],
                "steps": 24,
                "cfg": 3.5,
                "sampler_name": "euler",
                "seed": 1234,
            },
        },
        "2": {
            "class_type": "Latent",
            "inputs": {"width": 1024, "height": 1024, "batch_size": 1},
        },
        "3": {
            "class_type": "Text",
            "inputs": {"prompt": "a lighthouse at night"},
        },
    }
    info = {
        "Sampler": {
            "input": {
                "required": {
                    "model": ["MODEL", {}],
                    "steps": ["INT", {"min": 1, "max": 100, "step": 1}],
                    "cfg": ["FLOAT", {"min": 0.0, "max": 20.0, "step": 0.1}],
                    "sampler_name": [["euler", "dpmpp_2m"], {}],
                    "seed": ["INT", {"min": 0, "max": 999999999}],
                }
            }
        },
        "Latent": {
            "input": {
                "required": {
                    "width": ["INT", {"min": 64, "max": 4096, "step": 64}],
                    "height": ["INT", {"min": 64, "max": 4096, "step": 64}],
                    "batch_size": ["INT", {"min": 1, "max": 16}],
                }
            }
        },
        "Text": {
            "input": {
                "required": {
                    "prompt": ["STRING", {"multiline": True}],
                }
            }
        },
    }
    return prompt, info


def test_controls_are_derived_from_live_graph_schema():
    prompt, info = _fixture()
    registry = derive_graph_controls(prompt, info)
    controls = registry.by_id()

    assert "1.model" not in controls  # connected socket, not a scalar Workstation control
    assert controls["1.steps"].widget == "slider-number"
    assert controls["1.steps"].minimum == 1
    assert controls["1.steps"].maximum == 100
    assert controls["1.sampler_name"].widget == "dropdown"
    assert controls["1.sampler_name"].choices == ("euler", "dpmpp_2m")
    assert controls["3.prompt"].widget == "multiline"
    assert controls["2.width"].group == "Resolution"


def test_registry_applies_only_validated_graph_changes():
    prompt, info = _fixture()
    registry = derive_graph_controls(prompt, info)
    changed = registry.apply(prompt, {
        "1.steps": 32,
        "1.sampler_name": "dpmpp_2m",
        "2.width": 1344,
    })

    assert changed["1"]["inputs"]["steps"] == 32
    assert changed["1"]["inputs"]["sampler_name"] == "dpmpp_2m"
    assert changed["2"]["inputs"]["width"] == 1344
    assert prompt["1"]["inputs"]["steps"] == 24  # source graph was not mutated in place


def test_registry_rejects_invalid_agent_or_ui_values():
    prompt, info = _fixture()
    registry = derive_graph_controls(prompt, info)

    try:
        registry.apply(prompt, {"1.steps": 200})
    except ValueError as exc:
        assert "maximum" in str(exc)
    else:
        raise AssertionError("out-of-range control value was accepted")

    try:
        registry.apply(prompt, {"1.sampler_name": "invented_sampler"})
    except ValueError:
        pass
    else:
        raise AssertionError("unknown combo value was accepted")


def test_blueprint_metadata_can_curate_without_owning_graph_state():
    prompt, info = _fixture()
    registry = derive_graph_controls(
        prompt,
        info,
        presentation={
            "1.cfg": {"label": "Guidance", "group": "Quality", "priority": "primary"},
            "2.batch_size": {"hidden": True},
        },
    )
    controls = registry.by_id()

    assert controls["1.cfg"].label == "Guidance"
    assert controls["1.cfg"].group == "Quality"
    assert controls["1.cfg"].value == 3.5
    assert controls["2.batch_size"].priority == "hidden"
