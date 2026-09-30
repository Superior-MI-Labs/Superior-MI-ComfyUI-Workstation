# Development Qualification

This repository is intentionally pre-release.

## Candidate

**3.0.2**

## Current regression

WolfCat exposed a deterministic crash when opening Library in 3.0.1.

Cause:

```text
right_sc.add(right)
paned.pack2(right, ...)
```

The same GTK widget was attached to two parents. GTK widgets have a single-parent ownership contract.

3.0.2 changes the paned child to the scrolled container and adds a static parent-ownership regression test. Nested Library, Activity, and Advanced pages also lazy-load so unrelated feature pages are not constructed simply by opening another section.

## Release gate

Do not create an official release until the candidate is exercised on the target Linux Mint workstation, including Create, Blueprints, Starter Packs, Characters, Activity, updater checks, and ComfyUI bridge behavior.
