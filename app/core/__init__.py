"""Core contracts for Superior MI Workstation R1.

The core package is deliberately UI-agnostic. ComfyUI remains graph/runtime
authority; Workstation core owns normalized projections, planning, hardware
facts, and evidence.
"""

from .contracts import (
    ActionPlan,
    CapabilityRequest,
    GraphControl,
    GPUProfile,
    HardwareProfile,
    PlanAction,
    RuntimeProfile,
    StorageProfile,
)

__all__ = [
    "ActionPlan",
    "CapabilityRequest",
    "GraphControl",
    "GPUProfile",
    "HardwareProfile",
    "PlanAction",
    "RuntimeProfile",
    "StorageProfile",
]
