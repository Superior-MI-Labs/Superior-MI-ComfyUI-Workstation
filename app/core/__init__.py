"""Core contracts for Superior MI Workstation R1.

The core package is deliberately UI-agnostic. ComfyUI remains graph/runtime
authority; Workstation core owns normalized projections, planning, hardware
facts, and evidence.
"""

from .contracts import (
    ActionPlan,
    AssetRequirement,
    CandidateAssessment,
    CapabilityDefinition,
    CapabilityRequest,
    GPUProfile,
    GraphControl,
    HardwareProfile,
    ImplementationCandidate,
    InstalledInventory,
    PlanAction,
    ResolutionResult,
    RuntimeProfile,
    StorageProfile,
)
from .graph_controls import GraphControlRegistry, derive_graph_controls
from .hardware import observe_hardware
from .registry import (
    CapabilityRegistry,
    ImplementationRegistry,
    load_capability_registry,
    load_implementation_registry,
)
from .resolver import assess_candidate, resolve_capabilities
from .runtime_profile import observe_runtime

__all__ = [
    "ActionPlan",
    "AssetRequirement",
    "CandidateAssessment",
    "CapabilityDefinition",
    "CapabilityRegistry",
    "CapabilityRequest",
    "GPUProfile",
    "GraphControl",
    "GraphControlRegistry",
    "HardwareProfile",
    "ImplementationCandidate",
    "ImplementationRegistry",
    "InstalledInventory",
    "PlanAction",
    "ResolutionResult",
    "RuntimeProfile",
    "StorageProfile",
    "assess_candidate",
    "derive_graph_controls",
    "load_capability_registry",
    "load_implementation_registry",
    "observe_hardware",
    "observe_runtime",
    "resolve_capabilities",
]
