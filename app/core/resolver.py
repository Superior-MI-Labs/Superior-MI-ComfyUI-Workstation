from __future__ import annotations

from dataclasses import dataclass
from fractions import Fraction
from typing import Iterable

from .contracts import (
    ActionPlan,
    CandidateAssessment,
    CapabilityRequest,
    HardwareProfile,
    ImplementationCandidate,
    InstalledInventory,
    PlanAction,
    ResolutionResult,
    RuntimeProfile,
)


_STABILITY = {"experimental": 0, "beta": 1, "stable": 2, "qualified": 3}


def _physical_backends(hardware: HardwareProfile) -> frozenset[str]:
    backends = {"cpu"}
    for gpu in hardware.gpus:
        backends.update(gpu.backend_candidates)
    return frozenset(backends)


def _max_vram_for_backend(hardware: HardwareProfile, backend: str) -> int:
    values = [
        gpu.vram_bytes
        for gpu in hardware.gpus
        if backend in gpu.backend_candidates and gpu.vram_bytes > 0
    ]
    return max(values, default=0)


def assess_candidate(
    request: CapabilityRequest,
    hardware: HardwareProfile,
    runtime: RuntimeProfile,
    inventory: InstalledInventory,
    candidate: ImplementationCandidate,
) -> CandidateAssessment:
    rejection: list[str] = []
    setup: list[str] = []
    warnings: list[str] = []

    requested = set(request.capabilities)
    if not requested.intersection(candidate.capabilities):
        rejection.append("Candidate does not provide any requested capability.")

    if request.local_only and candidate.execution_mode != "local":
        rejection.append("Request requires local execution.")

    if candidate.platforms and hardware.platform not in candidate.platforms:
        rejection.append(
            f"Platform {hardware.platform!r} is not supported; expected one of {candidate.platforms!r}."
        )

    if candidate.architectures and hardware.architecture not in candidate.architectures:
        rejection.append(
            f"Architecture {hardware.architecture!r} is not supported; expected one of {candidate.architectures!r}."
        )

    physical_backends = _physical_backends(hardware)
    if candidate.backend not in physical_backends:
        rejection.append(
            f"Required backend {candidate.backend!r} is not compatible with observed hardware."
        )
    elif candidate.backend != "cpu" and runtime.compute_backend != candidate.backend:
        setup.append(
            f"Runtime backend {candidate.backend!r} must be prepared; current backend is {runtime.compute_backend or 'unknown'!r}."
        )

    observed_vram = 0
    if candidate.backend != "cpu":
        observed_vram = _max_vram_for_backend(hardware, candidate.backend)

    if candidate.min_vram_bytes > 0 and candidate.backend != "cpu":
        if observed_vram == 0:
            setup.append("GPU VRAM could not be verified for this backend.")
        elif observed_vram < candidate.min_vram_bytes:
            rejection.append(
                f"Observed VRAM {observed_vram} bytes is below required {candidate.min_vram_bytes} bytes."
            )

    if (
        candidate.recommended_vram_bytes > 0
        and observed_vram > 0
        and observed_vram < candidate.recommended_vram_bytes
    ):
        warnings.append(
            f"Observed VRAM {observed_vram} bytes is below recommended "
            f"{candidate.recommended_vram_bytes} bytes; offload or smaller settings may be needed."
        )

    if candidate.min_ram_bytes > 0:
        if hardware.memory_total_bytes == 0:
            setup.append("System RAM could not be verified.")
        elif hardware.memory_total_bytes < candidate.min_ram_bytes:
            rejection.append(
                f"Observed RAM {hardware.memory_total_bytes} bytes is below required {candidate.min_ram_bytes} bytes."
            )

    reused_assets = tuple(sorted(asset.id for asset in candidate.assets if asset.id in inventory.asset_ids))
    missing_assets = tuple(asset for asset in candidate.assets if asset.id not in inventory.asset_ids)
    required_download = sum(max(0, asset.size_bytes) for asset in missing_assets)
    if missing_assets:
        setup.append(f"{len(missing_assets)} asset(s) must be downloaded.")

    if request.storage_budget_bytes is not None and required_download > request.storage_budget_bytes:
        rejection.append(
            f"Required download {required_download} bytes exceeds request storage budget {request.storage_budget_bytes} bytes."
        )

    known_free = [storage.free_bytes for storage in hardware.storage if storage.free_bytes > 0]
    if required_download > 0:
        if known_free and max(known_free) < required_download:
            rejection.append(
                f"Required download {required_download} bytes exceeds observed free storage {max(known_free)} bytes."
            )
        elif not known_free:
            setup.append("Free storage could not be verified.")

    missing_packages = tuple(package for package in candidate.packages if package not in inventory.package_ids)
    if missing_packages:
        setup.append(f"{len(missing_packages)} package(s) must be installed.")

    if candidate.license_status in {"acknowledgement", "restricted"}:
        setup.append("License or access terms require explicit user review.")
        warnings.append(f"License status: {candidate.license_status}.")

    if candidate.stability == "experimental":
        warnings.append("Candidate is marked experimental.")

    if rejection:
        status = "rejected"
    elif setup:
        status = "setup_required"
    else:
        status = "ready"

    return CandidateAssessment(
        candidate_id=candidate.id,
        status=status,
        rejection_reasons=tuple(rejection),
        setup_reasons=tuple(setup),
        warnings=tuple(warnings),
        required_download_bytes=required_download,
        reused_assets=reused_assets,
    )


