# Superior MI Labs ComfyUI Workstation 3.0 Architecture

## Single conceptual system

```text
Pack ─────── supplies models/components ───────┐
                                                │
Character ── supplies reusable media input ──► Blueprint ──► Creation
                                                │
                                                ▼
                                      canonical ComfyUI graph
                                                │
                                                ▼
                                         ComfyUI runtime
```

The Workstation does not maintain separate "create presets", "preset presets", and "picks workflows".
Those are views over the same Blueprint/Pack registry.

## Beginner vs advanced surfaces

The beginner Create page selects and configures a Blueprint.
Library exposes the same Blueprints and Packs directly.
Advanced exposes implementation details: models, logs, runtime, diagnostics, settings.

## ComfyUI integration

API-format Blueprints remain the execution authority for direct queueing. For the graphical editor,
the Workstation converts the API prompt to a UI graph using the *local* `/object_info` schema, stores
it through ComfyUI's `/api/userdata` workflow store, then asks the bundled bridge to load it.

This keeps workflow import coupled to the installed ComfyUI contract instead of hard-coding one
frontend build's widget ordering.

## Character collections

Starter references are grouped as **Superior MI Characters**. User-created nested folders are discovered recursively and remain independent from bundled examples.
