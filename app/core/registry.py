from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable

from .contracts import (
    AssetRequirement,
    CapabilityDefinition,
    ImplementationCandidate,
)


@dataclass(frozen=True)
class CapabilityRegistry:
    entries: tuple[CapabilityDefinition, ...]

    def __post_init__(self):
        ids = [entry.id for entry in self.entries]
        if len(ids) != len(set(ids)):
            raise ValueError("Capability IDs must be unique.")

    def by_id(self) -> dict[str, CapabilityDefinition]:
        return {entry.id: entry for entry in self.entries}

    def require(self, capability_id: str) -> CapabilityDefinition:
        try:
            return self.by_id()[capability_id]
        except KeyError as exc:
            raise KeyError(f"Unknown capability: {capability_id}") from exc


@dataclass(frozen=True)
class ImplementationRegistry:
    entries: tuple[ImplementationCandidate, ...]

    def __post_init__(self):
        ids = [entry.id for entry in self.entries]
        if len(ids) != len(set(ids)):
            raise ValueError("Implementation IDs must be unique.")

    def by_id(self) -> dict[str, ImplementationCandidate]:
        return {entry.id: entry for entry in self.entries}

    def for_capability(self, capability_id: str) -> tuple[ImplementationCandidate, ...]:
        return tuple(
            entry for entry in self.entries if capability_id in entry.capabilities
        )


def load_capability_registry(path: Path) -> CapabilityRegistry:
    payload = json.loads(path.read_text(encoding="utf-8"))
    rows = payload.get("capabilities", [])
    if not isinstance(rows, list):
        raise ValueError("Capability catalog must contain a capabilities list.")

    entries = []
    for row in rows:
        if not isinstance(row, dict):
            raise ValueError("Capability entries must be objects.")
        entries.append(
            CapabilityDefinition(
                id=str(row["id"]),
                title=str(row["title"]),
                description=str(row.get("description", "")),
                input_media=tuple(str(x) for x in row.get("input_media", [])),
                output_media=tuple(str(x) for x in row.get("output_media", [])),
            )
        )
    return CapabilityRegistry(tuple(entries))


def _asset_rows(rows) -> tuple[AssetRequirement, ...]:
    assets = []
    for row in rows or []:
        if not isinstance(row, dict):
            raise ValueError("Implementation asset entries must be objects.")
        assets.append(
            AssetRequirement(
                id=str(row["id"]),
                size_bytes=max(0, int(row.get("size_bytes", 0))),
            )
        )
    return tuple(assets)


def load_implementation_registry(path: Path) -> ImplementationRegistry:
    payload = json.loads(path.read_text(encoding="utf-8"))
    rows = payload.get("implementations", [])
    if not isinstance(rows, list):
        raise ValueError("Implementation catalog must contain an implementations list.")

    entries = []
    for row in rows:
        if not isinstance(row, dict):
            raise ValueError("Implementation entries must be objects.")
        entries.append(
            ImplementationCandidate(
                id=str(row["id"]),
                title=str(row["title"]),
                capabilities=tuple(str(x) for x in row.get("capabilities", [])),
                backend=str(row.get("backend", "cpu")),
                platforms=tuple(str(x) for x in row.get("platforms", [])),
                architectures=tuple(str(x) for x in row.get("architectures", [])),
                min_vram_bytes=max(0, int(row.get("min_vram_bytes", 0))),
                recommended_vram_bytes=max(0, int(row.get("recommended_vram_bytes", 0))),
                min_ram_bytes=max(0, int(row.get("min_ram_bytes", 0))),
                assets=_asset_rows(row.get("assets", [])),
                packages=tuple(str(x) for x in row.get("packages", [])),
                blueprint_id=str(row.get("blueprint_id", "")),
                execution_mode=str(row.get("execution_mode", "local")),
                stability=str(row.get("stability", "stable")),
                evidence_score=int(row.get("evidence_score", 0)),
                preference_scores={
                    str(key): int(value)
                    for key, value in (row.get("preference_scores", {}) or {}).items()
                },
                license_status=str(row.get("license_status", "open")),
            )
        )
    return ImplementationRegistry(tuple(entries))