@dataclass(frozen=True)
class _Choice:
    ids: tuple[str, ...]
    mask: int
    backend: str
    setup_count: int
    preference_score: int
    hardware_fit_score: int
    evidence_score: int
    stability_score: int
    required_download_bytes: int
    missing_asset_ids: frozenset[str]


def _choice_key(choice: _Choice) -> tuple:
    # Scores are candidate-level catalog observations. Normalize them so adding
    # more packages cannot improve rank merely by accumulating score.
    count = max(1, len(choice.ids))
    return (
        Fraction(choice.preference_score, count),
        Fraction(choice.hardware_fit_score, count),
        Fraction(choice.evidence_score, count),
        Fraction(choice.stability_score, count),
        -choice.setup_count,
        -choice.required_download_bytes,
        -len(choice.ids),
    )


def _better(candidate: _Choice, current: _Choice | None) -> bool:
    if current is None:
        return True
    left = _choice_key(candidate)
    right = _choice_key(current)
    if left != right:
        return left > right
    return candidate.ids < current.ids


def _hardware_fit_score(hardware: HardwareProfile, candidate: ImplementationCandidate) -> int:
    if candidate.backend == "cpu" or candidate.recommended_vram_bytes <= 0:
        return 0
    observed = _max_vram_for_backend(hardware, candidate.backend)
    if observed <= 0:
        return 0
    return 1 if observed >= candidate.recommended_vram_bytes else -1


def _merge_backend(existing: str, candidate_backend: str) -> str | None:
    if candidate_backend == "cpu":
        return existing
    if not existing:
        return candidate_backend
    if existing == candidate_backend:
        return existing
    # One ComfyUI/PyTorch environment should not silently require two
    # incompatible GPU backend families in one setup plan.
    return None


def _select_candidates(
    request: CapabilityRequest,
    hardware: HardwareProfile,
    inventory: InstalledInventory,
    candidates: tuple[ImplementationCandidate, ...],
    assessments: dict[str, CandidateAssessment],
) -> tuple[str, ...]:
    capabilities = tuple(dict.fromkeys(request.capabilities))
    bit = {capability: 1 << index for index, capability in enumerate(capabilities)}
    full_mask = (1 << len(capabilities)) - 1

    viable = [
        candidate
        for candidate in candidates
        if assessments[candidate.id].status != "rejected"
        and any(capability in bit for capability in candidate.capabilities)
    ]
    viable.sort(key=lambda candidate: candidate.id)

    states: dict[tuple[int, str], _Choice] = {
        (0, ""): _Choice((), 0, "", 0, 0, 0, 0, 0, 0, frozenset())
    }

    for candidate in viable:
        assessment = assessments[candidate.id]
        coverage = 0
        for capability in candidate.capabilities:
            coverage |= bit.get(capability, 0)
        if coverage == 0:
            continue

        snapshot = list(states.items())
        for (_state_key, prior) in snapshot:
            backend = _merge_backend(prior.backend, candidate.backend)
            if backend is None:
                continue
            new_mask = prior.mask | coverage
            if new_mask == prior.mask:
                continue
            ids = tuple(sorted((*prior.ids, candidate.id)))
            missing_assets = tuple(
                asset for asset in candidate.assets if asset.id not in inventory.asset_ids
            )
            incremental_download = sum(
                max(0, asset.size_bytes)
                for asset in missing_assets
                if asset.id not in prior.missing_asset_ids
            )
            missing_asset_ids = prior.missing_asset_ids.union(
                asset.id for asset in missing_assets
            )
            choice = _Choice(
                ids=ids,
                mask=new_mask,
                backend=backend,
                setup_count=prior.setup_count + (1 if assessment.status == "setup_required" else 0),
                preference_score=prior.preference_score
                + int(candidate.preference_scores.get(request.quality_priority, 0)),
                hardware_fit_score=prior.hardware_fit_score + _hardware_fit_score(hardware, candidate),
                evidence_score=prior.evidence_score + max(0, int(candidate.evidence_score)),
                stability_score=prior.stability_score + _STABILITY.get(candidate.stability, 0),
                required_download_bytes=prior.required_download_bytes + incremental_download,
                missing_asset_ids=frozenset(missing_asset_ids),
            )
            key = (new_mask, backend)
            if _better(choice, states.get(key)):
                states[key] = choice

    finals = [choice for (mask, _backend), choice in states.items() if mask == full_mask]
    if not finals:
        return ()
    best = finals[0]
    for choice in finals[1:]:
        if _better(choice, best):
            best = choice
    return best.ids


