# Platform strategy

Version 2.2 is qualified for Linux desktop use and currently packages a Debian installer. The internal application is being separated from platform-specific shell integration so Windows and macOS can be added without creating separate product logic.

## Already portable

- character scanning and metadata
- preset/model catalog data
- generated ComfyUI workflows
- HTTP communication with ComfyUI
- most model-library logic
- path handling through `pathlib`
- external-target opening through a small platform adapter

## Linux-specific today

- `.desktop`/icon installation
- Debian package
- `/proc` based process ownership checks
- `nvidia-smi` diagnostics
- apt dependency installation
- shell launcher scripts
- libnotify/zenity integration

## Windows target

A Windows package should use a single PowerShell/bootstrap layer, Start Menu shortcut, Task Scheduler only when explicitly requested, Windows process inspection, and the same Python/GTK-or-replacement UI core. ComfyUI should remain the single runtime authority.

## macOS target

A macOS package should use an `.app` bundle/DMG, `open` integration, native process inspection, and Apple Silicon-aware PyTorch/ComfyUI setup. NVIDIA-specific stack recommendations must be hidden there.

The key rule is one application state model and one ComfyUI contract, with OS-specific adapters at the boundary rather than separate forks.
