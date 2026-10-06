from pathlib import Path
import sys

APP = Path(__file__).resolve().parents[1] / "app"
sys.path.insert(0, str(APP))

from core.contracts import (
    ActionPlan,
    CapabilityRequest,
    GPUProfile,
    HardwareProfile,
    PlanAction,
)


def test_hardware_is_typed_data_not_ui_state():
    hw = HardwareProfile(
        platform="linux",
        architecture="x86_64",
        cpu_model="Example CPU",
        logical_cpu_count=16,
        memory_total_bytes=32 * 1024**3,
        gpus=(GPUProfile(vendor="NVIDIA", model="Example GPU", vram_bytes=12 * 1024**3, backend_candidates=("cuda",)),),
    )
    assert hw.gpus[0].vram_bytes == 12 * 1024**3
    assert hw.gpus[0].backend_candidates == ("cuda",)


def test_capability_request_does_not_depend_on_ai_provider():
    request = CapabilityRequest(
        capabilities=("image.generate", "video.image_to_video"),
        local_only=True,
        quality_priority="quality",
    )
    assert request.capabilities == ("image.generate", "video.image_to_video")
    assert request.local_only is True


def test_action_plan_reports_approval_boundary():
    plan = ActionPlan(
        id="plan-1",
        title="Prepare image workflow",
        actions=(
            PlanAction(id="inspect", kind="inspect", title="Inspect runtime"),
            PlanAction(id="download", kind="download_asset", title="Download model", requires_approval=True),
        ),
    )
    assert plan.requires_approval is True
