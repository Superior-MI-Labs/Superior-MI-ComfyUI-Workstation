# Superior MI Labs ComfyUI Workstation Architecture

## Current transition

The current public beta still contains legacy GTK-era ownership. The active
Core R1 architecture is defined in
`docs/WORKSTATION-CORE-R1-PLAN.md` and is being migrated incrementally on
`architecture/workstation-core-r1`.

Current beta behavior is preserved until each replacement path is characterized
and qualified. Legacy ownership is deleted only after its replacement passes.

## Core R1 authority model

```text
User intent
    |
    v
Assistant / Simple UI
    |
    v
CapabilityRequest
    |
    v
Deterministic planner
    |
    +-- HardwareProfile
    +-- RuntimeProfile
    +-- AssetInventory
    +-- BlueprintRegistry
    +-- CapabilityRegistry
    +-- PackageRegistry
    '-- EvidenceStore
    |
    v
ActionPlan
    |
    v
Approved executor
    |
    +-- Comfy Manager / comfy-cli
    +-- asset download adapters
    '-- ComfyUI API
    |
    v
ComfyUI workflow + runtime
    |
    v
GraphControlRegistry
    |
    +-- Simple Create
    +-- Assistant actions
    '-- Studio / native graph
```

## Frozen responsibilities

ComfyUI owns:
- graph structure and workflow values;
- node/runtime schema exposed by `/object_info`;
- queueing and execution.

Workstation Core owns:
- hardware/runtime facts;
- normalized graph-control projections;
- capability/package/Blueprint registries;
- deterministic planning;
- approval-gated execution;
- evidence, diagnostics, recovery, and simplified UX.

Blueprints own:
- metadata;
- capability/requirement declarations;
- native ComfyUI workflows;
- optional presentation hints for graph controls.

Blueprints do not own a second copy of workflow values.

## Graph control rule

Simple controls are dynamically derived from the actual workflow plus the live
ComfyUI node schema. Dropdowns, sliders, numeric fields, toggles, prompts,
model pickers, and media inputs are projections of graph values.

Changing Simple Mode must update the graph value. Changing the graph must update
Simple Mode. Divergent value copies are an architecture failure.

Blueprint metadata may rename, group, prioritize, or hide controls in normal
Simple Mode. It may not become a second value authority.

## Core vs add-ons

Domain-specific concepts are outside Core.

Character Studio is a future experience add-on. Core does not define Character,
wardrobe, identity, reference sets, or character-aware Blueprint flags.

Future experience add-ons may include Character Studio, Marketing Studio,
Product Photography, Game Asset Studio, and YouTube Studio. They consume Core
capabilities and workflows instead of creating parallel runtime/package systems.

## UI direction

The target surfaces are Home, Create, Studio, Activity, and System.

Studio uses the real ComfyUI frontend. Workstation should not build a parallel
node editor.

The existing native launcher should progressively shrink toward installation,
boot, repair, update, recovery, and environment management while the Superior MI
ComfyUI extension becomes the primary creative workspace.
