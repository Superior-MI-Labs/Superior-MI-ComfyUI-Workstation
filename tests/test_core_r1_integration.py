from pathlib import Path
import sys

APP = Path(__file__).resolve().parents[1] / "app"
sys.path.insert(0, str(APP))

from core.assistant import AssistantService, build_assistant_context
from core.contracts import (
    AssetRequirement,
    CapabilityDefinition,
    GPUProfile,
    HardwareProfile,
    ImplementationCandidate,
    InstalledInventory,
    RuntimeProfile,
    StorageProfile,
)
from core.executor import PlanExecutor, approval_for
from core.graph_controls import derive_graph_controls
from core.journal import MemoryExecutionJournal
from core.registry import CapabilityRegistry
from core.resolver import resolve_capabilities


GIB = 1024**3


class IntentProvider:
    def propose(self, user_text, context):
        assert "image.generate" in context["capability_ids"]
        return {
            "kind": "capability_request",
            "capabilities": ["image.generate"],
            "local_only": True,
            "quality_priority": "quality",
            "message": "Use the qualified local image capability.",
        }


class EventRuntime:
    def __init__(self, events):
        self.events = events

    def prepare(self, backend):
        self.events.append(("runtime.prepare", backend))
        return f"prepared:{backend}"

    def restart(self):
        self.events.append(("runtime.restart", None))
        return "restarted"


class EventPackages:
    def __init__(self, events):
        self.events = events

    def install(self, package_id):
        self.events.append(("package.install", package_id))
        return f"installed:{package_id}"


class EventAssets:
    def __init__(self, events, *, fail_once=False):
        self.events = events
        self.fail_once = fail_once

    def download(self, asset_id):
        self.events.append(("asset.download", asset_id))
        if self.fail_once:
            self.fail_once = False
            raise RuntimeError("injected asset failure")
        return f"downloaded:{asset_id}"


class EventWorkflow:
    def __init__(self, events):
        self.events = events

    def load_blueprint(self, blueprint_id):
        self.events.append(("workflow.load", blueprint_id))
        return f"loaded:{blueprint_id}"

    def validate(self):
        self.events.append(("workflow.validate", None))
        return "validated"


def fixture_state():
    capabilities = CapabilityRegistry((
        CapabilityDefinition(
            id="image.generate",
            title="Generate Image",
            output_media=("image",),
        ),
    ))
    hardware = HardwareProfile(
        platform="linux",
        architecture="x86_64",
        memory_total_bytes=32 * GIB,
        gpus=(
            GPUProfile(
                vendor="NVIDIA",
                model="Example GPU",
                vram_bytes=12 * GIB,
                backend_candidates=("cuda",),
            ),
        ),
        storage=(StorageProfile(path="/models", free_bytes=100 * GIB),),
    )
    runtime = RuntimeProfile(compute_backend="cpu")
    candidate = ImplementationCandidate(
        id="image-qualified",
        title="Qualified Image Stack",
        capabilities=("image.generate",),
        backend="cuda",
        platforms=("linux",),
        architectures=("x86_64",),
        min_vram_bytes=8 * GIB,
        assets=(AssetRequirement(id="model.image", size_bytes=4 * GIB),),
        packages=("comfyui-example",),
        blueprint_id="image.basic",
        stability="qualified",
        evidence_score=100,
        preference_scores={"quality": 100},
    )
    return capabilities, hardware, runtime, candidate


def test_conversation_to_approved_setup_is_one_authority_chain():
    capabilities, hardware, runtime, candidate = fixture_state()

    context = build_assistant_context(
        capabilities,
        hardware=hardware,
        runtime=runtime,
    )
    proposal = AssistantService(IntentProvider()).propose(
        "I want to make high quality images locally.",
        context,
    )
    assert proposal.capability_request is not None

    resolution = resolve_capabilities(
        proposal.capability_request,
        hardware,
        runtime,
        InstalledInventory(),
        [candidate],
    )
    assert resolution.resolved
    assert resolution.plan is not None

    kinds = [action.kind for action in resolution.plan.actions]
    assert kinds == [
        "inspect_hardware",
        "inspect_runtime",
        "prepare_runtime",
        "install_package",
        "download_asset",
        "restart_runtime",
        "load_blueprint",
        "validate_workflow",
    ]

    required = {
        action.id for action in resolution.plan.actions if action.requires_approval
    }
    approval = approval_for(resolution.plan, required)

    events = []
    result = PlanExecutor(
        runtime_service=EventRuntime(events),
        package_service=EventPackages(events),
        asset_service=EventAssets(events),
        workflow_service=EventWorkflow(events),
    ).execute(resolution.plan, approval)

    assert result.completed
    assert events == [
        ("runtime.prepare", "cuda"),
        ("package.install", "comfyui-example"),
        ("asset.download", "model.image"),
        ("runtime.restart", None),
        ("workflow.load", "image.basic"),
        ("workflow.validate", None),
    ]


