# Workstation Core R1 Prompt 6 Checkpoint

Date: 2026-10-06  
Branch: `architecture/workstation-core-r1`  
Qualified source head: `d42628272d5405a639317bc3080da348b7cf7dc4`

## Scope

Prompt 6 establishes Dynamic Create as a live projection of the native ComfyUI
root workflow graph.

It does not introduce a Superior MI workflow-value store and it does not
synchronize two graph models.

Implemented:

- `smi-graph-controls.js` as a small native-widget projection layer;
- control discovery from `app.graph._nodes[].widgets`;
- stable root-graph control identity from node ID + widget name;
- conservative primary/advanced grouping;
- dropdown projection for combo widgets;
- toggle projection for booleans;
- slider + exact-number projection for bounded numeric widgets;
- numeric projection for unbounded numeric widgets;
- text and multiline projections;
- unknown custom and generic media widgets fail closed as read-only;
- numeric INT/FLOAT inference uses widget constraints as well as current value;
- live write path:
  `widget.value -> widget.callback -> graph.change -> canvas dirty`;
- live read path reads the same widget value back into Create;
- projection refresh when graph/widget structure changes;
- polling refresh for graph-side value changes;
- interval cleanup when the Create surface is detached;
- Show Advanced / Hide Advanced over the same graph values.

## Authority rule

```text
Studio edit ----\
                > native ComfyUI widget value -> graph
Create edit ----/
```

Create and Studio do not own separate copies.

## Qualification

GitHub Actions run: 37551999694

- Python 3.11: PASS
- Python 3.12: PASS
- JavaScript syntax checks: PASS
- JavaScript live graph-control test: PASS
- `js_graph_controls=PASS controls=6`
- JSON validation: 46 files PASS
- Python test suite: 80 passed

Qualification covers:

- control classification;
- primary vs advanced projection;
- combo choices;
- bounded numeric controls;
- integer validation;
- float preservation when the current value is integer-valued;
- native callback dispatch;
- graph change notification;
- canvas dirty notification;
- invalid range rejection;
- invalid combo rejection;
- unsupported-widget write rejection;
- external graph value changes being observed by the projection;
- no Character/domain authority in Core Create.

## Explicit scope boundary

Prompt 6 qualifies the root graph represented by `app.graph`.

Nested subgraphs are not flattened into a Superior MI graph model. They remain
editable through Studio until the installed ComfyUI frontend exposes a stable
projection contract we can consume directly.

Generic media widgets are visible but read-only until their native interaction
contract is qualified rather than guessed.

## Next gate

Prompt 7: Conversational Planner.

The assistant layer may translate natural language into:

- `CapabilityRequest` objects;
- registered GraphControl changes;
- requests to explain/review an existing ActionPlan.

It must not:

- execute arbitrary shell commands;
- invent package IDs;
- invent model URLs;
- bypass PlanApproval;
- become the deterministic resolver;
- become a second graph-value owner.

The system must remain fully usable when no AI provider is configured.
