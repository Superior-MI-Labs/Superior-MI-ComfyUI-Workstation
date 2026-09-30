# Superior MI Labs ComfyUI Workstation

> **Development / pre-release qualification. Not an official release yet.**

Superior MI Labs is qualifying a beginner-oriented local ComfyUI workstation organized around:

- Create
- Blueprints
- Starter Packs
- Characters
- Activity
- Advanced diagnostics
- Verified update checks

Current development candidate: **3.0.3**

## Current qualification note

3.0.3 fixes the Qwen Image 2.1 reference-generation failure found on WolfCat. Current ComfyUI uses V3 Autogrow reference inputs such as `images.image_1`, which are reconstructed into the node's `execute(images={...})` argument. Older flat `image_1` Blueprint inputs could reach Python as an unexpected keyword argument.

Create controls are now derived from the selected Blueprint graph rather than maintained as an independent hand-written UI capability table. Character, source image, format, and quality controls appear only when the selected setup can consume them.

Before a Creation is queued, its node inputs are reconciled against the running ComfyUI `/object_info` contract. Unsupported inputs fail preflight instead of reaching node execution.

Official binaries and release notes will be published only after local qualification is complete.

Canonical repository: `Superior-MI-Labs/Superior-MI-ComfyUI-Workstation`.
