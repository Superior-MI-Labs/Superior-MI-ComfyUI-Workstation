from pathlib import Path
import sys

APP = Path(__file__).resolve().parents[1] / "app"
sys.path.insert(0, str(APP))

from core.contracts import (
    AssetRequirement,
    CapabilityRequest,
    GPUProfile,
    HardwareProfile,
    ImplementationCandidate,
    InstalledInventory,
    RuntimeProfile,
    StorageProfile,
)
from core.resolver import assess_candidate, resolve_capabilities


GIB = 1024**3


def hardware(
    *,
    vendor="NVIDIA",
    backend_candidates=("cuda",),
    vram_gib=16,
    ram_gib=32,
    free_gib=200,
):
    gpus = ()
    if vendor:
        gpus = (
            GPUProfile(
                vendor=vendor,
                model=f"{vendor} Example",
                vram_bytes=vram_gib * GIB,
                backend_candidates=backend_candidates,
            ),
        )
    return HardwareProfile(
        platform="linux",
        architecture="x86_64",
        memory_total_bytes=ram_gib * GIB,
        gpus=gpus,
        storage=(StorageProfile(path="/models", free_bytes=free_gib * GIB),),
    )


def runtime(backend="cuda"):
    return RuntimeProfile(compute_backend=backend)


def candidate(
    cid,
    *capabilities,
    backend="cuda",
    min_vram_gib=0,
    download_gib=0,
    package="",
    blueprint="",
    quality=0,
    evidence=0,
    stability="stable",
    license_status="open",
):
    assets = ()
    if download_gib:
        assets = (AssetRequirement(id=f"{cid}.model", size_bytes=download_gib * GIB),)
    packages = (package,) if package else ()
    return ImplementationCandidate(
        id=cid,
        title=cid,
        capabilities=tuple(capabilities),
        backend=backend,
        platforms=("linux",),
        architectures=("x86_64",),
        min_vram_bytes=min_vram_gib * GIB,
        assets=assets,
        packages=packages,
        blueprint_id=blueprint,
        preference_scores={"quality": quality, "balanced": quality},
        evidence_score=evidence,
        stability=stability,
        license_status=license_status,
    )


def assessment_map(result):
    return {row.candidate_id: row for row in result.assessments}


def test_ready_candidate_is_selected_without_mutating_anything():
    request = CapabilityRequest(("image.generate",), quality_priority="quality")
    impl = candidate("flux", "image.generate", quality=10, evidence=10)
    result = resolve_capabilities(request, hardware(), runtime(), InstalledInventory(), [impl])

    assert result.resolved
    assert result.selected_candidate_ids == ("flux",)
    assert assessment_map(result)["flux"].status == "ready"
    assert result.plan is not None
    assert [action.kind for action in result.plan.actions] == [
        "inspect_hardware",
        "inspect_runtime",
        "validate_workflow",
    ]
    assert result.plan.requires_approval is False


def test_missing_assets_and_packages_produce_approval_gated_checklist():
    request = CapabilityRequest(("image.generate",), quality_priority="quality")
    impl = candidate(
        "flux",
        "image.generate",
        download_gib=8,
        package="comfy.example",
        blueprint="flux.basic",
        quality=10,
    )
    result = resolve_capabilities(request, hardware(), runtime(), InstalledInventory(), [impl])

    row = assessment_map(result)["flux"]
    assert row.status == "setup_required"
    assert row.required_download_bytes == 8 * GIB

    assert result.plan is not None
    kinds = [action.kind for action in result.plan.actions]
    assert kinds == [
        "inspect_hardware",
        "inspect_runtime",
        "install_package",
        "download_asset",
        "load_blueprint",
        "validate_workflow",
    ]
    assert result.plan.requires_approval is True


def test_existing_assets_and_packages_are_reused_not_reinstalled():
    request = CapabilityRequest(("image.generate",))
    impl = candidate(
        "flux",
        "image.generate",
        download_gib=8,
        package="comfy.example",
        blueprint="flux.basic",
    )
    inventory = InstalledInventory(
        asset_ids=frozenset({"flux.model"}),
        package_ids=frozenset({"comfy.example"}),
    )
    result = resolve_capabilities(request, hardware(), runtime(), inventory, [impl])

    row = assessment_map(result)["flux"]
    assert row.required_download_bytes == 0
    assert row.reused_assets == ("flux.model",)
    assert result.plan is not None
    kinds = [action.kind for action in result.plan.actions]
    assert "download_asset" not in kinds
    assert "install_package" not in kinds


def test_gpu_candidate_can_be_viable_after_runtime_setup():
    request = CapabilityRequest(("image.generate",), quality_priority="quality")
    gpu = candidate("gpu", "image.generate", quality=100)
    cpu = candidate("cpu", "image.generate", backend="cpu", quality=10)

    result = resolve_capabilities(
        request,
        hardware(),
        runtime("cpu"),
        InstalledInventory(),
        [cpu, gpu],
    )

    rows = assessment_map(result)
    assert rows["gpu"].status == "setup_required"
    assert result.selected_candidate_ids == ("gpu",)
    assert result.plan is not None
    assert any(action.kind == "prepare_runtime" for action in result.plan.actions)


