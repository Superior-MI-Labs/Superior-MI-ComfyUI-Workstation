from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Mapping


@dataclass(frozen=True)
class GPUProfile:
    vendor: str
    model: str
    vram_bytes: int = 0
    driver: str = ""
    backend_candidates: tuple[str, ...] = ()
    compute_capability: str = ""
    supported_dtypes: tuple[str, ...] = ()


@dataclass(frozen=True)
class StorageProfile:
    path: str
    free_bytes: int
    total_bytes: int = 0
    medium: str = ""
    label: str = ""


@dataclass(frozen=True)
class HardwareProfile:
    platform: str
    architecture: str
    os_version: str = ""
    distribution: str = ""
    cpu_model: str = ""
    logical_cpu_count: int = 0
    physical_cpu_count: int = 0
    memory_total_bytes: int = 0
    memory_available_bytes: int = 0
    gpus: tuple[GPUProfile, ...] = ()
    storage: tuple[StorageProfile, ...] = ()


@dataclass(frozen=True)
class RuntimeProfile:
    python_version: str = ""
    torch_version: str = ""
    compute_backend: str = ""
    backend_version: str = ""
    comfyui_version: str = ""
    comfyui_url: str = ""
    installed_node_types: frozenset[str] = frozenset()
    installed_packages: tuple[str, ...] = ()


@dataclass(frozen=True)
class CapabilityRequest:
    capabilities: tuple[str, ...]
    local_only: bool = True
    quality_priority: str = "balanced"
    storage_budget_bytes: int | None = None
    preferences: Mapping[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class GraphControl:
    """Normalized editable projection of one live workflow input.

    The value belongs to the graph. This object is a snapshot/binding, not a
    second state owner.
    """

    id: str
    node_id: str
    node_type: str
    input_name: str
    data_type: str
    value: Any
    widget: str
    label: str
    group: str
    section: str = "required"
    minimum: float | int | None = None
    maximum: float | int | None = None
    step: float | int | None = None
    choices: tuple[Any, ...] = ()
    editable: bool = True
    priority: str = "advanced"
    reason: str = ""


@dataclass(frozen=True)
class PlanAction:
    id: str
    kind: str
    title: str
    status: str = "pending"
    requires_approval: bool = False
    payload: Mapping[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class ActionPlan:
    id: str
    title: str
    actions: tuple[PlanAction, ...]
    summary: str = ""

    @property
    def requires_approval(self) -> bool:
        return any(action.requires_approval for action in self.actions)


@dataclass(frozen=True)
class AssetRequirement:
    id: str
    size_bytes: int = 0


@dataclass(frozen=True)
class InstalledInventory:
    asset_ids: frozenset[str] = frozenset()
    package_ids: frozenset[str] = frozenset()


@dataclass(frozen=True)
class ImplementationCandidate:
    id: str
    title: str
    capabilities: tuple[str, ...]
    backend: str = "cpu"
    platforms: tuple[str, ...] = ()
    architectures: tuple[str, ...] = ()
    min_vram_bytes: int = 0
    min_ram_bytes: int = 0
    assets: tuple[AssetRequirement, ...] = ()
    packages: tuple[str, ...] = ()
    blueprint_id: str = ""
    execution_mode: str = "local"
    stability: str = "stable"
    evidence_score: int = 0
    preference_scores: Mapping[str, int] = field(default_factory=dict)
    license_status: str = "open"


@dataclass(frozen=True)
class CandidateAssessment:
    candidate_id: str
    status: str
    rejection_reasons: tuple[str, ...] = ()
    setup_reasons: tuple[str, ...] = ()
    warnings: tuple[str, ...] = ()
    required_download_bytes: int = 0
    reused_assets: tuple[str, ...] = ()


@dataclass(frozen=True)
class ResolutionResult:
    requested_capabilities: tuple[str, ...]
    selected_candidate_ids: tuple[str, ...]
    assessments: tuple[CandidateAssessment, ...]
    plan: ActionPlan | None
    unresolved_capabilities: tuple[str, ...] = ()

    @property
    def resolved(self) -> bool:
        return not self.unresolved_capabilities and self.plan is not None
