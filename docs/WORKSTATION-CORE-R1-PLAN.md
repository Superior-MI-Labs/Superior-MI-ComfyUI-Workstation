# Workstation Core R1 Architecture and Delivery Plan

Status: active architecture program  
Branch: `architecture/workstation-core-r1`

## Product definition

Superior MI Workstation is a hardware-aware, conversational operating layer for ComfyUI.

ComfyUI owns graphs and execution. Workstation owns intent, hardware/runtime facts,
curation, planning, qualification, evidence, and the simplified user experience.

The user should be able to describe a goal in natural language, review an auditable
checklist of setup or workflow actions, approve changes, and then move between a
simple control surface and the real ComfyUI graph without switching execution systems.

## Frozen R1 invariants

1. The ComfyUI workflow is execution truth.
2. Live `/object_info` is node/input contract truth.
3. Workstation graph controls are projections of graph state, never a second state owner.
4. Simple UI and Studio operate on the same workflow values.
5. The assistant may propose only registered, validated actions.
6. An LLM never receives arbitrary shell or package-install authority.
7. Hardware and runtime state are typed data.
8. Package planning is deterministic and approval-gated.
9. Comfy Manager/comfy-cli are the preferred package mechanics.
10. Blueprints curate presentation and requirements; they do not duplicate graph state.
11. Character/domain-specific concepts are not Workstation Core.
12. Add-ons consume core capabilities instead of creating parallel pipelines.

## Target user flow

```text
User goal
   |
   v
Assistant / simple goal UI
   |
   v
CapabilityRequest
   |
   v
Deterministic Planner
   |-- HardwareProfile
   |-- RuntimeProfile
   |-- AssetInventory
   |-- BlueprintRegistry
   |-- CapabilityRegistry
   |-- PackageRegistry
   '-- EvidenceStore
   |
   v
ActionPlan / Checklist
   |
   +--> inspect-only actions run automatically
   |
   '--> mutations require review/approval
              |
              v
       Package / Workflow Executor
              |
              v
            ComfyUI
              |
              v
     GraphControlRegistry
        |          |
        v          v
    Simple UI    Studio
        \          /
         \        /
          same graph
              |
              v
         Run + Evidence
```

## User interface

The primary application has five surfaces:

- Home: assistant conversation plus the current plan/checklist.
- Create: dynamically generated simple controls for the active workflow.
- Studio: the real ComfyUI frontend/canvas.
- Activity: queue, downloads, outputs, benchmark/evidence, failures.
- System: hardware, runtime, storage, health, installed components, updates.

The preferred long-term host is a Superior MI ComfyUI frontend extension around
the real canvas. The native desktop launcher becomes bootstrap, runtime, repair,
update, and recovery tooling.

### Dynamic Create controls

The graph and live schema generate normalized controls:

```text
ComfyUI workflow
      |
      v
live node schema (/object_info)
      |
      v
GraphControlRegistry
      |
      +--> prompt          -> multiline editor
      +--> bool            -> toggle
      +--> enum/combo      -> searchable dropdown
      +--> bounded number  -> slider + exact numeric field
      +--> number          -> numeric field/stepper
      +--> model/file      -> searchable picker
      '--> media           -> drop/browse/preview
```

Curated Blueprint metadata may rename, group, prioritize, or hide a control in
normal Simple Mode. It never owns the value.

Three presentation levels share one workflow:

```text
Conversation
    |
Simple controls
    |
Advanced controls
    |
Full ComfyUI graph
```

Changing any level updates the same underlying graph state.

## Action checklist model

The application uses the same visual language for three plan types.

Setup plan:
- inspect runtime
- install package
- download model
- validate workflow
- load workflow

Workflow-change plan:
- change resolution
- change steps
- change sampler
- change model
- update any other registered graph control

Run plan:
- validate inputs
- validate hardware fit
- queue
- track execution
- retain output/evidence

Status is system-owned: ready, pending, running, complete, blocked, failed.
Users approve actions; they do not manually mark reality as complete.

## Core vs add-ons

Core owns:
- graph/runtime integration
- HardwareProfile and RuntimeProfile
- asset inventory and identity
- capability/Blueprint/package registries
- graph-control discovery and synchronization
- deterministic resolver/planner
- approval-gated executor
- activity/progress/output/evidence
- diagnostics/recovery/updates
- assistant provider contract
- plugin/add-on contract

Capability packs provide physical implementations such as image, video, audio,
upscale, restoration, or 3D.

Experience add-ons provide domain workflows such as Character Studio, Marketing
Studio, Product Photography, Game Asset Studio, or YouTube Studio.

Infrastructure add-ons provide cloud/API/remote compute/team capabilities.

Character Studio is explicitly deferred. Core must not know what a persistent
character is.

## Repository target layout

