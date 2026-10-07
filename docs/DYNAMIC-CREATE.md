# Dynamic Create Contract

Status: Core R1 Prompt 6

## Authority

The active native ComfyUI graph owns workflow values.

Superior MI Create is a projection of live ComfyUI node widgets. It does not
persist a second editable copy of prompt, steps, CFG, sampler, seed, dimensions,
model selections, or other graph values.

## Qualified flow

```text
native ComfyUI graph
       |
       v
live node widgets
       |
       v
deriveGraphControls()
       |
       v
Superior MI Create controls
       |
       | user edit
       v
writeLiveControlValue()
       |
       +-- widget.value
       +-- widget.callback(...)
       +-- graph.change()
       '-- canvas dirty
```

Graph-side changes are read back from the live widget values and refresh the
projection. The UI does not synchronize against a Superior MI value store.

## Presentation

Primary controls are inferred conservatively for common concepts such as:

- prompts;
- resolution;
- steps;
- seed.

Advanced controls include common sampling/model/output widgets and otherwise
supported scalar widgets.

Supported editable primitives currently include:

- combo/dropdown;
- boolean toggle;
- bounded numeric slider plus exact number input;
- numeric input;
- text;
- multiline text.

Unknown custom widget types and generic media widgets fail closed as read-only
until a specific native interaction contract is qualified.

## Scope

Prompt 6 qualifies the root workflow graph represented by `app.graph`.

Nested ComfyUI subgraphs are not flattened into a second Superior MI graph
model. Subgraph editing remains available through Studio until the installed
frontend exposes a stable, directly testable projection contract that can be
consumed without inventing ownership.

This is an explicit unsupported boundary, not silent partial synchronization.
