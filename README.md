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

Current development candidate: **3.0.2**

## Current qualification note

3.0.2 fixes the WolfCat Library crash found in 3.0.1. The root cause was a GTK single-parent invariant violation in the Starter Packs details pane. Library, Activity, and Advanced sub-pages now lazy-load independently and a regression test scans GTK attachment sites for accidental multi-parenting.

Official binaries and release notes will be published only after local qualification is complete.

Canonical repository: `Superior-MI-Labs/Superior-MI-ComfyUI-Workstation`.
