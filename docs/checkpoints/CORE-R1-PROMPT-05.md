# Workstation Core R1 Prompt 5 Checkpoint

Date: 2026-10-06  
Branch: `architecture/workstation-core-r1`  
Qualified structural source head: `f7ce94ab0e9d72b9927e58619577b3fbc327f3fe`

## Scope

Prompt 5 establishes Studio as the real ComfyUI frontend/canvas with Superior MI
panels around it.

Implemented:

- existing workflow handoff through `app.loadGraphData` preserved;
- native ComfyUI sidebar registration through the extension API;
- Superior MI shell with Home, Create, Activity, and System surfaces;
- Studio explicitly defined as the native ComfyUI canvas beside the sidebar;
- bridge status surfaced in System;
- extension errors use ComfyUI toast support when available;
- bridge version advanced to v2;
- JavaScript syntax qualification added to CI.

## Architecture boundary

There is no iframe.

There is no second LiteGraph instance.

There is no Superior MI node canvas.

There is no graph synchronization layer between two editors because only
ComfyUI owns the editor.

The relationship is:

```text
Superior MI sidebar | native ComfyUI canvas
                    |
                    '-- one workflow / one graph authority
```

## Qualification

GitHub Actions run: 37551416728

- Python 3.11: PASS
- Python 3.12: PASS
- bridge JavaScript syntax check: PASS
- Python compile: PASS
- JSON validation: 46 files PASS
- test suite: 75 passed

Static architecture tests require:

- native sidebar registration;
- preserved `app.loadGraphData`;
- no iframe creation;
- no new LiteGraph/LGraphCanvas construction;
- domain-neutral Core navigation;
- preserved backend handoff/status routes.

## Qualification scope

This is a structural/headless qualification.

A real browser/ComfyUI frontend interaction run is not falsely claimed while
WolfCat is unavailable. The previous beta bridge handoff remains characterized,
and the new extension source is syntax/contract qualified in remote CI.

Prompt 6 will add graph-derived controls and stronger replay/parity tests that do
not require GPU execution.

## Next gate

Prompt 6: Dynamic Create + two-way graph synchronization.

Simple controls must be projections of the active native graph. They may not
become a second value store.