```text
app/
  core/
    contracts.py
    graph_controls.py
    hardware.py
    runtime.py
    inventory.py
    planner.py
    executor.py
    evidence.py
  adapters/
    comfy.py
    manager.py
    comfy_cli.py
    huggingface.py
    assistant.py
  launcher/
    bootstrap.py
    repair.py
    updates.py

bridge/Superior-MI-Workstation-Bridge/
  web/
    assistant/
    create/
    studio/
    activity/
    system/

catalog/
  capabilities/
  blueprints/
  implementations/
  packs/

tests/
  contracts/
  graph_controls/
  hardware/
  planner/
  executor/
  graph_sync/
  qualification/
```

Migration is incremental. Existing files remain until their replacement is
qualified, then legacy ownership is deleted rather than left as a second path.

## Delivery prompts / waves

### Prompt 0: Census and architecture freeze

Exit gate:
- live repository reconciled;
- current ownership mapped;
- Core R1 invariants documented;
- no implementation authority duplicated.

### Prompt 1: Core contracts + graph controls + remote CI

Build:
- typed hardware/runtime/capability/action contracts;
- GraphControlRegistry;
- schema-driven widget mapping;
- validated graph patches;
- remote Python matrix CI.

Exit gate:
- controls derive from graph + `/object_info`;
- invalid values cannot be applied;
- branch CI green.

### Prompt 2: Hardware and runtime as data

Build:
- cross-platform hardware probes;
- GPU list with vendor/model/VRAM/driver/backend;
- CPU/RAM/storage;
- ComfyUI/Python/PyTorch/backend/runtime inventory;
- no NVIDIA-only authority in setup code.

Exit gate:
- fixture tests for NVIDIA/AMD/Intel/Apple/CPU-only cases;
- missing probes fail softly and explicitly;
- one canonical profile per machine observation.

### Prompt 3: Capability/package resolver

Build:
- capability registry;
- implementation candidates;
- hard compatibility constraints;
- ranking by hardware fit, installed reuse, storage, stability, license, evidence;
- dry-run InstallPlan.

Exit gate:
- no mutation;
- deterministic plan for fixed inputs;
- rejects impossible candidates with reasons.

### Prompt 4: Package execution authority

Build:
- Comfy Manager/comfy-cli adapter;
- approval boundary;
- model download adapter;
- restart/validation;
- raw git install demoted to explicit fallback.

Exit gate:
- installer executes only approved typed plan actions;
- no AI-generated commands;
- failure/resume evidence retained.

### Prompt 5: Studio host

Build:
- integrate the real ComfyUI frontend into Workstation experience;
- expand existing bridge into a first-class frontend extension;
- keep external browser launch as secondary/debug option.

Exit gate:
- real graph loads without a parallel graph editor;
- Workstation panels coexist with native canvas.

### Prompt 6: Dynamic Create + two-way synchronization

Build:
- render controls from GraphControlRegistry;
- primary/advanced/all modes;
- slider + exact-number pairing;
- searchable combos;
- specialized resolution/media controls;
- graph-to-simple and simple-to-graph event synchronization.

Exit gate:
- no divergent value copies;
- changing either surface is observable on the other;
- imported workflows get a useful generic UI without Superior MI metadata.

### Prompt 7: Conversational planner

Build:
- assistant provider interface;
- local/remote provider adapters;
- natural language -> CapabilityRequest or registered graph changes;
- checklist explanations;
- no direct executor access.

Exit gate:
- assistant can only select registered capabilities/actions/controls;
- deterministic planner remains final plan authority;
- system remains functional without an AI provider.

### Prompt 8: Delete legacy ownership

Remove/demote:
- Character from core UI/state/contracts/tests/catalog assumptions;
- `character_aware`;
- hard-coded `FAMILY_STACK`;
- direct-git normal package path;
- duplicate setup/runtime constants;
- old API-prompt-as-primary-graph assumptions where replacement exists;
- unused GTK feature surfaces.

Exit gate:
- characterization tests prove retained core behavior;
- one authority per responsibility.

### Prompt 9: Application qualification

Qualify:
- fresh setup fixture;
- existing-install adoption;
- hardware detection fixtures;
- package dry run and approved execution fixtures;
- Blueprint and arbitrary imported workflow control discovery;
- graph synchronization;
- assistant-off mode;
- assistant-on mock provider;
- failure injection;
- upgrade/recovery;
- package/build checks.

Release only after destructive review confirms no second planner, graph state,
package installer, or domain-specific Character authority remains in Core.

## Testing while WolfCat is unavailable

Testing is layered so most development does not depend on the user's PC.

1. Pure contract/unit tests run in GitHub Actions on multiple Python versions.
2. ComfyUI HTTP/schema behavior uses recorded and synthetic `/object_info`
   fixtures.
3. Package-manager behavior uses fake adapters and dry-run contracts.
4. Graph synchronization uses frontend/unit fixtures and event-replay tests.
5. Failure injection covers missing node types, invalid controls, network failure,
   interrupted download, partial install, and stale workflow schemas.
6. A containerized/headless integration lane will exercise ComfyUI where upstream
   dependencies allow it without a GPU.
7. GPU-specific qualification is evidence-gated and remains separate. Lack of
   WolfCat access cannot be mislabeled as GPU qualification.

Each prompt must leave a checkpoint containing branch head, tests, known gaps,
and the next exact gate.