def test_resolved_plan_recovers_after_injected_failure_without_replaying_success():
    capabilities, hardware, runtime, candidate = fixture_state()
    proposal = AssistantService(IntentProvider()).propose(
        "make an image",
        build_assistant_context(capabilities, hardware=hardware, runtime=runtime),
    )
    resolution = resolve_capabilities(
        proposal.capability_request,
        hardware,
        runtime,
        InstalledInventory(),
        [candidate],
    )
    assert resolution.plan is not None

    approval = approval_for(
        resolution.plan,
        {action.id for action in resolution.plan.actions if action.requires_approval},
    )
    journal = MemoryExecutionJournal()
    events = []
    assets = EventAssets(events, fail_once=True)

    first = PlanExecutor(
        journal=journal,
        runtime_service=EventRuntime(events),
        package_service=EventPackages(events),
        asset_service=assets,
        workflow_service=EventWorkflow(events),
    ).execute(resolution.plan, approval)

    assert first.failed
    assert ("runtime.restart", None) not in events
    assert ("workflow.load", "image.basic") not in events

    events.clear()
    second = PlanExecutor(
        journal=journal,
        runtime_service=EventRuntime(events),
        package_service=EventPackages(events),
        asset_service=assets,
        workflow_service=EventWorkflow(events),
    ).execute(resolution.plan, approval)

    assert second.completed
    assert events == [
        ("asset.download", "model.image"),
        ("runtime.restart", None),
        ("workflow.load", "image.basic"),
        ("workflow.validate", None),
    ]


def test_imported_workflow_projects_controls_without_becoming_graph_owner():
    prompt = {
        "1": {
            "class_type": "CheckpointLoader",
            "inputs": {"ckpt_name": "example.safetensors"},
        },
        "2": {
            "class_type": "KSampler",
            "inputs": {
                "model": ["1", 0],
                "steps": 24,
                "cfg": 3.5,
                "sampler_name": "euler",
                "seed": 42,
            },
        },
        "3": {
            "class_type": "EmptyLatentImage",
            "inputs": {"width": 1024, "height": 1024, "batch_size": 1},
        },
        "4": {
            "class_type": "ThirdPartyNode",
            "inputs": {"opaque_magic": "keep me"},
        },
    }
    object_info = {
        "CheckpointLoader": {
            "input": {
                "required": {
                    "ckpt_name": [["example.safetensors", "other.safetensors"], {}],
                }
            }
        },
        "KSampler": {
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
        "EmptyLatentImage": {
            "input": {
                "required": {
                    "width": ["INT", {"min": 64, "max": 4096, "step": 64}],
                    "height": ["INT", {"min": 64, "max": 4096, "step": 64}],
                    "batch_size": ["INT", {"min": 1, "max": 16}],
                }
            }
        },
        "ThirdPartyNode": {
            "input": {
                "required": {
                    "different_input": ["STRING", {}],
                }
            }
        },
    }

    registry = derive_graph_controls(prompt, object_info)
    controls = registry.by_id()

    assert "2.model" not in controls
    assert controls["2.steps"].widget == "slider-number"
    assert controls["2.sampler_name"].widget == "dropdown"
    assert controls["3.width"].group == "Resolution"
    assert controls["4.opaque_magic"].editable is False

    changed = registry.apply(
        prompt,
        {
            "2.steps": 32,
            "2.sampler_name": "dpmpp_2m",
            "3.width": 1344,
        },
    )
    assert changed["2"]["inputs"]["steps"] == 32
    assert changed["2"]["inputs"]["sampler_name"] == "dpmpp_2m"
    assert changed["3"]["inputs"]["width"] == 1344

    # Projection returned a new prompt. The source graph snapshot was not
    # mutated into a second hidden Workstation-owned value store.
    assert prompt["2"]["inputs"]["steps"] == 24
    assert prompt["3"]["inputs"]["width"] == 1024
