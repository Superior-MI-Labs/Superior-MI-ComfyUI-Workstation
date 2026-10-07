"""Core contracts for Superior MI Workstation R1.

The core package is deliberately UI-agnostic. ComfyUI remains graph/runtime
authority; Workstation core owns normalized projections, planning, hardware
facts, and evidence.
"""

from .contracts import (
    ActionExecution,
    ActionPlan,
    AssistantContext,
    AssistantProposal,
    AssetRequirement,
    CandidateAssessment,
    CapabilityDefinition,
    CapabilityRequest,
    GPUProfile,
    GPUTelemetry,
    GraphControl,
    HardwareProfile,
    ImplementationCandidate,
    InstalledInventory,
    PlanAction,
    PlanApproval,
    PlanExecutionResult,
    ResolutionResult,
    RuntimeProfile,
    StorageProfile,
)
from .assistant import AssistantService, build_assistant_context, validate_assistant_proposal
from .executor import PlanExecutor, approval_for, fingerprint_action, fingerprint_plan
from .graph_controls import GraphControlRegistry, derive_graph_controls
from .hardware import observe_hardware, observe_primary_gpu_telemetry
from .registry import (
    CapabilityRegistry,
    ImplementationRegistry,
    load_capability_registry,
    load_implementation_registry,
)
from .resolver import assess_candidate, resolve_capabilities
from .runtime_profile import observe_runtime

__all__ = [
    "ActionExecution",
    "ActionPlan",
    "AssistantContext",
    "AssistantProposal",
    "AssistantService",
    "AssetRequirement",
    "CandidateAssessment",
    "CapabilityDefinition",
    "CapabilityRegistry",
    "CapabilityRequest",
    "GPUProfile",
    "GPUTelemetry",
    "GraphControl",
    "GraphControlRegistry",
    "HardwareProfile",
    "ImplementationCandidate",
    "ImplementationRegistry",
    "InstalledInventory",
    "PlanAction",
    "PlanApproval",
    "PlanExecutionResult",
    "PlanExecutor",
    "ResolutionResult",
    "RuntimeProfile",
    "StorageProfile",
    "approval_for",
    "build_assistant_context",
    "assess_candidate",
    "derive_graph_controls",
    "fingerprint_action",
    "fingerprint_plan",
    "load_capability_registry",
    "load_implementation_registry",
    "observe_hardware",
    "observe_primary_gpu_telemetry",
    "observe_runtime",
    "resolve_capabilities",
    "validate_assistant_proposal",
]