def test_wrong_hardware_backend_is_rejected_with_reason():
    request = CapabilityRequest(("image.generate",))
    cuda = candidate("cuda-only", "image.generate", backend="cuda")

    result = resolve_capabilities(
        request,
        hardware(vendor="AMD", backend_candidates=("rocm",)),
        runtime("rocm"),
        InstalledInventory(),
        [cuda],
    )

    row = assessment_map(result)["cuda-only"]
    assert row.status == "rejected"
    assert "not compatible with observed hardware" in row.rejection_reasons[0]
    assert result.unresolved_capabilities == ("image.generate",)
    assert result.plan is None


def test_insufficient_vram_is_a_hard_rejection():
    request = CapabilityRequest(("video.generate",))
    big = candidate("big-video", "video.generate", min_vram_gib=12)

    result = resolve_capabilities(
        request,
        hardware(vram_gib=8),
        runtime(),
        InstalledInventory(),
        [big],
    )

    row = assessment_map(result)["big-video"]
    assert row.status == "rejected"
    assert any("below required" in reason for reason in row.rejection_reasons)


def test_unknown_vram_requires_setup_verification_not_fake_compatibility():
    request = CapabilityRequest(("video.generate",))
    big = candidate("video", "video.generate", min_vram_gib=12)

    result = resolve_capabilities(
        request,
        hardware(vram_gib=0),
        runtime(),
        InstalledInventory(),
        [big],
    )

    row = assessment_map(result)["video"]
    assert row.status == "setup_required"
    assert "GPU VRAM could not be verified for this backend." in row.setup_reasons


def test_storage_budget_and_observed_free_space_are_hard_constraints():
    request = CapabilityRequest(("image.generate",), storage_budget_bytes=4 * GIB)
    impl = candidate("large", "image.generate", download_gib=8)

    result = resolve_capabilities(
        request,
        hardware(free_gib=6),
        runtime(),
        InstalledInventory(),
        [impl],
    )

    reasons = assessment_map(result)["large"].rejection_reasons
    assert any("storage budget" in reason for reason in reasons)
    assert any("free storage" in reason for reason in reasons)


def test_multi_capability_candidate_can_cover_request_without_duplicate_installs():
    request = CapabilityRequest(
        ("image.generate", "image.edit"),
        quality_priority="quality",
    )
    bundle = candidate(
        "bundle",
        "image.generate",
        "image.edit",
        download_gib=9,
        quality=20,
        evidence=10,
    )
    image = candidate("image", "image.generate", download_gib=6, quality=10, evidence=10)
    edit = candidate("edit", "image.edit", download_gib=6, quality=10, evidence=10)

    result = resolve_capabilities(
        request,
        hardware(),
        runtime(),
        InstalledInventory(),
        [edit, image, bundle],
    )

    assert result.resolved
    assert result.selected_candidate_ids == ("bundle",)


def test_resolver_never_adds_redundant_candidate_for_score_padding():
    request = CapabilityRequest(("image.generate",), quality_priority="quality")
    a = candidate("a", "image.generate", quality=10, evidence=10)
    b = candidate("b", "image.generate", quality=9, evidence=100)

    result = resolve_capabilities(
        request,
        hardware(),
        runtime(),
        InstalledInventory(),
        [a, b],
    )

    assert len(result.selected_candidate_ids) == 1


def test_mixed_gpu_backend_plan_is_not_silently_constructed():
    request = CapabilityRequest(("image.generate", "video.generate"))
    cuda_image = candidate("cuda-image", "image.generate", backend="cuda", quality=10)
    rocm_video = candidate("rocm-video", "video.generate", backend="rocm", quality=10)

    dual = HardwareProfile(
        platform="linux",
        architecture="x86_64",
        memory_total_bytes=32 * GIB,
        gpus=(
            GPUProfile(vendor="NVIDIA", model="N", vram_bytes=16 * GIB, backend_candidates=("cuda",)),
            GPUProfile(vendor="AMD", model="A", vram_bytes=16 * GIB, backend_candidates=("rocm",)),
        ),
        storage=(StorageProfile(path="/models", free_bytes=200 * GIB),),
    )
    result = resolve_capabilities(
        request,
        dual,
        runtime("cuda"),
        InstalledInventory(),
        [cuda_image, rocm_video],
    )

    assert not result.resolved
    assert result.plan is None


def test_license_review_is_explicit_and_never_silent():
    request = CapabilityRequest(("image.generate",))
    gated = candidate(
        "gated",
        "image.generate",
        license_status="acknowledgement",
    )

    result = resolve_capabilities(
        request,
        hardware(),
        runtime(),
        InstalledInventory(),
        [gated],
    )

    assert result.plan is not None
    license_actions = [action for action in result.plan.actions if action.kind == "review_license"]
    assert len(license_actions) == 1
    assert license_actions[0].requires_approval is True


def test_resolution_is_deterministic_and_candidate_ids_must_be_unique():
    request = CapabilityRequest(("image.generate",))
    a = candidate("a", "image.generate", quality=10)
    b = candidate("b", "image.generate", quality=10)

    first = resolve_capabilities(request, hardware(), runtime(), InstalledInventory(), [b, a])
    second = resolve_capabilities(request, hardware(), runtime(), InstalledInventory(), [a, b])
    assert first.selected_candidate_ids == second.selected_candidate_ids == ("a",)

    try:
        resolve_capabilities(request, hardware(), runtime(), InstalledInventory(), [a, a])
    except ValueError as exc:
        assert "unique" in str(exc)
    else:
        raise AssertionError("duplicate candidate IDs were accepted")
