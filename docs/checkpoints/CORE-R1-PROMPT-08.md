# Workstation Core R1 Prompt 8 Checkpoint

Date: 2026-10-07  
Branch: `architecture/workstation-core-r1`  
Qualified source head: `150c2ff87654fb92cd149bb7c158f87199263230`

## Scope

Prompt 8 performs destructive ownership cleanup after the R1 replacement paths
were qualified.

Removed or demoted:

- Character as a Core domain;
- legacy `character_library.py`;
- Character-specific Core tests;
- bundled Character asset library;
- Character-category preset tree;
- standalone Character documentation;
- Character pack/catalog claims in current-facing product documentation;
- Character-specific preset naming where the underlying workflow is generic;
- hard-coded `FAMILY_STACK` Python mapping;
- direct-Git custom-node mutation as the normal stack-manager path;
- duplicate NVIDIA hardware probing in `setup_helper.py`;
- duplicate NVIDIA hardware probing in the GTK shell;
- Character-specific capability assumptions in retained creation contracts.

## Hardware authority cleanup

The GTK shell now consumes Core R1 hardware services.

A typed `GPUTelemetry` contract and canonical
`observe_primary_gpu_telemetry()` service preserve live GPU status without
allowing `main.py` to invoke `nvidia-smi` directly.

Vendor-specific probes remain encapsulated in `app/core/hardware.py`.

Diagnostics now serialize the canonical HardwareProfile instead of embedding a
separate NVIDIA-only hardware command path.

## Character boundary

Core R1 ships no:

- Character library module;
- `assets/characters` tree;
- `preset_library/Character` category;
- Character pack;
- Character-specific capability key;
- Character-specific Blueprint flag;
- standalone Character product documentation.

Git history preserves the removed implementation for a future experience add-on.

Generic reference-guided workflows remain because image references are a Core
media/input concept rather than a persistent Character domain.

## Qualification

GitHub Actions run: 37569184384

- Python 3.11: PASS
- Python 3.12: PASS
- JavaScript syntax: PASS
- graph-control replay: PASS
- `js_graph_controls=PASS controls=6`
- JSON validation: 46 files PASS
- Python test suite: 94 passed

Cleanup tests now lock:

- no `FAMILY_STACK` in Python;
- no direct-Git custom-node mutation in legacy stack manager;
- canonical hardware observers are used by setup helper;
- GTK shell contains no direct `nvidia-smi`;
- no Character module/assets/preset category/doc ships in Core R1;
- current README does not advertise Character Library behavior;
- every indexed Blueprint has data-owned stack/capability identity.

## Next gate

Prompt 9: application qualification.

Focus only on cross-component composition and release blockers:

1. assistant intent -> CapabilityRequest -> deterministic resolver -> ActionPlan;
2. exact approval -> executor -> restart -> workflow validation;
3. imported workflow -> live schema -> GraphControlRegistry -> validated changes;
4. assistant-off operation;
5. failure injection and idempotent recovery;
6. stale approval rejection;
7. missing/unknown package and asset rejection;
8. upgrade/update/recovery characterization;
9. package/build/static architecture checks;
10. destructive review for duplicate graph/planner/package/hardware authorities.

Do not claim GPU/UI qualification while physical workstation access is unavailable.