def _build_plan(
    request: CapabilityRequest,
    runtime: RuntimeProfile,
    inventory: InstalledInventory,
    selected: tuple[ImplementationCandidate, ...],
    assessments: dict[str, CandidateAssessment],
) -> ActionPlan:
    actions: list[PlanAction] = [
        PlanAction(
            id="inspect.hardware",
            kind="inspect_hardware",
            title="Inspect hardware",
            status="complete",
        ),
        PlanAction(
            id="inspect.runtime",
            kind="inspect_runtime",
            title="Inspect ComfyUI runtime",
            status="complete",
        ),
    ]

    mutation_requires_restart = False
    gpu_backends = sorted({candidate.backend for candidate in selected if candidate.backend != "cpu"})
    if gpu_backends and runtime.compute_backend not in gpu_backends:
        backend = gpu_backends[0]
        actions.append(
            PlanAction(
                id=f"runtime.{backend}",
                kind="prepare_runtime",
                title=f"Prepare {backend.upper()} runtime",
                requires_approval=True,
                payload={"backend": backend},
            )
        )
        mutation_requires_restart = True

    seen_license: set[str] = set()
    seen_packages: set[str] = set()
    seen_assets: set[str] = set()
    blueprint_ids: list[str] = []

    # Phase 1: approvals and environment/package/model mutations.
    for candidate in sorted(selected, key=lambda item: item.id):
        if candidate.license_status in {"acknowledgement", "restricted"} and candidate.id not in seen_license:
            actions.append(
                PlanAction(
                    id=f"license.{candidate.id}",
                    kind="review_license",
                    title=f"Review terms for {candidate.title}",
                    requires_approval=True,
                    payload={"candidate_id": candidate.id, "license_status": candidate.license_status},
                )
            )
            seen_license.add(candidate.id)

        for package in sorted(candidate.packages):
            if package in inventory.package_ids or package in seen_packages:
                continue
            actions.append(
                PlanAction(
                    id=f"package.{package}",
                    kind="install_package",
                    title=f"Install package {package}",
                    requires_approval=True,
                    payload={"package_id": package},
                )
            )
            seen_packages.add(package)
            mutation_requires_restart = True

        for asset in sorted(candidate.assets, key=lambda item: item.id):
            if asset.id in inventory.asset_ids or asset.id in seen_assets:
                continue
            actions.append(
                PlanAction(
                    id=f"asset.{asset.id}",
                    kind="download_asset",
                    title=f"Download asset {asset.id}",
                    requires_approval=True,
                    payload={"asset_id": asset.id, "size_bytes": asset.size_bytes},
                )
            )
            seen_assets.add(asset.id)
            mutation_requires_restart = True

        if candidate.blueprint_id and candidate.blueprint_id not in blueprint_ids:
            blueprint_ids.append(candidate.blueprint_id)

    # Phase 2: make the runtime observe any changed environment before loading
    # and validating workflows against live /object_info.
    if mutation_requires_restart:
        actions.append(
            PlanAction(
                id="runtime.restart",
                kind="restart_runtime",
                title="Restart ComfyUI runtime",
            )
        )

    # Phase 3: load graph truth, then validate it against the restarted runtime.
    for blueprint_id in blueprint_ids:
        actions.append(
            PlanAction(
                id=f"blueprint.{blueprint_id}",
                kind="load_blueprint",
                title=f"Load workflow {blueprint_id}",
                payload={"blueprint_id": blueprint_id},
            )
        )

    actions.append(
        PlanAction(
            id="validate.workflow",
            kind="validate_workflow",
            title="Validate workflow against live ComfyUI",
        )
    )

    selected_titles = ", ".join(candidate.title for candidate in selected)
    return ActionPlan(
        id="resolve:" + "+".join(candidate.id for candidate in selected),
        title="Prepare requested capabilities",
        actions=tuple(actions),
        summary=f"Selected: {selected_titles}",
    )

def resolve_capabilities(
    request: CapabilityRequest,
    hardware: HardwareProfile,
    runtime: RuntimeProfile,
    inventory: InstalledInventory,
    candidates: Iterable[ImplementationCandidate],
) -> ResolutionResult:
    if not request.capabilities:
        raise ValueError("At least one capability is required.")

    ordered = tuple(sorted(candidates, key=lambda candidate: candidate.id))
    ids = [candidate.id for candidate in ordered]
    if len(ids) != len(set(ids)):
        raise ValueError("Implementation candidate IDs must be unique.")

    assessments = {
        candidate.id: assess_candidate(request, hardware, runtime, inventory, candidate)
        for candidate in ordered
    }

    selected_ids = _select_candidates(request, hardware, inventory, ordered, assessments)
    selected_set = set(selected_ids)
    selected = tuple(candidate for candidate in ordered if candidate.id in selected_set)

    covered = {
        capability
        for candidate in selected
        for capability in candidate.capabilities
        if capability in request.capabilities
    }
    unresolved = tuple(capability for capability in request.capabilities if capability not in covered)
    plan = None if unresolved else _build_plan(request, runtime, inventory, selected, assessments)

    return ResolutionResult(
        requested_capabilities=request.capabilities,
        selected_candidate_ids=selected_ids,
        assessments=tuple(assessments[candidate.id] for candidate in ordered),
        plan=plan,
        unresolved_capabilities=unresolved,
    )
