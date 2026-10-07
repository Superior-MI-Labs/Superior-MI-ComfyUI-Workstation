from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Protocol


class ExecutionJournal(Protocol):
    def is_complete(self, action_fingerprint: str) -> bool: ...
    def record_complete(self, action_fingerprint: str, action_id: str, message: str = "") -> None: ...


class MemoryExecutionJournal:
    def __init__(self):
        self._complete: set[str] = set()
        self.records: list[dict[str, str]] = []

    def is_complete(self, action_fingerprint: str) -> bool:
        return action_fingerprint in self._complete

    def record_complete(self, action_fingerprint: str, action_id: str, message: str = "") -> None:
        self._complete.add(action_fingerprint)
        self.records.append({
            "action_fingerprint": action_fingerprint,
            "action_id": action_id,
            "message": message,
        })


class JsonlExecutionJournal:
    """Append-only action journal.

    Only completed action fingerprints are used for idempotent replay. Failed
    or interrupted actions are not silently promoted to complete.
    """

    def __init__(self, path: Path):
        self.path = Path(path)
        self._complete = self._load_complete()

    def _load_complete(self) -> set[str]:
        complete: set[str] = set()
        try:
            lines = self.path.read_text(encoding="utf-8").splitlines()
        except FileNotFoundError:
            return complete
        for raw in lines:
            try:
                row = json.loads(raw)
            except json.JSONDecodeError:
                continue
            if row.get("status") == "complete" and isinstance(row.get("action_fingerprint"), str):
                complete.add(row["action_fingerprint"])
        return complete

    def is_complete(self, action_fingerprint: str) -> bool:
        return action_fingerprint in self._complete

    def record_complete(self, action_fingerprint: str, action_id: str, message: str = "") -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        row = {
            "status": "complete",
            "action_fingerprint": action_fingerprint,
            "action_id": action_id,
            "message": message,
        }
        with self.path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(row, sort_keys=True, separators=(",", ":")) + "\n")
            handle.flush()
        self._complete.add(action_fingerprint)
