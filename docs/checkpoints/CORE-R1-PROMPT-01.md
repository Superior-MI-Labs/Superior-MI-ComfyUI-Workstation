# Workstation Core R1 Prompt 1 Checkpoint

Date: 2026-10-06  
Branch: `architecture/workstation-core-r1`  
Head: `f1a8f12afcc0dd3ff50879161ca4e6ad1185ea1a`

## Scope

Prompt 1 established the first new Core R1 authorities without replacing the
existing production beta UI/runtime paths.

Implemented:

- typed `HardwareProfile`, `RuntimeProfile`, `CapabilityRequest`,
  `GraphControl`, `PlanAction`, and `ActionPlan` contracts;
- `GraphControlRegistry` derived from the actual API workflow and live
  ComfyUI `/object_info` schema;
- automatic widget classification for combo/dropdown, bounded numeric
  slider+number, number, toggle, text, multiline, and media/file inputs;
- graph socket references excluded from editable scalar controls;
- Blueprint presentation metadata may rename/group/prioritize/hide controls
  without owning their values;
- validated control application rejects unknown IDs, invalid enum choices,
  wrong numeric types, and out-of-range values;
- Character is formally removed from the target Core architecture and deferred
  to a future add-on;
- Core R1 architecture and prompt/wave strategy documented;
- GitHub Actions qualification lane added for Python 3.11 and 3.12.

## Qualification

GitHub Actions run: 37547535844

- Python 3.11: PASS
- Python 3.12: PASS
- Python compile: PASS
- JSON validation: 45 files PASS
- Test suite: 29 passed

The first CI run correctly exposed a socket-reference classification bug. The
detector was repaired so stale/malformed Comfy connection tuples cannot be
reinterpreted as editable scalar controls. The repaired matrix is green.

## Preserved boundaries

- Existing GTK beta behavior remains untouched in Prompt 1.
- Existing direct package and Character code remains only as legacy migration
  surface until replacement authorities are qualified.
- ComfyUI remains graph/runtime authority.
- No LLM or assistant receives mutation authority.
- No package installer was added.

## Next gate

Prompt 2: Hardware and Runtime as Data.

Build one canonical observation pipeline for CPU, memory, storage, GPU(s),
driver/backend availability, Python, PyTorch, and ComfyUI runtime facts.
Characterize NVIDIA, AMD, Intel, Apple/MPS, and CPU-only fixtures. Existing
NVIDIA-only `setup_helper.detect_gpu()` remains legacy until the new profile
service is qualified.
