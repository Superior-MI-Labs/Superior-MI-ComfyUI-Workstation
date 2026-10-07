from pathlib import Path
import json
import sys

APP = Path(__file__).resolve().parents[1] / "app"
sys.path.insert(0, str(APP))

import startup_guard


def test_startup_guard_persists_last_stage_and_append_only_log(tmp_path, monkeypatch):
    cache = tmp_path / "cache"
    state = cache / "startup-state.json"
    log = cache / "startup-stage.log"

    monkeypatch.setattr(startup_guard, "CACHE", cache)
    monkeypatch.setattr(startup_guard, "STATE", state)
    monkeypatch.setattr(startup_guard, "LOG", log)

    startup_guard.stage("bootstrap", "begin")
    first = json.loads(state.read_text(encoding="utf-8"))
    assert first["stage"] == "bootstrap"
    assert first["detail"] == "begin"

    startup_guard.complete()
    latest = json.loads(state.read_text(encoding="utf-8"))
    assert latest["stage"] == "ready"
    assert latest["detail"] == "main window presented"

    lines = log.read_text(encoding="utf-8").splitlines()
    assert len(lines) == 2
    assert "stage=bootstrap" in lines[0]
    assert "stage=ready" in lines[1]


def test_startup_guard_failure_to_persist_does_not_crash(monkeypatch):
    class BrokenPath:
        def mkdir(self, *args, **kwargs):
            raise OSError("read-only")

    monkeypatch.setattr(startup_guard, "CACHE", BrokenPath())
    startup_guard.stage("test", "must fail soft")
