# Workstation Core R1 Prompt 2 Checkpoint

Date: 2026-10-06  
Branch: `architecture/workstation-core-r1`  
Qualified source head: `406453e7f3856998e46e50d823a376352127fdbc`

## Scope

Prompt 2 establishes Hardware and Runtime as typed data for future package
resolution. It deliberately separates physical device identity from active
software backend availability.

Implemented:

- cross-platform `HardwareProfile` observation;
- CPU model and logical/physical core observations;
- total/available memory snapshot;
- storage capacity/free-space snapshots;
- Linux distribution and OS version identity;
- multi-GPU discovery;
- NVIDIA identity, VRAM, driver, CUDA candidate, and compute capability;
- Linux AMD/Intel display discovery with ROCm/XPU candidates;
- macOS display discovery with MPS candidate;
- Windows video-controller discovery with backend candidates;
- `RuntimeProfile` observation for Python, PyTorch, active backend, backend
  version, ComfyUI identity, installed node types, and installed packages;
- active backend classification for CUDA, ROCm, XPU, MPS, and CPU.

## Authority split

`GPUProfile.backend_candidates` describes implementations that may be viable
for the physical vendor.

`RuntimeProfile.compute_backend` describes the backend actually observed as
usable by the current PyTorch runtime.

A candidate backend is never upgraded to active runtime truth because a GPU
exists.

## Qualification

GitHub Actions run: 37548085078

- Python 3.11: PASS
- Python 3.12: PASS
- Python compile: PASS
- JSON validation: 45 files PASS
- Test suite: 39 passed

Fixtures cover:

- NVIDIA multi-GPU and compute capability;
- AMD and Intel discovery;
- Apple/MPS discovery;
- Windows video adapters;
- Linux OS release parsing;
- CUDA runtime;
- ROCm runtime;
- XPU runtime;
- MPS runtime;
- CPU-only runtime.

## Known boundary

This is observation and contract work only.

Prompt 2 does not install drivers, select PyTorch builds, rank model stacks, or
mutate ComfyUI. The existing NVIDIA-only setup helper remains legacy until a
qualified resolver/executor replaces its ownership.

## Next gate

Prompt 3: Capability and Package Resolver.

Build a deterministic dry-run resolver that consumes:

- CapabilityRequest;
- HardwareProfile;
- RuntimeProfile;
- installed asset/package inventory;
- capability definitions;
- implementation candidates;
- storage/license/stability/evidence constraints.

The resolver must return an auditable InstallPlan with selected candidates and
explicit rejection reasons. No package mutation is authorized in Prompt 3.
