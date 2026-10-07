# Workstation Core R1 Prompt 4 Checkpoint

Date: 2026-10-06  
Branch: `architecture/workstation-core-r1`  
Qualified source head: `37bb33acde24fdb522f304ad5879062ef17b3e2d`

## Scope

Prompt 4 establishes one approval-bound execution authority for typed ActionPlans.

The executor accepts only registered PlanAction kinds produced by the deterministic
planner. It does not accept shell commands, arbitrary URLs, arbitrary package
repositories, or free-form model output as mutation authority.

Implemented:

- exact SHA-256 plan fingerprinting;
- exact action fingerprinting;
- approval grants bound to the exact plan fingerprint;
- full plan/schema validation before any side effect;
- explicit payload allowlists per action kind;
- duplicate action-ID rejection;
- append-only execution journal;
- idempotent retry by exact action fingerprint;
- failure stops later actions in the same attempt;
- retry resumes previously successful actions without replaying them;
- explicit runtime restart action;
- setup phases ordered as:
  inspect -> approvals/runtime/packages/assets -> restart -> workflow load -> live validation;
- read-only ComfyUI-Manager discovery adapter;
- Manager/Registry-known package IDs required before installation;
- comfy-cli package installation through fixed argv, no shell;
- `--exit-on-fail` for custom-node installs;
- `--skip-prompt` for non-interactive mutation;
- optional Manager unified `--uv-compile` dependency mode;
- model downloads by trusted pre-registered asset ID only;
- HTTPS-only model URLs;
- embedded URL credentials rejected;
- model relative-path traversal rejected.

## External authority choices

Normal custom-node mutation is delegated to current official comfy-cli /
ComfyUI-Manager mechanics instead of Workstation cloning Git repositories.

The current production mutation shape is:

```text
ActionPlan
   |
exact approval
   |
PlanExecutor
   |
   +-- package ID -> Manager discovery -> comfy-cli node install
   |
   +-- trusted asset ID -> trusted asset registry -> comfy-cli model download
   |
   +-- runtime service boundary
   |
   '-- workflow service boundary
```

The executor never constructs a shell string.

## Restart and validation rule

Any runtime preparation, package installation, or model download causes one
explicit runtime restart action before workflow load and live validation.

A missing runtime-control adapter fails explicitly. Workstation does not
silently validate a newly changed setup against stale ComfyUI state.

## Qualification

GitHub Actions run: 37551285412

- Python 3.11: PASS
- Python 3.12: PASS
- Python compile: PASS
- JSON validation: 46 files PASS
- test suite: 71 passed

Prompt 4 tests include:

- missing approval prevents all mutation;
- stale approval after plan change prevents all mutation;
- unsupported payload keys rejected before mutation;
- unknown action kinds rejected;
- exact approved dispatch;
- interrupted run and idempotent resume;
- later actions blocked after failure;
- journal persistence across process reconstruction;
- runtime prepare/restart dispatch;
- Manager package discovery;
- registry-unknown package rejection;
- CLI command-fragment rejection;
- fixed non-shell argv;
- non-interactive package/model operations;
- unknown trusted asset rejection;
- unsafe URL credential rejection;
- HTTP URL rejection;
- relative-path escape rejection.

## Failure-derived corrections retained

The non-interactive CLI change deliberately caused a failing command-contract
test until the model-download expectation was updated. The red run is retained
as evidence that CI observes exact external mutation argv.

## Known boundary

Prompt 4 does not yet make the old GTK runtime launcher the R1 runtime-control
authority. A RuntimeService is an explicit injected boundary. If unavailable,
restart/prepare actions fail rather than falling back to hidden shell logic.

Likewise, WorkflowService is an injected boundary until native-workflow ownership
is completed in the Studio/Create prompts.

## Next gate

Prompt 5: native Studio host.

Extend the existing Superior MI ComfyUI bridge so Workstation panels coexist
with the real ComfyUI canvas. Do not use an iframe and do not build another
LiteGraph/node editor.
