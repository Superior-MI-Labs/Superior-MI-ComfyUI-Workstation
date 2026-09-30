from __future__ import annotations
import os, platform, shutil, subprocess, webbrowser
from pathlib import Path


def system_name() -> str:
    return platform.system() or "Unknown"


def support_level() -> str:
    s = system_name()
    if s == "Linux":
        return "supported"
    if s in {"Windows", "Darwin"}:
        return "planned"
    return "unknown"


def open_target(target) -> None:
    text = str(target)
    s = system_name()
    if s == "Linux" and shutil.which("xdg-open"):
        subprocess.Popen(["xdg-open", text], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    elif s == "Darwin" and shutil.which("open"):
        subprocess.Popen(["open", text], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    elif s == "Windows":
        os.startfile(text)  # type: ignore[attr-defined]
    else:
        webbrowser.open(text)
