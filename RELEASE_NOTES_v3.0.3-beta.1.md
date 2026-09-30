# Superior MI Labs / ComfyUI Workstation v3.0.3 Public Beta

This is the first public beta of the Superior MI Labs ComfyUI Workstation.

The goal is straightforward: reduce the amount of manual setup between installing ComfyUI and actually creating something locally, while keeping ComfyUI itself as the real execution engine.

## What works in this beta

- Guided ComfyUI setup and runtime control
- Simple Create page with live generation progress and output preview
- FLUX.2 Klein and Qwen Image 2.1 image workflows
- Qwen Image 2.1 character/reference generation
- Wan2.2 TI2V image-to-video path
- Blueprint library that opens as real ComfyUI graphs
- Starter Packs / component management
- Expandable folder-based Character Library
- Activity, benchmarks, diagnostics, Safe Mode, and startup recovery
- Update checking through the canonical Superior MI Labs GitHub repository

## Important beta note

The GUI is functional, but it is not the final design.

A major GUI overhaul is planned, and the Blueprint/preset/template system will receive a large visual and organizational pass. The intention is to make model families, required inputs, expected outputs, starter packs, and workflow choices substantially easier to understand at a glance.

For now, the beta is already a quick way to install and control ComfyUI, install supported local model stacks, select a working Blueprint, create an image, and then open the resulting setup in ComfyUI without assembling the graph from scratch.

## v3.0.3 qualification fixes

This build includes fixes found during live WolfCat testing, including:

- GTK widget-parent ownership crash in the Library
- startup hardening and lazy page construction
- Qwen Image 2.1 V3 Autogrow reference-input compatibility
- Create controls derived from the selected Blueprint's capabilities
- runtime input validation against the local ComfyUI `/object_info` contract

The 3.0.3 candidate passed 22/22 automated tests plus Python, shell, JSON, ZIP, and Debian-package validation.

## Current platform

Linux Mint / Ubuntu / Debian-family Linux is the current supported target.

Windows and macOS adapters are planned. The application is being kept architecturally modular so platform-specific runtime, packaging, process, and GPU logic can be swapped without forking the core product.

## Install

Download:

`Superior-MI-Labs-ComfyUI-Workstation_3.0.3_all.deb`

Then:

```bash
cd ~/Downloads
sudo apt install ./Superior-MI-Labs-ComfyUI-Workstation_3.0.3_all.deb
```

Launch:

```bash
smi-comfyui
```

## Beta feedback

If something is confusing, crashes, exposes an option the selected graph cannot actually use, or fails to translate cleanly into ComfyUI, please report it. Those are exactly the kinds of issues this beta is intended to surface.
