# Workstation Core R1 Prompt 3 Checkpoint

Date: 2026-10-06  
Branch: `architecture/workstation-core-r1`  
Qualified source head: `5de9051ad907a584cecb31fb74a3241f0e586703`

## Scope

Prompt 3 establishes the deterministic, dry-run capability/package resolver.

It consumes typed user intent and machine state and produces an auditable
ActionPlan. It does not install, download, modify ComfyUI, or execute arbitrary
commands.

Implemented:

- semantic `CapabilityDefinition` and production capability registry;
- typed `ImplementationCandidate`, `AssetRequirement`,
  `InstalledInventory`, `CandidateAssessment`, and `ResolutionResult`;
- typed capability and implementation registries with unique identity checks;
- deterministic candidate assessment;
- deterministic multi-capability set selection;
- explicit ready / setup_required / rejected states;
- explicit rejection/setup/warning reasons;
- physical-backend compatibility checks;
- active-runtime mismatch represented as setup rather than fake incompatibility;
- VRAM and RAM hard constraints when observed;
- unknown VRAM/RAM represented as verification/setup work rather than guessed;
- storage-budget and observed-free-space constraints;
- installed package/asset reuse;
- shared asset download cost deduplication;
- one-GPU-backend-family rule per ComfyUI environment plan;
- request-priority, evidence, stability, setup burden, download size, and
  candidate-count ranking with score normalization so extra packages cannot
  improve rank simply by adding scores;
- license/access review as an explicit approval-gated action;
- dry-run checklist actions for runtime preparation, package install, asset
  download, Blueprint load, and live workflow validation.

## Semantic capability catalog

`catalog/r1/capabilities.json` currently defines generic Core capabilities:

- `image.generate`
- `image.reference`
- `image.edit`
- `video.image_to_video`
- `video.generate`
- `audio.generate`
- `image.upscale`

There is deliberately no Character capability in Core.

## Important migration boundary

The legacy `catalog/stacks.json` is not yet promoted into the R1
ImplementationRegistry.

Existing pack fields such as recommended VRAM are recommendation-oriented and
must not silently become hard compatibility constraints. Production R1
implementation records will be migrated only when hardware/runtime requirements
are backed by appropriate upstream or measured evidence.

## Qualification

GitHub Actions run: 37548889862

- Python 3.11: PASS
- Python 3.12: PASS
- Python compile: PASS
- JSON validation: 46 files PASS
- Test suite: 55 passed

The Prompt 3 test matrix includes:

- ready candidates;
- missing-package/model checklist generation;
- installed asset/package reuse;
- runtime setup on compatible hardware;
- incompatible backend rejection;
- insufficient VRAM rejection;
- unknown VRAM verification behavior;
- storage budget/free-space rejection;
- multi-capability bundle selection;
- redundant-candidate prevention;
- mixed GPU backend plan rejection;
- explicit license review;
- deterministic tie breaking;
- duplicate identity rejection;
- semantic registry loading.

## Failure-derived corrections retained

Prompt 3 qualification caught and repaired:

1. candidate scoring that could reward redundant package addition;
2. aggregate evidence scoring that could reward splitting one bundle into
   multiple implementations;
3. shared asset cost being counted more than once during selection;
4. an implicit inventory dependency introduced during that repair.

These failures are retained as design evidence for future resolver changes.

## Next gate

Prompt 4: Package Execution Authority.

Implement adapters around authoritative package mechanics, beginning with
read-only discovery and dry-run translation, then approval-gated mutation:

- ComfyUI Manager / Registry;
- comfy-cli;
- model asset download service;
- restart/revalidation;
- action journal and idempotency.

No AI provider may call subprocesses or package mutation directly. The executor
must accept only typed, previously planned and approved PlanActions.
