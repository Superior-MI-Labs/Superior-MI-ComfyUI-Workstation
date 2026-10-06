# Character Studio

Status: deferred future add-on

Character support existed as a first-class feature in the 3.0 public beta.
It is intentionally being removed from Workstation Core during the Core R1
refactor.

Character Studio may return later as an experience add-on that consumes generic
Core capabilities such as image generation, reference-image input, editing,
video generation, and audio/speech.

Workstation Core must not own domain concepts such as:
- Character identity;
- canonical reference collections;
- wardrobe;
- expressions;
- character-aware Blueprint flags;
- Character-specific creation modes.

The legacy implementation remains in the migration branch only until the
replacement Core architecture is qualified and Prompt 8 performs destructive
cleanup. Git history preserves the original implementation and beta behavior.

See `docs/WORKSTATION-CORE-R1-PLAN.md`.
