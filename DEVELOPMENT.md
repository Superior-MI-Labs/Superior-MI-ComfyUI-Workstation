# Development Status

Current public-beta line: **v3.0.3 / beta.1**

This repository is intentionally being released as a public beta before the major GUI and Blueprint-library redesign.

## Qualified in the current beta

- Normal startup and Safe Mode
- Qwen Image 2.1 reference-guided creation and editing
- FLUX.2 Klein image creation path
- Wan2.2 image-to-video setup path
- Live Create progress and output preview
- Blueprint-to-ComfyUI graph handoff
- Dynamic graph-derived reference inputs
- Lazy-loaded Library/Activity/Advanced surfaces
- Runtime input-contract validation against ComfyUI `/object_info`
- Update checker and development-source sync
- 22/22 automated tests in the v3.0.3 qualification pass

## Planned next

The next major work is product polish rather than piling on more tabs:

1. Major GUI/visual hierarchy overhaul.
2. More visual Blueprint and template cards with input/output previews.
3. Stronger Starter Pack guidance and dependency visualization.
4. Better workflow capability discovery from the live ComfyUI graph contract.
5. Expanded image/video/audio model families.
6. Windows and macOS platform adapters.
7. Public bug reports, qualification evidence, and repeatable release automation.

## Architecture direction

Keep one authority per domain:

- Blueprints define creation recipes.
- Packs define model/component dependencies.
- Compatible workflows expose generic image-reference inputs directly from the graph.
- ComfyUI remains the canonical execution graph/runtime.
- The Workstation provides orchestration, onboarding, validation, and visibility.

Do not create parallel rendering pipelines simply to make the GUI easier.
